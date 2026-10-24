import type { ErrorCode, Source, StreamEvent, ToolName, ToolState } from "../types/api";

export type ChatStatus =
  | "idle"
  | "submitting"
  | "streaming"
  | "enriching"
  | "complete"
  | "failed"
  | "cancelled";

export interface ToolProgress {
  tool: ToolName;
  status: ToolState;
  summary: string;
}

export interface ChatError {
  code: ErrorCode;
  message: string;
  retryable: boolean;
}

export interface UserMessage {
  id: string;
  role: "user";
  text: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  status: ChatStatus;
  requestId?: string;
  /** Shown while evidence is still being verified. */
  preliminaryText: string;
  /** Replaces the preliminary text once the grounded answer arrives. */
  finalText?: string;
  limitations: string[];
  tools: ToolProgress[];
  /** Sources found so far (may arrive before the final answer). */
  evidence: Source[];
  /** Sources the final answer is based on. */
  sources: Source[];
  error?: ChatError;
}

export type ChatMessage = UserMessage | AssistantMessage;

export interface ChatState {
  messages: ChatMessage[];
}

export const initialChatState: ChatState = { messages: [] };

export type ChatAction =
  | { type: "submit"; userId: string; assistantId: string; text: string }
  | { type: "event"; event: StreamEvent }
  | { type: "cancel" }
  | { type: "stream_closed" }
  | { type: "connection_failed"; error: ChatError }
  | { type: "discard_last_turn" };

const ACTIVE: ChatStatus[] = ["submitting", "streaming", "enriching"];
export const isActive = (status: ChatStatus): boolean => ACTIVE.includes(status);

function lastAssistant(state: ChatState): { index: number; message: AssistantMessage } | undefined {
  for (let i = state.messages.length - 1; i >= 0; i--) {
    const m = state.messages[i];
    if (m && m.role === "assistant") return { index: i, message: m };
  }
  return undefined;
}

export function selectStatus(state: ChatState): ChatStatus {
  return lastAssistant(state)?.message.status ?? "idle";
}

export function selectLastUserText(state: ChatState): string | undefined {
  for (let i = state.messages.length - 1; i >= 0; i--) {
    const m = state.messages[i];
    if (m && m.role === "user") return m.text;
  }
  return undefined;
}

function updateLast(state: ChatState, patch: (m: AssistantMessage) => AssistantMessage): ChatState {
  const found = lastAssistant(state);
  if (!found) return state;
  const messages = state.messages.slice();
  messages[found.index] = patch(found.message);
  return { messages };
}

function mergeSources(existing: Source[], incoming: Source[]): Source[] {
  const byId = new Map(existing.map((s) => [s.source_id, s]));
  for (const s of incoming) byId.set(s.source_id, s);
  return Array.from(byId.values());
}

function fail(m: AssistantMessage, error: ChatError): AssistantMessage {
  return { ...m, status: "failed", error };
}

function applyEvent(m: AssistantMessage, event: StreamEvent): AssistantMessage {
  if (event.type === "request.started") {
    return { ...m, requestId: event.request_id, status: "streaming" };
  }
  // Every other event must belong to the request we started; anything else is stale.
  if (m.requestId !== event.request_id) return m;

  switch (event.type) {
    case "assistant.delta":
      return { ...m, status: "streaming", preliminaryText: m.preliminaryText + event.text };
    case "tool.status": {
      const rest = m.tools.filter((t) => t.tool !== event.tool);
      const tools = [...rest, { tool: event.tool, status: event.status, summary: event.summary }];
      return { ...m, status: "enriching", tools };
    }
    case "evidence.ready":
      return { ...m, status: "enriching", evidence: mergeSources(m.evidence, event.sources) };
    case "assistant.final":
      return {
        ...m,
        status: "complete",
        finalText: event.answer,
        sources: event.sources,
        evidence: mergeSources(m.evidence, event.sources),
        limitations: event.limitations ?? [],
      };
    case "request.error":
      return fail(m, { code: event.error_code, message: event.message, retryable: event.retryable });
    case "request.done":
      // done without a final answer means the stream ended early.
      return fail(m, {
        code: "STREAM_ENDED_EARLY",
        message: "The assistant stopped before finishing. Try again.",
        retryable: true,
      });
  }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "submit": {
      // Block duplicate submissions while a request is in flight.
      if (isActive(selectStatus(state))) return state;
      const user: UserMessage = { id: action.userId, role: "user", text: action.text };
      const assistant: AssistantMessage = {
        id: action.assistantId,
        role: "assistant",
        status: "submitting",
        preliminaryText: "",
        limitations: [],
        tools: [],
        evidence: [],
        sources: [],
      };
      return { messages: [...state.messages, user, assistant] };
    }
    case "event": {
      const found = lastAssistant(state);
      if (!found || !isActive(found.message.status)) return state; // late events are ignored
      return updateLast(state, (m) => applyEvent(m, action.event));
    }
    case "cancel": {
      const found = lastAssistant(state);
      if (!found || !isActive(found.message.status)) return state;
      return updateLast(state, (m) => ({ ...m, status: "cancelled" }));
    }
    case "stream_closed": {
      const found = lastAssistant(state);
      if (!found || !isActive(found.message.status)) return state;
      return updateLast(state, (m) =>
        fail(m, {
          code: "STREAM_DISCONNECTED",
          message: "The connection dropped before the answer finished.",
          retryable: true,
        }),
      );
    }
    case "connection_failed": {
      const found = lastAssistant(state);
      if (!found || !isActive(found.message.status)) return state;
      return updateLast(state, (m) => fail(m, action.error));
    }
    case "discard_last_turn": {
      const found = lastAssistant(state);
      if (!found || isActive(found.message.status)) return state;
      const before = state.messages.slice(0, found.index);
      const prev = before[before.length - 1];
      return { messages: prev && prev.role === "user" ? before.slice(0, -1) : before };
    }
  }
}
