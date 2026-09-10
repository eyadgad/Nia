// "/" means same origin, which is how the deployed build reaches its backend: Next rewrites
// /api/* to it, so the browser only ever talks to this site and the session cookie is
// first-party. Unset still means a local stack, so nothing changes for development.
const CONFIGURED_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;
const API_BASE =
  CONFIGURED_API_BASE === undefined || CONFIGURED_API_BASE === ""
    ? "http://localhost:8000"
    : CONFIGURED_API_BASE.replace(/\/$/, "");

const LOCAL_HOST = /^(localhost|127(?:\.\d+){3}|\[?::1\]?|0\.0\.0\.0)$/i;

/** True when this page would have to reach the visitor's own machine to find the API.
 *
 * The fallback base is localhost, which is right when you are running the stack and wrong
 * everywhere else. Deployed, it makes every visitor's browser knock on their own port 8000:
 * Chrome and Edge now gate that behind a "wants to access other apps and services on this
 * device" prompt, so a tester's first impression of a records assistant is a public site
 * asking for access to their machine -- and whatever answers on that port is not this API.
 * Better to say the build has no backend than to go looking for one on their computer.
 */
export function apiTargetIsUnreachable(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const target = new URL(API_BASE, window.location.href);
    return LOCAL_HOST.test(target.hostname) && !LOCAL_HOST.test(window.location.hostname);
  } catch {
    return false;
  }
}

export class ApiUnconfiguredError extends Error {
  constructor() {
    super(
      "This build has no backend configured, so there is nothing to sign in to yet. " +
        "Set NEXT_PUBLIC_API_BASE_URL and redeploy."
    );
    this.name = "ApiUnconfiguredError";
  }
}

function assertApiReachable(): void {
  // Thrown before fetch rather than after it fails: the point is that the request is never
  // made, so the browser never asks the visitor for local network access.
  if (apiTargetIsUnreachable()) throw new ApiUnconfiguredError();
}

export type Session = {
  principal_id: string;
  allowed_file_ids: number[];
  can_use_private_files: boolean;
  history_allowed: boolean;
};

export type Dataset = {
  file_id: number;
  filename: string;
  description: string | null;
  current_version: number;
  private: boolean;
  assistant_enabled: boolean;
  user_facing_label: string;
  is_default_people_scope: boolean;
  fields: DatasetField[];
  supported_operations: string[];
  starter_prompts: StarterPrompt[];
};

export type DatasetField = {
  semantic_field: string;
  human_label: string;
  aliases?: string[];
  semantic_type: string;
  allowed_operators: string[];
  aggregatable: boolean;
  sortable: boolean;
};

export type StarterPrompt = {
  title: string;
  caption: string;
  prompt: string;
};

export class AuthExpiredError extends Error {
  constructor(message = "Your session expired. Please sign in again.") {
    super(message);
    this.name = "AuthExpiredError";
  }
}

async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  assertApiReachable();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
  });
  if (response.status === 401) {
    throw new AuthExpiredError();
  }
  return response;
}

export async function login(username: string, password: string): Promise<Session> {
  assertApiReachable();
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(
      response.status === 401
        ? "That username and password were not accepted. Check them against the ones shown here."
        : "Sign-in is unavailable right now. Please try again."
    );
  }
  return response.json();
}

export async function fetchSession(): Promise<Session | null> {
  assertApiReachable();
  const response = await fetch(`${API_BASE}/api/auth/session`, { credentials: "include" });
  if (response.status === 204) {
    return null;
  }
  if (!response.ok) {
    throw new Error("Could not restore the session.");
  }
  return response.json();
}

export async function logout(): Promise<void> {
  assertApiReachable();
  await fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export type ModelChoice = {
  id: string;
  selected: boolean;
};

export type DatasetCatalog = {
  datasets: Dataset[];
  models: ModelChoice[];
};

export async function fetchDatasets(): Promise<DatasetCatalog> {
  const response = await authorizedFetch("/api/assistant/datasets");
  if (!response.ok) {
    throw new Error("Could not load authorized datasets.");
  }
  const payload = await response.json();
  return { datasets: payload.datasets ?? [], models: payload.models ?? [] };
}

export type LivekitToken = {
  server_url: string;
  room_name: string;
  participant_identity: string;
  participant_token: string;
  selected_file_id: number;
  agent_name: string;
  ttl_seconds: number;
};

export async function fetchLivekitToken(
  conversationId: string | null,
  selectedFileId: number
): Promise<LivekitToken> {
  const response = await authorizedFetch("/api/livekit/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId || undefined,
      selected_file_id: selectedFileId,
    }),
  });
  if (!response.ok) {
    throw new Error("Could not start a voice session.");
  }
  return response.json();
}

export async function health(): Promise<{ status: string }> {
  assertApiReachable();
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error("API unavailable");
  }
  return response.json();
}

