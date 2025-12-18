import asyncio
import json
import os
import time
import uuid

import aiohttp
from dotenv import load_dotenv
from langsmith_processor import span_processor  # noqa: F401
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.mem0.memory import Mem0MemoryService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat.transports.daily.utils import (
    DailyRESTHelper,
    DailyRoomParams,
    DailyRoomProperties,
)
from pydantic import BaseModel
from tavily import TavilyClient
from websockets.asyncio.server import serve

from pipecat.audio.turn.smart_turn.base_smart_turn import SmartTurnParams
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

from pipecat.observers.loggers.user_bot_latency_log_observer import UserBotLatencyLogObserver



class Room(BaseModel):
    url: str


load_dotenv()


tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

ROOM_NAME = "arnab-test-room-18122025"


async def search_internet(params: FunctionCallParams, query: str):
    """Do internet search

    Args:
        query: query to search on the internet.
    """
    response = tavily_client.search(query)

    await params.result_callback(response)


async def create_daily_room() -> tuple[str, str]:
    async with aiohttp.ClientSession() as session:
        helper = DailyRESTHelper(
            daily_api_key=os.environ["DAILY_API_KEY"], aiohttp_session=session
        )

        params = DailyRoomParams(
            name=ROOM_NAME,
            privacy="private",
            properties=DailyRoomProperties(
                exp=time.time() + 3600 * 8, enable_chat=True
            ),
        )

        try:
            room = await helper.create_room(params)
        except Exception:
            room = Room(url=f"https://prediqt.daily.co/{ROOM_NAME}")

        token = await helper.get_token(
            room_url=room.url,
            expiry_time=3600 * 8,  # 8 hours
            owner=True,
            eject_at_token_exp=True,
        )

        return room.url, token


async def delete_room() -> None:
    async with aiohttp.ClientSession() as session:
        helper = DailyRESTHelper(
            daily_api_key=os.environ["DAILY_API_KEY"], aiohttp_session=session
        )
        success = await helper.delete_room_by_name(ROOM_NAME)
        if success:
            print(f"Room {ROOM_NAME} deleted successfully")


async def websocket_handler(websocket):
    """Handle WebSocket connection: send token and start bot."""
    print("Frontend connected via WebSocket")

    # Create the Daily room
    (room_url, token) = await create_daily_room()

    # Send token and room_url as JSON to frontend
    await websocket.send(json.dumps({"room_url": room_url, "token": token}))
    print(f"Sent credentials to frontend: {room_url}")

    # Close the WebSocket connection
    await websocket.close()
    print("WebSocket connection closed")

    # Start the bot with the credentials
    await run_bot(room_url, token)


async def run_bot(room_url: str, token: str):
    conversation_id = str(uuid.uuid4())

    transport = DailyTransport(
        room_url,
        token,
        "Simple Bot",
        DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            transcription_enabled=False,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.1)),
            turn_analyzer=LocalSmartTurnAnalyzerV3(params=SmartTurnParams()),
        ),
    )

    stt = DeepgramSTTService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        live_options=LiveOptions(model="nova-3-general"),
    )

    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        voice_id=os.environ["CARTESIA_VOICE_ID"],
    )

    llm = OpenAILLMService(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini")

    messages = [
        {
            "role": "system",
            "content": """
                You are Jane, A personal assistant. 
                answer the user questions to the best of your knowledge,
                and use the available tools to search the internet about anything you can not answer directly.
                Also in case users wants to know about news today or weather info directly use the tool to find 
                that inforamtion

                Initially introduce yourself to the user and tell briefly what you can do to start the convo

                Do not mention the http urls coming from the tool calling to the user. only share the weather or new itself.
            """,
        },
    ]

    tools = ToolsSchema(standard_tools=[search_internet])

    llm.register_direct_function(search_internet, cancel_on_interruption=True)

    context = LLMContext(messages, tools=tools)
    context_aggregator = LLMContextAggregatorPair(context)

    memory = Mem0MemoryService(
        api_key=os.environ["MEM0_API_KEY"],
        user_id="arnab",
        agent_id="agent1",
        run_id="session1",
        params=Mem0MemoryService.InputParams(
            search_limit=10,
            search_threshold=0.3,
            api_version="v2",
            system_prompt="Based on previous conversations, Here is What I recall: \n\n",
            add_as_system_message=True,
            position=1,
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            memory,
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
            observers=[UserBotLatencyLogObserver()],
        ),
        enable_tracing=True,
        enable_turn_tracking=True,
        conversation_id=conversation_id,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        print("Client disconnected")
        await task.cancel()
        await delete_room()

    runner = PipelineRunner()

    await runner.run(task)


if __name__ == "__main__":
    import asyncio

    async def main():
        async with serve(websocket_handler, "0.0.0.0", 8765):
            print("WebSocket server started on ws://0.0.0.0:8765")
            print("Waiting for frontend connection...")
            await asyncio.Future()

    asyncio.run(main())
