import { useState } from "react";
import { usePipecatClientMediaDevices } from "@pipecat-ai/client-react";

function DeviceSelector() {
    const {
        availableMics,
        selectedMic,
        updateMic,
    } = usePipecatClientMediaDevices();
    
    const [isRequestingPermission, setIsRequestingPermission] = useState(false);

    const requestMicrophoneAccess = async () => {
        setIsRequestingPermission(true);
        try {
            await navigator.mediaDevices.getUserMedia({ audio: true });
            // After permission granted, the device list should refresh automatically
        } catch (err) {
            console.error("Failed to get microphone access:", err);
        } finally {
            setIsRequestingPermission(false);
        }
    };

    // Show permission request if no devices available
    if (availableMics.length === 0) {
        return (
            <div className="device-selector-section">
                <label className="device-selector-label">
                    Input Device
                </label>
                <button 
                    className="device-permission-btn"
                    onClick={requestMicrophoneAccess}
                    disabled={isRequestingPermission}
                >
                    {isRequestingPermission ? "Requesting..." : "🎤 Allow Microphone Access"}
                </button>
            </div>
        );
    }

    return (
        <div className="device-selector-section">
            <label className="device-selector-label" htmlFor="mic-select">
                Input Device
            </label>
            <select
                id="mic-select"
                className="device-select"
                name="mic"
                onChange={(ev) => updateMic(ev.target.value)}
                value={selectedMic?.deviceId}
            >
                {availableMics.map((mic) => (
                    <option key={mic.deviceId} value={mic.deviceId}>
                        {mic.label || `Microphone ${mic.deviceId.slice(0, 8)}...`}
                    </option>
                ))}
            </select>
        </div>
    );
}

export default DeviceSelector;