export type QueryResult = {
  status: string;
  answer: string;
  planner_type: string | null;
  reasoning_calls: number;
  facts: Array<{ name: string; value: unknown }>;
  rows: Array<Record<string, unknown>>;
  list_results?: QueryListResult[];
  detail?: string | null;
  conversation_id?: string | null;
  selected_file_id?: number | null;
  suggested_file_id?: number | null;
  error_code?: string | null;
  citations?: string[];
  evidence?: Array<{ source_id: string; file_id?: number; fields?: Record<string, unknown> }>;
  inference?: boolean;
  planner_attempts?: number;
  planner_retry_count?: number;
  review_attempts?: number;
  review_status?: string | null;
  planner_total_model_calls?: number;
  planner_failure_stage?: string | null;
  planner_provider?: string | null;
  planner_model?: string | null;
  planner_usage?: Record<string, unknown>;
};

export type QueryListResult = {
  action_id: string;
  dataset_label: string;
  fields: Array<{ name: string; label: string }>;
  rows: Array<{
    file_id?: number | null;
    source_row_id?: number | null;
    values: Record<string, unknown>;
  }>;
  total_count: number;
  offset: number;
  page_size?: number | null;
  has_more: boolean;
  window?: {
    anchor: "start" | "end";
    size: number;
    count?: number | null;
    cursor: number;
  } | null;
};

export type ConversationSummary = {
  id: string;
  title: string | null;
  active_frame_key: string | null;
  preview: string;
  turn_count: number;
  selected_file_id: number | null;
  selected_dataset_label: string | null;
  legacy_unscoped: boolean;
};

export type QueryEvent =
  | { event: "plan_started"; data: Record<string, unknown> }
  | { event: "plan_validated"; data: Record<string, unknown> }
  | { event: "retrieval_completed"; data: Record<string, unknown> }
  | { event: "computed_fact"; data: Record<string, unknown> }
  | { event: "answer_delta"; data: { text: string } }
  | { event: "citation"; data: { source_id: string; fields?: Record<string, unknown> } }
  | { event: "memory_update"; data: Record<string, unknown> }
  | { event: "answer_completed"; data: QueryResult };

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const response = await authorizedFetch("/api/assistant/conversations");
  if (!response.ok) {
    throw new Error("Could not load conversations.");
  }
  const payload = await response.json();
  return payload.conversations ?? [];
}

export async function renameConversation(
  conversationId: string,
  title: string
): Promise<void> {
  const response = await authorizedFetch(`/api/assistant/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error("Could not rename that conversation.");
  }
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const response = await authorizedFetch(`/api/assistant/conversations/${conversationId}`, {
    method: "DELETE",
  });
  // 404 means it is already gone, which is the outcome the caller wanted.
  if (!response.ok && response.status !== 404) {
    throw new Error("Could not delete that conversation.");
  }
}

export type ReportAttachment = {
  filename: string;
  contentType: string;
  dataBase64: string;
  byteSize: number;
};

export async function submitFeedback(input: {
  comment: string;
  reporterName?: string;
  conversationId?: string | null;
  attachments?: ReportAttachment[];
}): Promise<void> {
  const response = await authorizedFetch("/api/assistant/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      comment: input.comment,
      reporter_name: input.reporterName ?? "",
      conversation_id: input.conversationId ?? null,
      // The server stamps the renamed conversation with this, so the time in the sidebar
      // is the one the reporter's own clock showed. getTimezoneOffset counts the other way.
      tz_offset_minutes: -new Date().getTimezoneOffset(),
      attachments: (input.attachments ?? []).map((item) => ({
        filename: item.filename,
        content_type: item.contentType,
        data_base64: item.dataBase64,
      })),
    }),
  });
  if (!response.ok) {
    // A refused file comes back with a reason worth showing ("… is too large to attach").
    let detail = "";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Not JSON; the generic message below stands.
    }
    throw new Error(
      detail || (response.status === 413 ? "Those files are too large to send." : "Could not send that report."),
    );
  }
}

export type ConversationTurn = {
  role: string;
  text: string;
  mode?: string;
  interrupted?: boolean;
  citations?: string[];
};

export async function fetchConversation(
  conversationId: string
): Promise<{
  id: string;
  title: string | null;
  active_frame_key?: string | null;
  selected_file_id: number | null;
  selected_dataset_label: string | null;
  legacy_unscoped: boolean;
  turns: ConversationTurn[];
}> {
  const response = await authorizedFetch(`/api/assistant/conversations/${conversationId}`);
  if (!response.ok) {
    throw new Error("Could not open that conversation.");
  }
  return response.json();
}

export async function streamQuery(
  question: string,
  conversationId: string | null,
  selectedFileId: number,
  onEvent: (event: QueryEvent) => void,
  model?: string | null
): Promise<QueryResult> {
  const response = await authorizedFetch("/api/assistant/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      question,
      mode: "text",
      conversation_id: conversationId || undefined,
      selected_file_id: selectedFileId,
      model: model || undefined,
    }),
  });
  if (!response.ok || !response.body) {
    throw new Error("The assistant could not answer that question.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: QueryResult | null = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const block of parts) {
      const parsed = parseSseBlock(block);
      if (!parsed) {
        continue;
      }
      onEvent(parsed);
      if (parsed.event === "answer_completed") {
        completed = parsed.data;
      }
    }
  }
  if (!completed) {
    throw new Error("The assistant stream ended without a completed answer.");
  }
  return completed;
}

function parseSseBlock(block: string): QueryEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!dataLines.length) {
    return null;
  }
  return { event, data: JSON.parse(dataLines.join("\n")) } as QueryEvent;
}
