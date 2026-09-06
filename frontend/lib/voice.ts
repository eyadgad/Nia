import type { LivekitToken } from "@/lib/api";

const VOICE_INPUT_PREROLL_MS = 600;

export type VoiceUiState =
  | "Disconnected"
  | "Connecting"
  | "Ready"
  | "Listening"
  | "User speaking"
  | "Processing"
  | "Assistant speaking"
  | "Interrupted"
  | "Reconnecting"
  | "Error";

export type VoiceMessage = {
  type:
    | "voice_state"
    | "voice_preference"
    | "assistant_reply"
    | "transcript"
    | "assistant_delta"
    | "citation";
  state?: VoiceUiState;
  status?: "partial" | "final";
  text?: string;
  conversation_id?: string | null;
  citations?: string[];
  evidence?: Array<{ source_id: string; fields?: Record<string, unknown> }>;
  source_id?: string;
  fields?: Record<string, unknown>;
  interrupted?: boolean;
  preference?: VoicePreference;
};

export type VoicePreference = "male" | "female";

export type VoiceSession = {
  disconnect: () => Promise<void>;
  setMuted: (muted: boolean) => Promise<void>;
  interrupt: () => Promise<void>;
  setVoice: (preference: VoicePreference, greet?: boolean) => Promise<void>;
  isMuted: () => boolean;
};

type VoiceHandlers = {
  onState: (state: VoiceUiState) => void;
  onMessage: (message: VoiceMessage) => void;
  onError: (message: string) => void;
  onLevel?: (level: number) => void;
};

export async function connectVoice(details: LivekitToken, handlers: VoiceHandlers): Promise<VoiceSession> {
  const { ConnectionState, Room, RoomEvent, Track } = await import("livekit-client");
  const room = new Room({
    adaptiveStream: true,
    dynacast: true,
    audioCaptureDefaults: { autoGainControl: true, echoCancellation: true, noiseSuppression: true },
  });
  let lastLocalSpeaking = false;
  let microphoneSubscribed = false;
  let microphoneReady = false;
  let resolveMicrophoneSubscribed: (() => void) | null = null;
  const microphoneSubscription = new Promise<void>((resolve) => {
    resolveMicrophoneSubscribed = resolve;
  });
  const attached = new Set<HTMLMediaElement>();

  const setState = (state: VoiceUiState) => handlers.onState(state);

  const attachAudio = (track: { kind?: string; attach: () => HTMLMediaElement }) => {
    if (track.kind && track.kind !== Track.Kind.Audio) return;
    const el = track.attach();
    el.autoplay = true;
    el.setAttribute("playsinline", "true");
    el.style.display = "none";
    document.body.appendChild(el);
    attached.add(el);
    void el.play().catch(() => undefined);
  };

  const detachAudio = () => {
    for (const el of attached) {
      el.pause();
      el.remove();
    }
    attached.clear();
  };

  room.on(RoomEvent.ConnectionStateChanged, (state) => {
    if (state === ConnectionState.Connecting) {
      setState("Connecting");
    } else if (state === ConnectionState.Connected) {
      setState(microphoneReady ? "Listening" : "Connecting");
    } else if (state === ConnectionState.Reconnecting) {
      microphoneSubscribed = false;
      microphoneReady = false;
      setState("Reconnecting");
    } else if (state === ConnectionState.Disconnected) {
      setState("Disconnected");
    }
  });

  room.on(RoomEvent.TrackSubscribed, (track) => {
    attachAudio(track);
  });

  room.on(RoomEvent.LocalTrackSubscribed, (publication) => {
    if (publication.kind !== Track.Kind.Audio) return;
    if (microphoneSubscribed) return;
    microphoneSubscribed = true;
    window.setTimeout(() => {
      microphoneReady = true;
      resolveMicrophoneSubscribed?.();
      resolveMicrophoneSubscribed = null;
      setState("Ready");
      setState("Listening");
    }, VOICE_INPUT_PREROLL_MS);
  });

  room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
    const localId = room.localParticipant.identity;
    const localSpeaking = speakers.some((speaker) => speaker.identity === localId);
    const remoteSpeaking = speakers.some((speaker) => speaker.identity !== localId);
    if (localSpeaking && lastLocalSpeaking === false && remoteSpeaking) {
      setState("Interrupted");
    } else if (localSpeaking) {
      setState("User speaking");
      if (!lastLocalSpeaking) {
        handlers.onMessage({ type: "transcript", status: "partial", text: "Hearing you…" });
      }
    } else if (remoteSpeaking) {
      setState("Assistant speaking");
    } else {
      if (lastLocalSpeaking) {
        handlers.onMessage({ type: "transcript", status: "partial", text: "Transcribing…" });
      }
      setState("Listening");
    }
    lastLocalSpeaking = localSpeaking;
  });

  room.on(RoomEvent.DataReceived, (payload) => {
    try {
      const message = JSON.parse(new TextDecoder().decode(payload)) as VoiceMessage;
      if (message.type === "voice_state" && message.state) {
        setState(message.state);
      }
      handlers.onMessage(message);
    } catch {
      handlers.onError("Could not read a voice event.");
    }
  });

  room.on(RoomEvent.Disconnected, () => {
    detachAudio();
    setState("Disconnected");
  });

  await room.connect(details.server_url, details.participant_token);
  try {
    await room.startAudio();
  } catch {
    handlers.onError("Click the page once if you cannot hear NIA — the browser blocked audio playback.");
  }
  await room.localParticipant.setMicrophoneEnabled(true);
  await waitForVoiceInput(microphoneSubscription, 20_000);
  for (const participant of room.remoteParticipants.values()) {
    for (const publication of participant.audioTrackPublications.values()) {
      if (publication.track) attachAudio(publication.track);
    }
  }
  setState("Listening");
  const stopMeter = startLevelMeter(room, handlers.onLevel);

  return {
    async disconnect() {
      stopMeter();
      detachAudio();
      await room.disconnect();
      setState("Disconnected");
    },
    async setMuted(muted: boolean) {
      await room.localParticipant.setMicrophoneEnabled(!muted);
    },
    async interrupt() {
      await room.localParticipant.publishData(
        new TextEncoder().encode(JSON.stringify({ type: "interrupt" })),
        { reliable: true }
      );
    },
    async setVoice(preference: VoicePreference, greet = true) {
      await room.localParticipant.publishData(
        new TextEncoder().encode(JSON.stringify({ type: "set_voice", preference, greet })),
        { reliable: true }
      );
    },
    isMuted() {
      return room.localParticipant.isMicrophoneEnabled === false;
    },
  };
}

