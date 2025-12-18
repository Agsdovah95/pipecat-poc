import { useState, useRef } from "react";
import {
    PipecatClientMicToggle,
    VoiceVisualizer,
    usePipecatClient,
    usePipecatClientTransportState,
} from "@pipecat-ai/client-react";
import DeviceSelector from "./DeviceSelector";
import MediaTracks from "./MediaTrack";
import "./App.css";

// Transport state display names
const transportStateDisplay: Record<string, string> = {
    idle: "Idle",
    initializing: "Initializing",
    initialized: "Initialized",
    connecting: "Connecting",
    connected: "Connected",
    ready: "Ready",
    disconnected: "Disconnected",
    error: "Error",
};

export default function Bot() {
    const pcClient = usePipecatClient();
    const transportState = usePipecatClientTransportState();
    const [wsError, setWsError] = useState<string | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    const currentState = transportState || "idle";
    const isConnected = currentState === "connected" || currentState === "ready";
    const isConnecting = currentState === "connecting" || currentState === "initializing" || currentState === "initialized";


    const connectbot = async () => {
        setWsError(null);

        const wsUrl = import.meta.env.VITE_WEBSOCKET_URL || "ws://0.0.0.0:8765";

        try {
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log("WebSocket connected");
            };

            ws.onmessage = async (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const { room_url, token } = data;

                    if (room_url && token) {
                        console.log("Received room_url and token from WebSocket");
                        try {

                            await pcClient?.connect({
                                url: room_url,
                                token: token
                            });

                        } catch (connectErr) {
                            console.error("Error connecting to Daily:", connectErr);
                            if (connectErr instanceof Error && connectErr.name === "NotFoundError") {
                                setWsError("Microphone not found. Please check your audio device settings.");
                            } else {
                                setWsError(`Connection failed: ${connectErr instanceof Error ? connectErr.message : 'Unknown error'}`);
                            }
                        }
                    }
                } catch (err) {
                    console.error("Error parsing WebSocket message:", err);
                    setWsError("Failed to parse server response");
                }
            };

            ws.onerror = (error) => {
                console.error("WebSocket error:", error);
                setWsError("WebSocket connection failed");
            };

            ws.onclose = () => {
                console.log("WebSocket closed");
                wsRef.current = null;
            };
        } catch (err) {
            console.error("Failed to connect to WebSocket:", err);
            setWsError("Failed to connect to WebSocket");
        }
    };

    const disconnect = async () => {
        // Close WebSocket if open
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
        await pcClient?.disconnect();
    };

    return (
        <div className="app-container">

            {/* Main Card */}
            <div className="main-card">

                {/* Device Selector Section */}
                <DeviceSelector />

                {/* Transport Info */}
                <div className="transport-info">
                    <div className="transport-icon">📡</div>
                    <div className="transport-details">
                        <div className="transport-label">Transport Status</div>
                        <div className="transport-state">
                            {transportStateDisplay[currentState] || currentState}
                        </div>
                    </div>
                </div>

                {/* WebSocket Error */}
                {wsError && (
                    <div className="ws-error">
                        <span className="ws-error-icon">⚠️</span>
                        <span>{wsError}</span>
                    </div>
                )}


                {/* Connecting State */}
                {isConnecting && (
                    <div className="idle-state">
                        <div className="idle-icon">
                            <div className="idle-circle" style={{ animation: 'rotate 2s linear infinite' }}>⚡</div>
                            <div className="idle-pulse"></div>
                        </div>
                        <p className="idle-text">Establishing connection...</p>
                        <p className="idle-subtext">Please wait a moment</p>
                    </div>
                )}

                {/* Active State - Show when connected */}
                {isConnected && (
                    <div className="active-state">
                        {/* Audio Visualization */}
                        <div className="audio-section">
                            <div className="audio-label">Audio Activity</div>
                            <div className="audio-visualizer-wrapper">
                                <div className="dual-visualizer">
                                    {/* Your Voice */}
                                    <div className="visualizer-row">
                                        <span className="visualizer-label">You</span>
                                        <div className="visualizer-container">
                                            <VoiceVisualizer
                                                participantType="local"
                                                backgroundColor="transparent"
                                                barColor="#06b6d4"
                                                barGap={2}
                                                barWidth={3}
                                                barMaxHeight={32}
                                            />
                                        </div>
                                    </div>

                                    {/* Bot Voice */}
                                    <div className="visualizer-row">
                                        <span className="visualizer-label">AI</span>
                                        <div className="visualizer-container">
                                            <VoiceVisualizer
                                                participantType="bot"
                                                backgroundColor="transparent"
                                                barColor="#a855f7"
                                                barGap={2}
                                                barWidth={3}
                                                barMaxHeight={32}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Media Tracks Display */}
                        <MediaTracks />

                        {/* Microphone Toggle */}
                        <PipecatClientMicToggle
                            onMicEnabledChanged={(enabled) => console.log("Microphone enabled:", enabled)}
                            disabled={false}
                        >
                            {({ disabled, isMicEnabled, onClick }) => (
                                <div className="mic-toggle-section">
                                    <div className="mic-info">
                                        <div className={`mic-icon ${isMicEnabled ? 'enabled' : 'disabled'}`}>
                                            {isMicEnabled ? '🎤' : '🔇'}
                                        </div>
                                        <div>
                                            <div className="mic-label">Microphone</div>
                                            <div className="mic-status">
                                                {isMicEnabled ? 'Listening...' : 'Muted'}
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        className={`mic-toggle-btn ${isMicEnabled ? 'enabled' : 'disabled'}`}
                                        disabled={disabled}
                                        onClick={onClick}
                                        aria-label={isMicEnabled ? "Disable Microphone" : "Enable Microphone"}
                                    />
                                </div>
                            )}
                        </PipecatClientMicToggle>



                    </div>
                )}

                {/* Connect/Disconnect Button */}
                {!isConnected ? (
                    <button
                        className={`connect-btn primary ${isConnecting ? 'loading' : ''}`}
                        onClick={connectbot}
                        disabled={isConnecting}
                    >
                        {isConnecting ? 'Connecting...' : 'Connect'}
                    </button>
                ) : (
                    <button
                        className="connect-btn secondary"
                        onClick={disconnect}
                    >
                        Disconnect
                    </button>
                )}
            </div>
        </div>
    );
}
