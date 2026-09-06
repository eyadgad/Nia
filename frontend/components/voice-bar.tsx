import type { VoiceUiState } from "@/lib/voice";

type VoiceBarProps = {
  state: VoiceUiState;
  muted: boolean;
  level: number;
  error: string | null;
  onMute: () => void;
  onInterrupt: () => void;
  onDisconnect: () => void;
};

export function VoiceBar({ state, muted, level, error, onMute, onInterrupt, onDisconnect }: VoiceBarProps) {
  const speaking = state === "User speaking" || state === "Assistant speaking";
  const canInterrupt = state === "Assistant speaking" || state === "Processing";
  const bars = Array.from({ length: 7 }, (_, index) => {
    const idle = 0.12 + (index % 3) * 0.04;
    const active = speaking ? Math.max(level, 0.35 + (index % 4) * 0.12) : idle;
    return Math.max(4, Math.min(21, Math.round(active * 24)));
  });

  return (
    <div className="nia-voice-session">
      <div className="nia-voice-session-main">
        <div className="nia-voice-wave" aria-hidden="true">
          {bars.map((height, index) => (
            <span
              key={index}
              style={{ height: `${height}px`, opacity: muted ? 0.28 : 0.92 }}
            />
          ))}
        </div>
        <div className="nia-voice-copy">
          <strong>{state}</strong>
          <small>{error || (muted ? "Microphone muted" : "Voice session is active")}</small>
        </div>
      </div>
      <div className="nia-voice-actions">
        <button type="button" onClick={onMute}>{muted ? "Unmute" : "Mute"}</button>
        <button type="button" onClick={onInterrupt} disabled={!canInterrupt}>Interrupt</button>
        <button type="button" onClick={onDisconnect}>End</button>
      </div>
    </div>
  );
}
