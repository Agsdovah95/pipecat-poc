import { usePipecatClientMediaTrack } from "@pipecat-ai/client-react";
import { useEffect, useState } from "react";
import "./MediaTrack.css";

function MediaTracks() {
    const localAudioTrack = usePipecatClientMediaTrack("audio", "local");
    const botAudioTrack = usePipecatClientMediaTrack("audio", "bot");
    
    const [localLevel, setLocalLevel] = useState(0);
    const [botLevel, setBotLevel] = useState(0);

    // Create audio level analyzers for both tracks
    useEffect(() => {
        if (!localAudioTrack) return;
        
        const audioContext = new AudioContext();
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        
        const source = audioContext.createMediaStreamSource(
            new MediaStream([localAudioTrack])
        );
        source.connect(analyser);
        
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        
        const updateLevel = () => {
            analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
            setLocalLevel(Math.min(100, (average / 128) * 100));
            requestAnimationFrame(updateLevel);
        };
        
        updateLevel();
        
        return () => {
            audioContext.close();
        };
    }, [localAudioTrack]);

    useEffect(() => {
        if (!botAudioTrack) return;
        
        const audioContext = new AudioContext();
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        
        const source = audioContext.createMediaStreamSource(
            new MediaStream([botAudioTrack])
        );
        source.connect(analyser);
        
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        
        const updateLevel = () => {
            analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
            setBotLevel(Math.min(100, (average / 128) * 100));
            requestAnimationFrame(updateLevel);
        };
        
        updateLevel();
        
        return () => {
            audioContext.close();
        };
    }, [botAudioTrack]);

    return (
        <div className="media-tracks-container">
            <div className="tracks-header">
                <span className="tracks-icon">🎚️</span>
                <span className="tracks-title">Audio Tracks</span>
            </div>
            
            <div className="tracks-grid">
                {/* Local Audio Track */}
                <div className={`track-card ${localAudioTrack ? 'active' : 'inactive'}`}>
                    <div className="track-header">
                        <div className="track-indicator local"></div>
                        <span className="track-name">Your Audio</span>
                        <span className={`track-status ${localAudioTrack ? 'on' : 'off'}`}>
                            {localAudioTrack ? 'LIVE' : 'OFF'}
                        </span>
                    </div>
                    
                    <div className="track-details">
                        <div className="track-info-row">
                            <span className="info-label">Track ID</span>
                            <span className="info-value">
                                {localAudioTrack?.id?.slice(0, 12) || '—'}...
                            </span>
                        </div>
                        <div className="track-info-row">
                            <span className="info-label">Enabled</span>
                            <span className="info-value">
                                {localAudioTrack?.enabled ? '✓ Yes' : '✗ No'}
                            </span>
                        </div>
                        <div className="track-info-row">
                            <span className="info-label">Muted</span>
                            <span className="info-value">
                                {localAudioTrack?.muted ? 'Yes' : 'No'}
                            </span>
                        </div>
                    </div>

                    {/* Audio Level Meter */}
                    <div className="level-meter-container">
                        <div className="level-meter">
                            <div 
                                className="level-bar local" 
                                style={{ width: `${localAudioTrack ? localLevel : 0}%` }}
                            ></div>
                        </div>
                        <span className="level-value">{Math.round(localLevel)}%</span>
                    </div>
                </div>

                {/* Bot Audio Track */}
                <div className={`track-card ${botAudioTrack ? 'active' : 'inactive'}`}>
                    <div className="track-header">
                        <div className="track-indicator bot"></div>
                        <span className="track-name">AI Audio</span>
                        <span className={`track-status ${botAudioTrack ? 'on' : 'off'}`}>
                            {botAudioTrack ? 'LIVE' : 'OFF'}
                        </span>
                    </div>
                    
                    <div className="track-details">
                        <div className="track-info-row">
                            <span className="info-label">Track ID</span>
                            <span className="info-value">
                                {botAudioTrack?.id?.slice(0, 12) || '—'}...
                            </span>
                        </div>
                        <div className="track-info-row">
                            <span className="info-label">Enabled</span>
                            <span className="info-value">
                                {botAudioTrack?.enabled ? '✓ Yes' : '✗ No'}
                            </span>
                        </div>
                        <div className="track-info-row">
                            <span className="info-label">Muted</span>
                            <span className="info-value">
                                {botAudioTrack?.muted ? 'Yes' : 'No'}
                            </span>
                        </div>
                    </div>

                    {/* Audio Level Meter */}
                    <div className="level-meter-container">
                        <div className="level-meter">
                            <div 
                                className="level-bar bot" 
                                style={{ width: `${botAudioTrack ? botLevel : 0}%` }}
                            ></div>
                        </div>
                        <span className="level-value">{Math.round(botLevel)}%</span>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default MediaTracks;
