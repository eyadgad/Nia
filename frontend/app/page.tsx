"use client";

import { ChangeEvent, FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AuthExpiredError,
  ConversationSummary,
  ConversationTurn,
  Dataset,
  QueryListResult,
  Session,
  fetchConversation,
  apiTargetIsUnreachable,
  deleteConversation,
  submitFeedback,
  fetchConversations,
  fetchDatasets,
  type ModelChoice,
  fetchLivekitToken,
  fetchSession,
  health,
  login,
  logout,
  streamQuery,
} from "@/lib/api";
import { VoiceBar } from "@/components/voice-bar";
import {
  VoiceMessage,
  VoicePreference,
  VoiceSession,
  VoiceUiState,
  connectVoice,
  requestedVoicePreference,
} from "@/lib/voice";

type ChatLine = {
  id: string;
  role: "system" | "user" | "assistant";
  text: string;
  citations?: string[];
  evidence?: Array<{ source_id: string; fields?: Record<string, unknown> }>;
  streaming?: boolean;
  progress?: string;
  partial?: boolean;
  mode?: string;
  interrupted?: boolean;
  listResults?: QueryListResult[];
  errorCode?: string | null;
  suggestedFileId?: number | null;
};

// Shown on the sign-in screen while this is a testing build. They live in the environment,
// not in the repository: published login defaults were scrubbed from this project's history
// once already. Unset means the block simply does not render.
const TEST_USERNAME = process.env.NEXT_PUBLIC_TEST_USERNAME || "";
const TEST_PASSWORD = process.env.NEXT_PUBLIC_TEST_PASSWORD || "";

const CONV_KEY = "nia.standalone.conversation";
const VOICE_PREF_KEY = "nia.standalone.voice-preference";
// Persisted like the voice preference: a per-researcher choice, not conversation state.
const MODEL_PREF_KEY = "nia.standalone.model";
const PARTIAL_ID = "voice-partial";
const VOICE_ASSISTANT_ID = "voice-assistant";

