import { PipecatClient } from "@pipecat-ai/client-js";
import { DailyTransport } from "@pipecat-ai/daily-transport";
import {
  PipecatClientProvider,
  PipecatClientAudio,
} from "@pipecat-ai/client-react";
import Bot from "./Bot";
import "./index.css";

// Create the client instance
const client = new PipecatClient({
  transport: new DailyTransport(),
  enableMic: false,
});

export default function App() {
  return (
    <PipecatClientProvider client={client}>
      <Bot />
      <PipecatClientAudio />
    </PipecatClientProvider>
  );
}
