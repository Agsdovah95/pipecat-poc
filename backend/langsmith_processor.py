"""
LangSmith span processor for Pipecat.

Enriches OpenTelemetry spans from Pipecat with LangSmith-compatible attributes
for proper conversation tracking and visualization.
"""
import base64
import json
from pathlib import Path
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import SpanProcessor, ReadableSpan, TracerProvider
from opentelemetry import trace
from loguru import logger
from pipecat.utils.tracing.setup import setup_tracing


class LangSmithSTTSpanProcessor(SpanProcessor):
    """
    Custom OpenTelemetry span processor that enriches Pipecat spans with LangSmith-compatible attributes.
    This enables proper conversation tracking and message visualization in LangSmith's UI.
    """

    def __init__(self):
        super().__init__()
        # Track conversation messages across spans for proper LangSmith grouping
        self.conversation_messages = {}  # trace_id -> list of messages
        self.turn_messages = {}  # parent_span_id -> list of messages
        self.trace_to_conversation_id = {}  # trace_id -> conversation_id
        self.conversation_recordings = {}  # conversation_id -> recording_path
        self.conversation_recorders = {}  # conversation_id -> AudioRecorder instance
        self.turn_recordings = {}  # conversation_id -> {turn_number: {user: path, ai: path}}
        self.turn_audio_recorders = {}  # conversation_id -> TurnAudioRecorder instance

    def on_start(self, span: ReadableSpan, parent_context=None) -> None:
        pass
    
    def register_recording(self, conversation_id: str, recording_path: str, audio_recorder=None):
        """Register a recording path and optional audio recorder for a conversation to attach to the root span."""
        self.conversation_recordings[conversation_id] = recording_path
        if audio_recorder:
            self.conversation_recorders[conversation_id] = audio_recorder

    def register_turn_audio_recorder(self, conversation_id: str, turn_audio_recorder):
        """
        Register the TurnAudioRecorder instance for a conversation.
        This allows the span processor to call save_turn_audio_sync() when turn spans end.

        Args:
            conversation_id: The conversation ID
            turn_audio_recorder: TurnAudioRecorder instance
        """
        self.turn_audio_recorders[conversation_id] = turn_audio_recorder

    def register_turn_recording(self, conversation_id: str, turn_number: int, recording_paths: dict):
        """
        Register turn-specific audio recordings for attachment to turn spans.

        Args:
            conversation_id: The conversation ID
            turn_number: The turn number
            recording_paths: Dict with 'user' and/or 'ai' keys pointing to WAV file paths
        """
        if conversation_id not in self.turn_recordings:
            self.turn_recordings[conversation_id] = {}
        self.turn_recordings[conversation_id][turn_number] = recording_paths
    
    def on_end(self, span: ReadableSpan) -> None:
        """
        Enriches spans with LangSmith-compatible attributes before they're exported.
        Maps Pipecat span types (stt, llm, tts, turn, conversation) to LangSmith's expected format.
        """
        # Track each conversation as a thread in LangSmith
        trace_id = format(span.context.trace_id, '032x')
        span._attributes["langsmith.metadata.thread_id"] = trace_id

        # Link all spans to their conversation for proper grouping in LangSmith
        if trace_id in self.trace_to_conversation_id:
            conversation_id = self.trace_to_conversation_id[trace_id]
            span._attributes["conversation.id"] = conversation_id
            span._attributes["langsmith.parent_span_id"] = "conversation"
        
        # STT span: audio input -> transcribed text
        if span.name == "stt":
            transcript = span.attributes.get("transcript", "")
            span._attributes["langsmith.span.kind"] = "llm"
            self._set_prompt_attributes(span, [{"role": "user", "content": "audio_segment"}])
            self._set_completion_attributes(span, [{"role": "assistant", "content": transcript}])
        
        # LLM span: conversation messages -> AI response
        elif span.name == "llm":
            input_data = span.attributes.get("input", "")
            output_data = span.attributes.get("output", "")
            span._attributes["langsmith.span.kind"] = "llm"

            # Parse and add input messages
            messages = []
            try:
                messages = json.loads(input_data)
                self._set_prompt_attributes(span, messages)
            except json.JSONDecodeError:
                pass

            # Add LLM output
            if output_data:
                self._set_completion_attributes(span, [{"role": "assistant", "content": output_data}])

            # Track messages for aggregating into turn and conversation spans
            parent_span_id = format(span.parent.span_id, '016x') if span.parent else None
            self._track_messages(self.conversation_messages, trace_id, messages, output_data)
            if parent_span_id:
                self._track_messages(self.turn_messages, parent_span_id, messages, output_data)
        
        # TTS span: text -> audio
        elif span.name == "tts":
            text = span.attributes.get("text", "")
            voice_id = span.attributes.get("voice_id", "")
            span._attributes["langsmith.span.kind"] = "llm"
            self._set_prompt_attributes(span, [
                {"role": "system", "content": f"Convert to speech with voice: {voice_id}"},
                {"role": "user", "content": text}
            ])
            self._set_completion_attributes(span, [{"role": "assistant", "content": f"Generated audio for: {text}"}])
        
        # Turn span: represents a single user-assistant interaction
        elif span.name == "turn":
            turn_number = span.attributes.get("turn.number", 0)
            was_interrupted = span.attributes.get("turn.was_interrupted", False)
            span._attributes["langsmith.span.kind"] = "chain"

            # Aggregate messages from this turn's child spans
            span_id = format(span.context.span_id, '016x')
            turn_msgs = self.turn_messages.get(span_id, [])
            user_msgs = self._get_messages_by_role(turn_msgs, "user")
            assistant_msgs = self._get_messages_by_role(turn_msgs, "assistant")

            # Add user input(s)
            if user_msgs:
                self._set_prompt_attributes(span, user_msgs)
            else:
                self._set_prompt_attributes(span, [{"role": "user", "content": f"Turn {turn_number}"}])

            # Add assistant response(s)
            if assistant_msgs:
                self._set_completion_attributes(span, assistant_msgs)
            else:
                status = "interrupted" if was_interrupted else "no response"
                self._set_completion_attributes(span, [{"role": "assistant", "content": status}])

            # Attach turn audio files - save them NOW before span is exported
            conversation_id = span.attributes.get("conversation.id", "")
            if not conversation_id:
                conversation_id = self.trace_to_conversation_id.get(trace_id, "")

            # Get the turn audio recorder and save files synchronously RIGHT NOW
            if conversation_id and conversation_id in self.turn_audio_recorders:
                turn_audio_recorder = self.turn_audio_recorders[conversation_id]

                # Save files synchronously before span is exported
                turn_files = turn_audio_recorder.save_turn_audio_sync(turn_number)

                if turn_files:
                    attachments = []

                    # Attach user audio
                    if 'user' in turn_files:
                        user_audio = self._load_audio_file(turn_files['user'])
                        if user_audio:
                            attachments.append({
                                "name": f"turn_{turn_number}_user.wav",
                                "content": user_audio,
                                "mime_type": "audio/wav"
                            })

                    # Attach AI audio
                    if 'ai' in turn_files:
                        ai_audio = self._load_audio_file(turn_files['ai'])
                        if ai_audio:
                            attachments.append({
                                "name": f"turn_{turn_number}_ai.wav",
                                "content": ai_audio,
                                "mime_type": "audio/wav"
                            })

                    if attachments:
                        span._attributes["langsmith.attachments"] = json.dumps(attachments)

            # Cleanup
            if span_id in self.turn_messages:
                del self.turn_messages[span_id]
        
        # Conversation span: represents the entire conversation session
        elif span.name == "conversation":
            conversation_id = span.attributes.get("conversation.id", "")
            conversation_type = span.attributes.get("conversation.type", "voice")

            # Try alternative conversation_id keys if the standard one is empty
            if not conversation_id:
                conversation_id = span.attributes.get("conversation_id", "")

            # Store conversation_id for linking child spans
            self.trace_to_conversation_id[trace_id] = conversation_id

            span._attributes["langsmith.span.kind"] = "chain"
            span._attributes["langsmith.root_span"] = True

            # Aggregate all messages from the conversation
            conv_msgs = self.conversation_messages.get(trace_id, [])

            if conv_msgs:
                system_msg, first_user_msg, remaining_msgs = self._split_conversation_messages(conv_msgs)

                # Add input (first user message only, exclude system message)
                prompt_msgs = []
                if first_user_msg:
                    prompt_msgs.append(first_user_msg)
                self._set_prompt_attributes(span, prompt_msgs)

                # Add output (remaining conversation)
                if remaining_msgs:
                    self._set_completion_attributes(span, remaining_msgs)
                else:
                    self._set_completion_attributes(span, [{"role": "assistant", "content": "No responses yet"}])
            else:
                self._set_prompt_attributes(span, [{"role": "system", "content": f"Starting {conversation_type} conversation"}])
                self._set_completion_attributes(span, [{"role": "assistant", "content": "No messages"}])

            # Save and attach recording if available
            # First, try to save the recording if we have the audio recorder instance
            if conversation_id and conversation_id in self.conversation_recorders:
                audio_recorder = self.conversation_recorders[conversation_id]
                try:
                    audio_recorder.save_recording()
                except Exception as e:
                    logger.warning(f"Failed to save recording for conversation {conversation_id}: {e}")

            # Try to find recording by conversation_id, or use single available recording
            recording_path_str = None
            if conversation_id and conversation_id in self.conversation_recordings:
                recording_path_str = self.conversation_recordings[conversation_id]
            elif len(self.conversation_recordings) == 1:
                # If there's only one recording, use it (likely this conversation)
                recording_path_str = list(self.conversation_recordings.values())[0]
            
            if recording_path_str:
                recording_path = Path(recording_path_str)

                # Try to read the file once - don't block the telemetry pipeline with retries
                # The file should already exist since save_recording() is called before span ends
                if recording_path.exists():
                    try:
                        with open(recording_path, 'rb') as f:
                            audio_data = f.read()
                            if audio_data:  # Ensure file is not empty
                                audio_base64 = base64.b64encode(audio_data).decode('utf-8')

                                attachments = [{
                                    "name": recording_path.name,
                                    "content": audio_base64,
                                    "mime_type": "audio/wav"
                                }]

                                span._attributes["langsmith.attachments"] = json.dumps(attachments)
                                logger.debug(f"Attached recording {recording_path.name} to conversation span")
                            else:
                                logger.warning(f"Recording file {recording_path} exists but is empty")
                    except Exception as e:
                        logger.warning(f"Failed to read recording file {recording_path}: {e}")
                else:
                    logger.warning(f"Recording file {recording_path} does not exist when attaching to span")

            # Cleanup
            if trace_id in self.conversation_messages:
                del self.conversation_messages[trace_id]
            if trace_id in self.trace_to_conversation_id:
                del self.trace_to_conversation_id[trace_id]
            if conversation_id in self.conversation_recordings:
                del self.conversation_recordings[conversation_id]
            if conversation_id in self.conversation_recorders:
                del self.conversation_recorders[conversation_id]
            if conversation_id in self.turn_recordings:
                del self.turn_recordings[conversation_id]
            if conversation_id in self.turn_audio_recorders:
                del self.turn_audio_recorders[conversation_id]
    
    def _set_prompt_attributes(self, span: ReadableSpan, messages: list, start_idx: int = 0):
        """Set gen_ai.prompt.* attributes from a list of messages."""
        for i, msg in enumerate(messages):
            idx = start_idx + i
            span._attributes[f"gen_ai.prompt.{idx}.role"] = msg.get("role", "")
            span._attributes[f"gen_ai.prompt.{idx}.content"] = msg.get("content", "")
    
    def _set_completion_attributes(self, span: ReadableSpan, messages: list, start_idx: int = 0):
        """Set gen_ai.completion.* attributes from a list of messages."""
        for i, msg in enumerate(messages):
            idx = start_idx + i
            span._attributes[f"gen_ai.completion.{idx}.role"] = msg.get("role", "")
            span._attributes[f"gen_ai.completion.{idx}.content"] = msg.get("content", "")
    
    def _get_messages_by_role(self, messages: list, role: str) -> list:
        """Filter messages by role."""
        return [msg for msg in messages if msg.get("role") == role]
    
    def _split_conversation_messages(self, messages: list) -> tuple:
        """
        Split conversation messages into system, first user, and remaining messages.
        Returns: (system_msg, first_user_msg, remaining_msgs)
        """
        system_msg = None
        first_user_msg = None
        remaining_msgs = []
        first_user_found = False

        for msg in messages:
            role = msg.get("role", "")
            if role == "system" and system_msg is None:
                system_msg = msg
            elif role == "user" and not first_user_found:
                first_user_msg = msg
                first_user_found = True
            elif first_user_found:
                remaining_msgs.append(msg)

        return (system_msg, first_user_msg, remaining_msgs)
    
    def _track_messages(self, target_dict: dict, key: str, messages: list, output_data: str):
        """
        Track messages in target_dict, avoiding duplicates.
        Preserves all deduplication logic: case-insensitive content comparison,
        system prompt handling, and duplicate detection.
        """
        if key not in target_dict:
            target_dict[key] = []
            # Add system prompt once at the start
            for msg in messages:
                if msg.get("role") == "system":
                    target_dict[key].append(msg)
                    break

        # Add the latest user message if it's new
        last_user_msg = next((msg for msg in reversed(messages) if msg.get("role") == "user"), None)
        if last_user_msg:
            new_content = last_user_msg.get("content", "").strip().lower()
            existing_contents = [m.get("content", "").strip().lower()
                                for m in target_dict[key] if m.get("role") == "user"]
            if new_content and new_content not in existing_contents:
                target_dict[key].append(last_user_msg)

        # Add the assistant response if it's new
        if output_data:
            new_assistant_content = output_data.strip().lower()
            existing_assistant_contents = [m.get("content", "").strip().lower()
                                          for m in target_dict[key] if m.get("role") == "assistant"]
            if new_assistant_content not in existing_assistant_contents:
                target_dict[key].append({"role": "assistant", "content": output_data})

    def _load_audio_file(self, file_path: str):
        """
        Load and base64 encode an audio file.

        Args:
            file_path: Path to the audio file

        Returns:
            Base64-encoded audio data or None if file doesn't exist/can't be read
        """
        try:
            recording_path = Path(file_path)
            if recording_path.exists():
                with open(recording_path, 'rb') as f:
                    audio_data = f.read()
                    if audio_data:
                        return base64.b64encode(audio_data).decode('utf-8')
        except Exception as e:
            logger.warning(f"Failed to load audio file {file_path}: {e}")
        return None

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


# Setup OpenTelemetry tracing with LangSmith
# Configure OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS in your .env
setup_tracing(
    service_name="pipecat-langsmith-demo",
    exporter=OTLPSpanExporter(),
    console_export=False,  # Disable console export to avoid base64 audio spam
)

# Register our custom span processor to enrich Pipecat spans for LangSmith
tracer_provider = trace.get_tracer_provider()
if isinstance(tracer_provider, TracerProvider):
    span_processor = LangSmithSTTSpanProcessor()
    tracer_provider.add_span_processor(span_processor)
else:
    # Fallback if tracer provider is not the expected type
    span_processor = LangSmithSTTSpanProcessor()