export default function HomePage() {
  const [session, setSession] = useState<Session | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [apiReady, setApiReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [models, setModels] = useState<ModelChoice[]>([]);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [legacyUnscoped, setLegacyUnscoped] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceUiState>("Disconnected");
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [voiceMuted, setVoiceMuted] = useState(false);
  const [voiceLevel, setVoiceLevel] = useState(0);
  const [selectedCitation, setSelectedCitation] = useState<{
    source_id: string;
    fields?: Record<string, unknown>;
  } | null>(null);
  const [lines, setLines] = useState<ChatLine[]>([welcomeLine()]);
  const voiceSession = useRef<VoiceSession | null>(null);
  const previousVoiceState = useRef<VoiceUiState>("Disconnected");
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    // Resolved in the browser, not at build time: the answer depends on where the page was
    // served from, and the server rendering it cannot know.
    const unreachable = apiTargetIsUnreachable();
    setApiUnreachable(unreachable);
    if (unreachable) {
      // No health call: it would be the local-network request this exists to prevent.
      setApiReady(false);
    } else {
      health()
        .then(() => setApiReady(true))
        .catch(() => setApiReady(false));
    }
    // Always, whatever the outcome above. restoreSession owns `hydrated` in its finally, and
    // returning early from this effect left it false forever -- the deployed build sat on
    // "Opening the research desk…" instead of reaching the sign-in screen. When the API is
    // unreachable fetchSession throws before touching the network, which this already
    // handles as "no session".
    void restoreSession();
  }, []);

  useEffect(() => {
    if (!session) return;
    fetchDatasets()
      .then(({ datasets: items, models: available }) => {
        setDatasets(items);
        setSelectedFileId((current) =>
          current && items.some((item) => item.file_id === current)
            ? current
            : defaultDatasetId(items)
        );
        setModels(available);
        // A remembered model is honoured only while the backend still offers it.
        const stored = window.localStorage.getItem(MODEL_PREF_KEY);
        const fallback = available.find((item) => item.selected)?.id ?? available[0]?.id ?? null;
        setSelectedModel(
          stored && available.some((item) => item.id === stored) ? stored : fallback
        );
      })
      .catch((err: Error) => {
        if (err instanceof AuthExpiredError) {
          expireSession();
          return;
        }
        setError(err.message);
      });
    void refreshConversations();
    const storedConversation = window.localStorage.getItem(CONV_KEY);
    if (storedConversation) void restoreConversation(storedConversation);
  }, [session]);

  useEffect(() => {
    if (conversationId) window.localStorage.setItem(CONV_KEY, conversationId);
    else window.localStorage.removeItem(CONV_KEY);
  }, [conversationId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines, voiceState]);

  useEffect(() => {
    return () => {
      void voiceSession.current?.disconnect();
      voiceSession.current = null;
    };
  }, []);

  const authorizedLabel = useMemo(() => {
    if (!datasets.length) return session ? "No authorized datasets" : "Not signed in";
    return datasets.map((item) => item.user_facing_label).join(" · ");
  }, [datasets, session]);
  const activeDataset = useMemo(
    () => datasets.find((item) => item.file_id === selectedFileId) ?? null,
    [datasets, selectedFileId]
  );
  // The backend already filters /api/assistant/datasets by AccessScope and
  // access_grants, so every dataset returned here is one this principal is
  // authorized to query. Filtering by `private` again would hide granted
  // restricted lists (93 Additional Deaths, 94 Potential) from the picker.
  const selectableDatasets = datasets;

  async function restoreSession() {
    try {
      const next = await fetchSession();
      setSession(next);
    } catch {
      window.localStorage.removeItem(CONV_KEY);
      setSession(null);
    } finally {
      setHydrated(true);
    }
  }

  function expireSession(message = "Your session expired. Sign in again.") {
    signOut();
    setError(message);
  }

  async function refreshConversations() {
    try {
      const remote = await fetchConversations();
      setConversations((current) => {
        const optimistic = new Map(current.map((item) => [item.id, item]));
        return remote.map((item) => {
          const prior = optimistic.get(item.id);
          if (!prior) return item;
          return {
            ...item,
            title: item.title || prior.title,
          };
        });
      });
    } catch (err) {
      if (err instanceof AuthExpiredError) {
        expireSession();
      }
    }
  }

  async function onLogin(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const next = await login(username, password);
      setSession(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    }
  }

  function signOut() {
    void voiceSession.current?.disconnect();
    void logout();
    voiceSession.current = null;
    window.localStorage.removeItem(CONV_KEY);
    setSession(null);
    setDatasets([]);
    setConversations([]);
    setConversationId(null);
    setSelectedFileId(null);
    setLegacyUnscoped(false);
    setVoiceState("Disconnected");
    setVoiceMuted(false);
    setSidebarOpen(false);
    setLines([welcomeLine()]);
  }

  function startNewConversation() {
    void voiceSession.current?.disconnect();
    voiceSession.current = null;
    setVoiceState("Disconnected");
    setConversationId(null);
    setSelectedFileId(defaultDatasetId(datasets));
    setLegacyUnscoped(false);
    setSelectedCitation(null);
    setSidebarOpen(false);
    setLines([welcomeLine()]);
    window.setTimeout(() => composerRef.current?.focus(), 0);
  }

  async function removeConversation(id: string, label: string) {
    if (busy) return;
    if (!window.confirm(`Delete "${label}"? This cannot be undone.`)) return;
    const wasActive = id === conversationId;
    const previous = conversations;
    // Drop the row first so the sidebar answers the click, and put it back if the
    // server disagrees -- a chat that silently reappears on the next refresh is worse
    // than one that never left.
    setConversations((current) => current.filter((item) => item.id !== id));
    try {
      await deleteConversation(id);
    } catch (err) {
      setConversations(previous);
      setError(err instanceof Error ? err.message : "Could not delete that conversation.");
      return;
    }
    if (wasActive) startNewConversation();
  }

  async function openConversation(id: string) {
    if (!session) return;
    try {
      const detail = await fetchConversation(id);
      setConversationId(id);
      setSelectedFileId(detail.selected_file_id ?? defaultDatasetId(datasets));
      setLegacyUnscoped(detail.legacy_unscoped);
      setSelectedCitation(null);
      setSidebarOpen(false);
      setLines([welcomeLine(), ...detail.turns.map(turnToLine)]);
    } catch (err) {
      if (err instanceof AuthExpiredError) {
        expireSession();
        return;
      }
      setError(err instanceof Error ? err.message : "Could not open that conversation.");
    }
  }

  async function restoreConversation(id: string) {
    try {
      const detail = await fetchConversation(id);
      setConversationId(id);
      setSelectedFileId(detail.selected_file_id ?? defaultDatasetId(datasets));
      setLegacyUnscoped(detail.legacy_unscoped);
      setLines([welcomeLine(), ...detail.turns.map(turnToLine)]);
    } catch (err) {
      window.localStorage.removeItem(CONV_KEY);
      if (err instanceof AuthExpiredError) {
        expireSession();
      }
    }
  }

  async function toggleVoice() {
    if (!session) return;
    if (voiceState !== "Disconnected" && voiceState !== "Error") {
      await voiceSession.current?.disconnect();
      voiceSession.current = null;
      setVoiceState("Disconnected");
      setVoiceError(null);
      return;
    }
    await connectVoiceSession();
  }

  async function connectVoiceSession(): Promise<VoiceSession | null> {
    if (!selectedFileId) {
      setVoiceError("Select a list before starting voice.");
      return null;
    }
    const voiceConversationId = legacyUnscoped ? null : conversationId;
    if (legacyUnscoped) {
      setConversationId(null);
      setLegacyUnscoped(false);
      setLines([welcomeLine()]);
    }
    setVoiceState("Connecting");
    setVoiceError(null);
    setVoiceMuted(false);
    try {
      const details = await fetchLivekitToken(voiceConversationId, selectedFileId);
      if (!details.participant_token || !details.server_url) throw new Error("voice token missing");
      const connected = await connectVoice(details, {
        onState: (state) => {
          if (state === "Ready" && previousVoiceState.current === "Reconnecting") {
            const id = window.localStorage.getItem(CONV_KEY);
            if (id && session) {
              void restoreConversation(id);
              void refreshConversations();
            }
          }
          previousVoiceState.current = state;
          setVoiceState(state);
        },
        onMessage: (message) => applyVoiceMessage(message),
        onError: (message) => setVoiceError(message),
        onLevel: setVoiceLevel,
      });
      voiceSession.current = connected;
      const saved = (window.localStorage.getItem(VOICE_PREF_KEY) || "male") as VoicePreference;
      await connected.setVoice(saved === "female" ? "female" : "male", false);
      return connected;
    } catch (err) {
      if (err instanceof AuthExpiredError) {
        expireSession();
        return null;
      }
      voiceSession.current = null;
      setVoiceState("Error");
      setVoiceError(err instanceof Error ? err.message : "Voice connect failed");
      return null;
    }
  }

  function applyVoiceMessage(message: VoiceMessage) {
    if (message.type === "voice_preference" && message.preference) {
      window.localStorage.setItem(VOICE_PREF_KEY, message.preference);
      return;
    }

    if (message.type === "transcript" && message.text) {
      if (message.status === "partial") {
        setLines((current) =>
          upsertLine(current, {
            id: PARTIAL_ID,
            role: "user",
            text: message.text ?? "",
            partial: true,
            mode: "voice",
          })
        );
        return;
      }
      setLines((current) => {
        const withoutPartial = current.filter((line) => line.id !== PARTIAL_ID);
        return [
          ...withoutPartial,
          { id: crypto.randomUUID(), role: "user", text: message.text ?? "", mode: "voice" },
        ];
      });
      return;
    }

    if (message.type === "assistant_delta" && message.text) {
      setLines((current) => {
        const existing = current.find((line) => line.id === VOICE_ASSISTANT_ID);
        return upsertLine(current, {
          id: VOICE_ASSISTANT_ID,
          role: "assistant",
          text: `${existing?.text ?? ""}${existing?.text ? " " : ""}${message.text ?? ""}`.trim(),
          streaming: true,
          mode: "voice",
          citations: existing?.citations,
          evidence: existing?.evidence,
        });
      });
      return;
    }

    if (message.type === "citation" && message.source_id) {
      setLines((current) =>
        current.map((line) =>
          line.id === VOICE_ASSISTANT_ID || (line.role === "assistant" && line.streaming)
            ? {
                ...line,
                citations: [...new Set([...(line.citations ?? []), message.source_id ?? ""])],
                evidence: [
                  ...(line.evidence ?? []).filter((item) => item.source_id !== message.source_id),
                  { source_id: message.source_id ?? "", fields: message.fields },
                ],
              }
            : line
        )
      );
      return;
    }

    if (message.type === "assistant_reply" && message.text) {
      if (message.conversation_id) setConversationId(message.conversation_id);
      setLines((current) => {
        const withoutLive = current.filter(
          (line) => line.id !== VOICE_ASSISTANT_ID && line.id !== PARTIAL_ID
        );
        return [
          ...withoutLive,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            text: message.text ?? "",
            citations: message.citations,
            evidence: message.evidence,
            mode: "voice",
            interrupted: message.interrupted,
          },
        ];
      });
      if (session) void refreshConversations();
    }
  }

  async function toggleMute() {
    const next = !voiceMuted;
    await voiceSession.current?.setMuted(next);
    setVoiceMuted(next);
  }

  async function interruptVoice() {
    await voiceSession.current?.interrupt();
    setVoiceState("Interrupted");
  }

  async function sendQuestion(event?: FormEvent) {
    event?.preventDefault();
    const text = question.trim();
    if (!text || !session || busy || !selectedFileId) return;
    const effectiveConversationId = legacyUnscoped ? null : conversationId;
    if (legacyUnscoped) {
      setConversationId(null);
      setLegacyUnscoped(false);
    }

    const voicePreference = requestedVoicePreference(text);
    if (voicePreference) {
      setLines((current) => [
        ...(legacyUnscoped ? [welcomeLine()] : current),
        { id: crypto.randomUUID(), role: "user", text },
      ]);
      setQuestion("");
      if (composerRef.current) composerRef.current.style.height = "auto";
      setError(null);
      setBusy(true);
      window.localStorage.setItem(VOICE_PREF_KEY, voicePreference);
      try {
        const active = voiceSession.current ?? (await connectVoiceSession());
        if (!active) throw new Error("Could not start a voice session.");
        await active.setVoice(voicePreference, true);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not switch the voice.");
      } finally {
        setBusy(false);
      }
      return;
    }

    const assistantId = crypto.randomUUID();
    setLines((current) => [
      ...(legacyUnscoped ? [welcomeLine()] : current),
      { id: crypto.randomUUID(), role: "user", text },
      { id: assistantId, role: "assistant", text: "", streaming: true },
    ]);
    setQuestion("");
    if (composerRef.current) composerRef.current.style.height = "auto";
    setError(null);
    setBusy(true);

    try {
      const result = await streamQuery(
        text,
        effectiveConversationId,
        selectedFileId,
        (event) => {
        if (event.event === "plan_started") {
          setLines((current) => updateLineProgress(current, assistantId, "Understanding your request..."));
        }
        if (event.event === "plan_validated") {
          setLines((current) => updateLineProgress(current, assistantId, "Checking authorized records..."));
        }
        if (event.event === "retrieval_completed" || event.event === "computed_fact") {
          setLines((current) => updateLineProgress(current, assistantId, "Preparing the answer..."));
        }
        if (event.event === "answer_delta") {
          setLines((current) =>
            current.map((line) =>
              line.id === assistantId
                ? { ...line, text: `${line.text}${event.data.text}`, progress: undefined }
                : line
            )
          );
        }
        if (event.event === "citation") {
          setLines((current) =>
            current.map((line) =>
              line.id === assistantId
                ? {
                    ...line,
                    citations: [...new Set([...(line.citations ?? []), event.data.source_id])],
                    evidence: [
                      ...(line.evidence ?? []).filter((item) => item.source_id !== event.data.source_id),
                      { source_id: event.data.source_id, fields: event.data.fields },
                    ],
                  }
                : line
            )
          );
        }
        },
        selectedModel
      );

      if (result.conversation_id) setConversationId(result.conversation_id);
      if (result.selected_file_id) setSelectedFileId(result.selected_file_id);
      setLines((current) =>
        current.map((line) =>
          line.id === assistantId
            ? {
                ...line,
                text: result.answer || line.text,
                citations: result.citations ?? line.citations,
                evidence: result.evidence ?? line.evidence,
                listResults: result.list_results,
                streaming: false,
                progress: undefined,
                errorCode: result.error_code,
                suggestedFileId: result.suggested_file_id,
              }
            : line
        )
      );
      const conversationId = result.conversation_id;
      if (conversationId) {
        const preview = (result.answer || text).slice(0, 80);
        setConversations((current) => {
          const existing = current.find((item) => item.id === conversationId);
          const optimistic: ConversationSummary = {
            id: conversationId,
            title: existing?.title ?? null,
            active_frame_key: existing?.active_frame_key ?? null,
            preview,
            turn_count: (existing?.turn_count ?? 0) + 1,
            selected_file_id: result.selected_file_id ?? existing?.selected_file_id ?? null,
            selected_dataset_label: existing?.selected_dataset_label ?? null,
            legacy_unscoped: existing?.legacy_unscoped ?? false,
          };
          const rest = current.filter((item) => item.id !== conversationId);
          return [optimistic, ...rest];
        });
      }
      void refreshConversations().catch((err) => {
        console.warn("conversation list refresh failed", err);
      });
    } catch (err) {
      if (err instanceof AuthExpiredError) {
        expireSession();
        return;
      }
      setError(err instanceof Error ? err.message : "Ask failed");
      setLines((current) => current.filter((line) => line.id !== assistantId));
    } finally {
      setBusy(false);
      window.setTimeout(() => composerRef.current?.focus(), 0);
    }
  }

  function onQuestionChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setQuestion(event.target.value);
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 160)}px`;
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion();
    }
  }

  const [apiUnreachable, setApiUnreachable] = useState(false);
  const [copied, setCopied] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportName, setReportName] = useState("");
  const [reportComment, setReportComment] = useState("");
  const [reportSending, setReportSending] = useState(false);
  const [reportSent, setReportSent] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  async function sendReport(event: FormEvent) {
    event.preventDefault();
    const comment = reportComment.trim();
    if (!comment || reportSending) return;
    setReportSending(true);
    setReportError(null);
    try {
      await submitFeedback({
        comment,
        reporterName: reportName.trim(),
        conversationId,
      });
      setReportSent(true);
      setReportComment("");
    } catch (err) {
      setReportError(err instanceof Error ? err.message : "Could not send that report.");
    } finally {
      setReportSending(false);
    }
  }

  function closeReport() {
    setReportOpen(false);
    setReportError(null);
    setReportSent(false);
  }
  const visibleLines = lines.filter((line) => line.role !== "system");
  const isEmptyConversation = visibleLines.length === 0;
  const activeConversationTitle =
    conversations.find((item) => item.id === conversationId)?.title || "New chat";

  // A conversation is worth copying as readable text: role labels, answer
  // text, structured rows, and the citations that back them.
  function conversationToText(): string {
    const NL = String.fromCharCode(10);
    const header = [
      activeConversationTitle,
      activeDataset?.user_facing_label
        ? `Research list: ${activeDataset.user_facing_label}`
        : null,
      new Date().toLocaleString(),
    ]
      .filter(Boolean)
      .join(NL);

    const body = visibleLines.map((line) => {
      const who = line.role === "user" ? "You" : "NIA";
      const parts: string[] = [];

      if (line.text) parts.push(line.text);

      // Structured results are part of the answer, so copy them as a table
      // instead of losing them with the rendered-only component.
      line.listResults?.forEach((result) => {
        const cols = result.fields.map((f) => f.label);
        parts.push(
          [result.dataset_label, cols.join(" | ")].filter(Boolean).join(NL)
        );
        result.rows.forEach((row, index) => {
          const cells = result.fields.map((f) => {
            const value = row.values?.[f.name];
            return value === null || value === undefined || value === ""
              ? "-"
              : String(value);
          });
          parts.push(`${result.offset + index + 1}. ${cells.join(" | ")}`);
        });
        if (result.total_count > result.rows.length) {
          parts.push(
            `(showing ${result.rows.length} of ${result.total_count})`
          );
        }
      });

      if (line.citations?.length) {
        parts.push(`Sources: ${line.citations.join(", ")}`);
      }

      return `${who}:` + NL + (parts.join(NL) || "(no content)");
    });

    return [header, ...body].join(NL + NL).trim() + NL;
  }

  async function copyConversation() {
    const text = conversationToText();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // The async clipboard needs a secure context and permission. Fall back
      // so the button still works over plain http or when permission is
      // denied, rather than silently doing nothing.
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(area);
      }
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  function switchModel(model: string) {
    if (busy || model === selectedModel) return;
    // Unlike a dataset switch this keeps the conversation: which model answers is a
    // preference, not a change of what is being asked about.
    setSelectedModel(model);
    window.localStorage.setItem(MODEL_PREF_KEY, model);
  }

  function switchDataset(fileId: number) {
    if (busy || fileId === selectedFileId) return;
    void voiceSession.current?.disconnect();
    voiceSession.current = null;
    setVoiceState("Disconnected");
    setVoiceError(null);
    setSelectedFileId(fileId);
    setConversationId(null);
    setLegacyUnscoped(false);
    setSelectedCitation(null);
    setLines([welcomeLine()]);
    setError(null);
    window.setTimeout(() => composerRef.current?.focus(), 0);
  }

  function useSuggestion(text: string) {
    setQuestion(text);
    window.setTimeout(() => {
      composerRef.current?.focus();
      if (composerRef.current) {
        composerRef.current.style.height = "auto";
        composerRef.current.style.height = `${Math.min(composerRef.current.scrollHeight, 160)}px`;
      }
    }, 0);
  }

  if (!hydrated) {
    return (
      <main className="nia-stage nia-stage-loading">
        <div className="nia-loading-mark"><NiaGlyph /></div>
        <span>Opening the research desk…</span>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="nia-stage nia-login-stage">
        <section className="nia-login-panel">
          <div className="nia-login-hero">
            <NiaMark />
            <div className="nia-login-hero-copy">
              <p className="nia-eyebrow">NIA</p>
              <h1>Still in testing.</h1>
              <div className="nia-login-brief">
                <p>This is still under development and testing. Help me test it.</p>
                {TEST_USERNAME && TEST_PASSWORD ? (
                  <>
                    <p>You can access the workspace with these credentials:</p>
                    <dl className="nia-login-creds">
                      <div>
                        <dt>Username</dt>
                        <dd>{TEST_USERNAME}</dd>
                      </div>
                      <div>
                        <dt>Password</dt>
                        <dd>{TEST_PASSWORD}</dd>
                      </div>
                    </dl>
                  </>
                ) : null}
                <p>The goal is to find bugs, and inappropriate or inaccurate answers.</p>
                <p>
                  If you find any, at the end of your conversation click{" "}
                  <strong>Report</strong> at the top, write your name and any comments, and
                  submit.
                </p>
              </div>
            </div>
            <div className="nia-login-hero-foot">Testing build</div>
          </div>
          <div className="nia-login-card">
            <div className="nia-login-brand">
              <NiaMark />
              <div>
                <strong>NIA</strong>
                <span>Research assistant</span>
              </div>
            </div>
            <div className="nia-login-copy">
              <h1>Sign in</h1>
            </div>
            <form onSubmit={onLogin} className="nia-login-form">
              <label>
                <span>Username</span>
                <input
                  className="nia-field"
                  value={username}
                  autoComplete="username"
                  onChange={(event) => setUsername(event.target.value)}
                />
              </label>
              <label>
                <span>Password</span>
                <input
                  type="password"
                  className="nia-field"
                  value={password}
                  autoComplete="current-password"
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              {error ? <p className="nia-form-error">{error}</p> : null}
              <button type="submit" className="nia-primary-button">Enter workspace</button>
            </form>
            {apiUnreachable ? (
              <p className="nia-login-notice">
                This build has no backend configured yet, so sign-in will not work here. It
                runs against a local stack for now.
              </p>
            ) : (
              <div className="nia-login-status">
                <span className={`nia-status-dot ${apiReady ? "is-ready" : "is-offline"}`} />
                API {apiReady ? "connected" : "offline"}
              </div>
            )}
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="nia-stage">
      <div className="nia-shell">
        {sidebarOpen ? (
          <button
            type="button"
            aria-label="Close sidebar"
            className="nia-sidebar-scrim"
            onClick={() => setSidebarOpen(false)}
          />
        ) : null}

        <aside
          className={`nia-sidebar ${sidebarCollapsed ? "is-collapsed" : ""} ${sidebarOpen ? "is-open" : ""}`}
        >
          <div className="nia-sidebar-head">
            <button
              type="button"
              className="nia-brand-button"
              onClick={() => sidebarCollapsed && setSidebarCollapsed(false)}
              title={sidebarCollapsed ? "Expand sidebar" : "NIA"}
            >
              <NiaMark compact={sidebarCollapsed} />
              <span className="nia-sidebar-label">NIA</span>
            </button>
            <button
              type="button"
              className="nia-icon-button nia-desktop-collapse"
              onClick={() => setSidebarCollapsed((value) => !value)}
              aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <PanelIcon collapsed={sidebarCollapsed} />
            </button>
            <button
              type="button"
              className="nia-icon-button nia-mobile-close"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close sidebar"
            >
              <CloseIcon />
            </button>
          </div>

          <div className="nia-sidebar-action-wrap">
            <button
              type="button"
              onClick={startNewConversation}
              className="nia-new-chat-button"
              title="New chat"
            >
              <ComposeIcon />
              <span className="nia-sidebar-label">New chat</span>
            </button>
          </div>

          <div className="nia-history">
            <div className="nia-history-title nia-sidebar-label">Chats</div>
            <ul>
              {conversations.length ? (
                conversations.map((item) => (
                  <li key={item.id} className="nia-history-row">
                    <button
                      type="button"
                      onClick={() => void openConversation(item.id)}
                      className={`nia-history-item ${item.id === conversationId ? "is-active" : ""}`}
                      title={item.title || item.preview || "Untitled conversation"}
                    >
                      <span className="nia-history-dot" />
                      <span className="nia-history-text nia-sidebar-label">
                        <strong>{item.title || "Untitled conversation"}</strong>
                        <small>{item.preview}</small>
                      </span>
                    </button>
                    <button
                      type="button"
                      className="nia-history-delete nia-sidebar-label"
                      onClick={() =>
                        void removeConversation(item.id, item.title || "Untitled conversation")
                      }
                      disabled={busy}
                      title="Delete this chat"
                      aria-label={`Delete ${item.title || "Untitled conversation"}`}
                    >
                      <TrashIcon />
                    </button>
                  </li>
                ))
              ) : (
                <li className="nia-history-empty nia-sidebar-label">Your conversations will appear here.</li>
              )}
            </ul>
          </div>

          <div className="nia-sidebar-footer">
            <details className="nia-account-menu">
              <summary className="nia-account-row" title="Account">
                <span className="nia-account-avatar">{initials(session.principal_id)}</span>
                <span className="nia-account-copy nia-sidebar-label">
                  <strong>Researcher</strong>
                  <small>{datasets.length} dataset{datasets.length === 1 ? "" : "s"} available</small>
                </span>
                <ChevronIcon />
              </summary>
              <div className="nia-account-popover">
                <p>{authorizedLabel}</p>
                <button type="button" onClick={signOut}>Sign out</button>
              </div>
            </details>
          </div>
        </aside>

        <section className="nia-main">
          <header className="nia-chat-header">
            <div className="nia-header-left">
              <button
                type="button"
                className="nia-icon-button nia-mobile-menu"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
              >
                <MenuIcon />
              </button>
              {sidebarCollapsed ? (
                <button
                  type="button"
                  className="nia-icon-button nia-collapsed-trigger"
                  onClick={() => setSidebarCollapsed(false)}
                  aria-label="Expand sidebar"
                >
                  <PanelIcon collapsed />
                </button>
              ) : null}
              <div className="nia-chat-title">
                <strong>{activeConversationTitle}</strong>
                <span>{activeDataset?.user_facing_label ?? "Select a research list"}</span>
              </div>
            </div>
            <div className="nia-header-actions">
              <div className="nia-dataset-toggle" role="group" aria-label="Research list">
                {selectableDatasets.map((dataset) => (
                  <button
                    key={dataset.file_id}
                    type="button"
                    aria-pressed={dataset.file_id === selectedFileId}
                    className={dataset.file_id === selectedFileId ? "is-selected" : ""}
                    disabled={busy}
                    onClick={() => switchDataset(dataset.file_id)}
                    title={`Use ${dataset.user_facing_label}` + (dataset.private ? " (restricted list - access granted to your account)" : "")}
                  >
                    <span className="nia-dataset-label-full">{shortDatasetLabel(dataset)}</span>
                    <span className="nia-dataset-label-compact">{compactDatasetLabel(dataset)}</span>
                  </button>
                ))}
              </div>
              {models.length > 1 && (
                <div className="nia-dataset-toggle" role="group" aria-label="Answer model">
                  {models.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      aria-pressed={option.id === selectedModel}
                      className={option.id === selectedModel ? "is-selected" : ""}
                      disabled={busy}
                      onClick={() => switchModel(option.id)}
                      title={modelHint(option.id)}
                    >
                      <span className="nia-dataset-label-full">{modelLabel(option.id)}</span>
                      <span className="nia-dataset-label-compact">{modelLabel(option.id)}</span>
                    </button>
                  ))}
                </div>
              )}
              <button
                type="button"
                onClick={() => setReportOpen(true)}
                className="nia-report-button"
                aria-label="Report a problem"
                title="Report a bug, or an inappropriate or inaccurate answer"
              >
                <FlagIcon />
                <span className="nia-report-label">Report</span>
              </button>
              <button
                type="button"
                onClick={() => void copyConversation()}
                className="nia-icon-button"
                disabled={isEmptyConversation}
                aria-label="Copy conversation"
                title={isEmptyConversation ? "Nothing to copy yet" : "Copy the whole chat"}
              >
                {copied ? <CheckIcon /> : <CopyIcon />}
              </button>
              <button
                type="button"
                onClick={() => void toggleVoice()}
                className={`nia-icon-button ${
                  voiceState !== "Disconnected" && voiceState !== "Error" ? "is-active" : ""
                }`}
                aria-label={voiceState === "Disconnected" || voiceState === "Error" ? "Start voice" : "Stop voice"}
                title={voiceState === "Disconnected" || voiceState === "Error" ? "Start voice" : "Stop voice"}
              >
                <VoiceIcon />
              </button>
            </div>
          </header>

          <section className={`nia-conversation ${isEmptyConversation ? "is-empty" : ""}`} aria-live="polite">
            {isEmptyConversation ? (
              <div className="nia-empty-state">
                <div className="nia-empty-mark"><NiaGlyph /></div>
                <p className="nia-eyebrow">Research desk</p>
                <h1>Ask about the records</h1>
                <p>NIA searches only the list this chat is using. Start with a count, a name, or what the list contains.</p>
                {activeDataset ? (
                  <div className="nia-empty-list">
                    Working in <strong>{activeDataset.user_facing_label}</strong>
                  </div>
                ) : null}
                <div className="nia-suggestions">
                  {(activeDataset?.starter_prompts?.length
                    ? activeDataset.starter_prompts
                    : starterPrompts(activeDataset?.user_facing_label)
                  ).map((prompt) => (
                    <button key={prompt.title} type="button" onClick={() => useSuggestion(prompt.prompt)}>
                      <span>{prompt.title}</span>
                      <small>{prompt.caption}</small>
                      <ArrowDiagonalIcon />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="nia-message-list">
                {visibleLines.map((line) => (
                  <ChatMessage
                    key={line.id}
                    line={line}
                    onCitation={(citation) => setSelectedCitation(citation)}
                    onDatasetSwitch={switchDataset}
                  />
                ))}
                <div ref={chatEndRef} className="nia-scroll-anchor" />
              </div>
            )}
          </section>

          <div className="nia-composer-dock">
            <div className="nia-composer-wrap">
              {voiceState !== "Disconnected" && voiceState !== "Error" ? (
                <VoiceBar
                  state={voiceState}
                  muted={voiceMuted}
                  level={voiceLevel}
                  error={voiceError}
                  onMute={() => void toggleMute()}
                  onInterrupt={() => void interruptVoice()}
                  onDisconnect={() => void toggleVoice()}
                />
              ) : voiceError ? (
                <div className="nia-voice-error">{voiceError}</div>
              ) : null}

              {error ? <div className="nia-inline-error">{error}</div> : null}

              <form onSubmit={(event) => void sendQuestion(event)} className="nia-composer">
                <textarea
                  ref={composerRef}
                  rows={1}
                  className="nia-composer-input"
                  placeholder="Ask about this list"
                  value={question}
                  onChange={onQuestionChange}
                  onKeyDown={onComposerKeyDown}
                  disabled={busy}
                />
                <div className="nia-composer-footer">
                  <div className="nia-composer-tools">
                    <button
                      type="button"
                      onClick={() => void toggleVoice()}
                      className={`nia-tool-button ${
                        voiceState !== "Disconnected" && voiceState !== "Error" ? "is-active" : ""
                      }`}
                      aria-label="Voice conversation"
                      title="Voice conversation"
                    >
                      <VoiceIcon />
                      <span>Voice</span>
                    </button>
                  </div>
                  <button
                    type="submit"
                    disabled={busy || !question.trim()}
                    className="nia-send-button"
                    aria-label="Send message"
                  >
                    {busy ? <LoadingDots /> : <ArrowUpIcon />}
                  </button>
                </div>
              </form>
              <p className="nia-disclaimer">NIA may make mistakes. Verify important findings against the cited records.</p>
            </div>
          </div>
        </section>

        {reportOpen ? (
          <div className="nia-modal-layer">
            <button
              type="button"
              className="nia-modal-backdrop"
              aria-label="Close report"
              onClick={closeReport}
            />
            <aside className="nia-report-panel" role="dialog" aria-modal="true" aria-label="Report a problem">
              <div className="nia-source-head">
                <div>
                  <span>Testing</span>
                  <strong>Report a problem</strong>
                </div>
                <button type="button" className="nia-icon-button" onClick={closeReport} aria-label="Close report">
                  <CloseIcon />
                </button>
              </div>
              {reportSent ? (
                <div className="nia-report-done">
                  <p>Thank you — your report was sent.</p>
                  <button type="button" className="nia-primary-button" onClick={closeReport}>
                    Close
                  </button>
                </div>
              ) : (
                <form onSubmit={sendReport} className="nia-report-form">
                  <p className="nia-report-intro">
                    Found a bug, or an answer that was inaccurate or inappropriate? Tell us
                    what happened. Your current chat is attached automatically.
                  </p>
                  <label>
                    <span>Your name</span>
                    <input
                      className="nia-field"
                      value={reportName}
                      maxLength={120}
                      onChange={(event) => setReportName(event.target.value)}
                    />
                  </label>
                  <label>
                    <span>Comments</span>
                    <textarea
                      className="nia-field nia-report-textarea"
                      value={reportComment}
                      maxLength={4000}
                      rows={6}
                      required
                      onChange={(event) => setReportComment(event.target.value)}
                    />
                  </label>
                  {reportError ? <p className="nia-form-error">{reportError}</p> : null}
                  <button
                    type="submit"
                    className="nia-primary-button"
                    disabled={reportSending || !reportComment.trim()}
                  >
                    {reportSending ? "Sending…" : "Submit report"}
                  </button>
                </form>
              )}
            </aside>
          </div>
        ) : null}

        {selectedCitation ? (
          <div className="nia-modal-layer">
            <button
              type="button"
              className="nia-modal-backdrop"
              aria-label="Close citation"
              onClick={() => setSelectedCitation(null)}
            />
            <aside className="nia-source-panel">
              <div className="nia-source-head">
                <div>
                  <span>Source</span>
                  <strong>{citationHeading(selectedCitation)}</strong>
                </div>
                <button type="button" className="nia-icon-button" onClick={() => setSelectedCitation(null)} aria-label="Close citation">
                  <CloseIcon />
                </button>
              </div>
              <dl>
                {Object.entries(selectedCitation.fields ?? {}).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </aside>
          </div>
        ) : null}
      </div>
    </main>
  );
}

function ChatMessage({
  line,
  onCitation,
  onDatasetSwitch,
}: {
  line: ChatLine;
  onCitation: (citation: { source_id: string; fields?: Record<string, unknown> }) => void;
  onDatasetSwitch: (fileId: number) => void;
}) {
  const isUser = line.role === "user";
  return (
    <article className={`nia-message ${isUser ? "is-user" : "is-assistant"}`}>
      {isUser ? (
        <div className={`nia-user-message ${line.partial ? "is-partial" : ""}`}>
          <p>{line.text || "…"}</p>
        </div>
      ) : (
        <div className="nia-assistant-row">
          <div className="nia-message-avatar"><NiaGlyph /></div>
          <div className="nia-assistant-content">
            <div className="nia-message-meta">
              <strong>NIA</strong>
              {line.mode === "voice" ? <span>Voice</span> : null}
            </div>
            <div className="nia-answer-text">
              {line.listResults?.length ? (
                line.listResults.map((result) => (
                  <StructuredListResult key={result.action_id} result={result} />
                ))
              ) : line.text ? (
                <p>{line.text}</p>
              ) : line.progress ? (
                <div className="nia-progress" role="status">
                  <TypingIndicator />
                  <span>{line.progress}</span>
                </div>
              ) : line.streaming ? (
                <TypingIndicator />
              ) : (
                <p>…</p>
              )}
            </div>
            {line.suggestedFileId ? (
              <button
                type="button"
                className="nia-switch-dataset-action"
                onClick={() => onDatasetSwitch(line.suggestedFileId as number)}
              >
                Switch to the suggested list
              </button>
            ) : null}
            {line.interrupted ? <span className="nia-interrupted">Response interrupted</span> : null}
            {line.citations?.length ? (
              <div className="nia-citations">
                {line.citations.map((citation, index) => {
                  const item = line.evidence?.find((entry) => entry.source_id === citation);
                  return (
                    <button
                      key={citation}
                      type="button"
                      onClick={() => onCitation({ source_id: citation, fields: item?.fields })}
                      className="nia-citation-chip"
                      title={citationLabel(item?.fields, index)}
                    >
                      <SourceIcon />
                      <span>{index + 1}</span>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </article>
  );
}

function StructuredListResult({ result }: { result: QueryListResult }) {
  const start = result.rows.length ? result.offset + 1 : 0;
  const end = result.offset + result.rows.length;
  const selected = result.window?.count ?? result.window?.size;
  const position = result.window?.anchor === "end" ? "last" : "first";
  return (
    <section className="nia-structured-result" aria-label={`${result.dataset_label} results`}>
      <p>
        {result.total_count.toLocaleString()} records in {result.dataset_label}. Showing {start.toLocaleString()}-
        {end.toLocaleString()} of {result.total_count.toLocaleString()}
        {result.window ? ` from the requested ${position} ${selected}` : ""}.
      </p>
      <div className="nia-result-table-wrap">
        <table className="nia-result-table">
          <thead>
            <tr>
              <th scope="col">#</th>
              {result.fields.map((field) => (
                <th scope="col" key={field.name}>{field.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, index) => (
              <tr key={`${row.file_id ?? "file"}-${row.source_row_id ?? index}`}>
                <th scope="row">{result.offset + index + 1}</th>
                {result.fields.map((field) => (
                  <td key={field.name}>{displayResultValue(row.values[field.name])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.has_more ? <p className="nia-result-more">Say “next” to continue.</p> : null}
    </section>
  );
}

function displayResultValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map(displayResultValue).join(", ");
  return String(value);
}

function starterPrompts(datasetLabel?: string | null) {
  const label = datasetLabel || "this list";
  return [
    {
      title: "Explore the records",
      caption: `What data is available in ${label}?`,
      prompt: "What information is available in this list?",
    },
    {
      title: "Count records",
      caption: "Start with a precise database question",
      prompt: "How many records are in this list?",
    },
    {
      title: "Browse communities",
      caption: "See distinct places in the records",
      prompt: "List the communities represented in the student records.",
    },
    {
      title: "Find a person",
      caption: "Search names naturally",
      prompt: "Find students named Samuel and show me the matching records.",
    },
  ];
}

function modelLabel(id: string): string {
  // "grok-4.20-0309-non-reasoning" is a build identifier, not something to show a
  // researcher. Keep the family, say whether it reasons.
  const family = id.replace(/^grok-/, "").split("-")[0];
  if (id.includes("non-reasoning")) return `${family} fast`;
  if (id.endsWith("-fast")) return `${family} fast-reasoning`;
  return family;
}

function modelHint(id: string): string {
  // This picks the model that writes the answer, not the one that plans the query.
  // Planning is pinned to PLANNER_MODEL server-side so a slower pick cannot make
  // finding the records slower -- only the wording of the reply changes.
  if (id.includes("non-reasoning")) {
    return `${id} - writes the answer directly`;
  }
  return `${id} - reasons before writing the answer, slower and more deliberate`;
}

function defaultDatasetId(datasets: Dataset[]): number | null {
  return datasets.find((item) => item.is_default_people_scope)?.file_id ?? datasets[0]?.file_id ?? null;
}

function shortDatasetLabel(dataset: Dataset): string {
  const label = dataset.user_facing_label.toLowerCase();
  if (dataset.is_default_people_scope || label.includes("master")) return "Master list";
  if (label.includes("confirmed") && label.includes("death")) return "Confirmed deaths";
  return dataset.user_facing_label;
}

function compactDatasetLabel(dataset: Dataset): string {
  return dataset.is_default_people_scope || dataset.user_facing_label.toLowerCase().includes("master")
    ? "Master"
    : "Deaths";
}

function citationLabel(fields: Record<string, unknown> | undefined, index: number) {
  const name = fields?.canonical_name || fields?.student_name || fields?.Name;
  if (typeof name === "string" && name.trim()) return name.trim();
  return `Source ${index + 1}`;
}

function citationHeading(citation: { source_id: string; fields?: Record<string, unknown> }) {
  return citationLabel(citation.fields, 0);
}

function welcomeLine(): ChatLine {
  return {
    id: "welcome",
    role: "system",
    text: "Ask naturally. NIA searches only the research data available in your access scope.",
  };
}

function turnToLine(turn: ConversationTurn): ChatLine {
  return {
    id: crypto.randomUUID(),
    role: turn.role === "user" ? "user" : "assistant",
    text: turn.text,
    mode: turn.mode,
    interrupted: turn.interrupted,
    citations: turn.citations,
  };
}

function upsertLine(lines: ChatLine[], next: ChatLine): ChatLine[] {
  const index = lines.findIndex((line) => line.id === next.id);
  if (index < 0) return [...lines, next];
  return lines.map((line, current) => (current === index ? next : line));
}

function updateLineProgress(lines: ChatLine[], id: string, progress: string): ChatLine[] {
  return lines.map((line) =>
    line.id === id && !line.text ? { ...line, progress } : line
  );
}

function initials(value: string) {
  const cleaned = value.replace(/^principal-/, "").trim();
  return (cleaned.slice(0, 2) || "NI").toUpperCase();
}

function NiaMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`nia-mark ${compact ? "is-compact" : ""}`}>
      <NiaGlyph />
    </div>
  );
}

function NiaGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="nia-glyph" fill="none" aria-hidden="true">
      <path d="M7 17V7l10 10V7" stroke="currentColor" strokeWidth="2.15" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIcon() { return <Icon path="M4 7h16M4 12h16M4 17h16" />; }
function CloseIcon() { return <Icon path="M6 6l12 12M18 6L6 18" />; }
function ComposeIcon() { return <Icon path="M12 5v14M5 12h14" />; }
function ChevronIcon() { return <Icon path="M9 10l3 3 3-3" className="h-4 w-4" />; }
function VoiceIcon() { return <Icon path="M12 15a3 3 0 003-3V7a3 3 0 10-6 0v5a3 3 0 003 3zm5-3a5 5 0 01-10 0M12 17v3M9 20h6" />; }
function ArrowUpIcon() { return <Icon path="M12 19V5M6.5 10.5L12 5l5.5 5.5" className="h-4 w-4" />; }
function ArrowDiagonalIcon() { return <Icon path="M8 16L16 8M10 8h6v6" className="h-4 w-4" />; }
function CopyIcon() { return <Icon path="M9 9h9v9H9zM6 15H5V5h10v1" />; }
function FlagIcon() { return <Icon path="M6 20V5h11l-2 3.5L17 12H6" className="h-4 w-4" />; }
function TrashIcon() { return <Icon path="M5 7h14M10 7V5h4v2M6 7l1 12h10l1-12M10 11v5M14 11v5" className="h-4 w-4" />; }
function CheckIcon() { return <Icon path="M5 13l4 4L19 7" />; }
function SourceIcon() { return <Icon path="M7 7h10v10H7zM10 10h8v8h-8z" className="h-3.5 w-3.5" />; }
function PanelIcon({ collapsed = false }: { collapsed?: boolean }) {
  return <Icon path={collapsed ? "M4 5h16v14H4zM9 5v14" : "M4 5h16v14H4zM9 5v14M6.5 9h0M6.5 12h0M6.5 15h0"} />;
}
function Icon({ path, className = "h-5 w-5" }: { path: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
      <path d={path} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TypingIndicator() {
  return (
    <span className="nia-typing" aria-label="NIA is responding">
      <span />
      <span />
      <span />
    </span>
  );
}

function LoadingDots() {
  return (
    <span className="nia-loading-dots" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}