export function requestedVoicePreference(text: string): VoicePreference | null {
  const gender =
    text.match(
      /\b(?:switch|change|set|use|select|choose|prefer|speak|talk|sound|make)\b.{0,36}?\b(female|woman(?:['’]s)?|woman|lady|male|man(?:['’]s)?|man)\b(?:\s+voice)?/i
    )?.[1] ??
    text.match(
      /^\s*(?:please\s+)?(?:use\s+)?(?:a\s+)?(female|woman(?:['’]s)?|woman|lady|male|man(?:['’]s)?|man)(?:\s+voice)?(?:\s+please)?[.!?]*\s*$/i
    )?.[1];
  if (!gender) return null;
  return /^[fwl]/i.test(gender) ? "female" : "male";
}

async function waitForVoiceInput(subscription: Promise<void>, timeoutMs: number): Promise<void> {
  let timeout: number | undefined;
  try {
    await Promise.race([
      subscription,
      new Promise<never>((_resolve, reject) => {
        timeout = window.setTimeout(
          () => reject(new Error("Voice agent did not subscribe to the microphone in time.")),
          timeoutMs
        );
      }),
    ]);
  } finally {
    if (timeout !== undefined) window.clearTimeout(timeout);
  }
}

function startLevelMeter(room: { localParticipant: { audioTrackPublications?: Map<unknown, { audioTrack?: { mediaStream?: MediaStream } }> } }, onLevel?: (level: number) => void) {
  if (!onLevel || typeof window === "undefined") {
    return () => undefined;
  }
  let frame = 0;
  let ctx: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  const data = new Uint8Array(16);
  const tick = () => {
    if (analyser) {
      analyser.getByteFrequencyData(data);
      const avg = data.reduce((sum, value) => sum + value, 0) / (data.length || 1) / 255;
      onLevel(avg);
    }
    frame = window.requestAnimationFrame(tick);
  };
  try {
    const publications = room.localParticipant.audioTrackPublications;
    const publication = publications ? [...publications.values()][0] : undefined;
    const stream = publication?.audioTrack?.mediaStream;
    if (stream) {
      ctx = new AudioContext();
      analyser = ctx.createAnalyser();
      analyser.fftSize = 32;
      ctx.createMediaStreamSource(stream).connect(analyser);
    }
  } catch {
    /* analyser is optional; UI falls back to state animation */
  }
  frame = window.requestAnimationFrame(tick);
  return () => {
    window.cancelAnimationFrame(frame);
    void ctx?.close();
  };
}
