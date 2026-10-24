// Wire types. These mirror docs/api-contract.md. Field names are snake_case on the wire.

export type EmailContext = {
  subject: string;
  bodyText: string;
  itemId?: string;
};

export interface ChatRequest {
  message: string;
  email_context: { subject: string; body_text: string } | null;
  conversation_id: string | null;
}

export type SourceType = "bug" | "documentation";

export interface Source {
  source_id: string;
  source_type: SourceType;
  title: string;
  /** Only render as a link when it passes safeUrl(). */
  uri?: string;
}

export type ToolName = "search_documentation" | "get_bug_details";
export type ToolState = "running" | "done" | "failed";

export type ErrorCode =
  | "RATE_LIMITED"
  | "UPSTREAM_TIMEOUT"
  | "LLM_UNAVAILABLE"
  | "UNAUTHORIZED"
  | "INVALID_REQUEST"
  | "STREAM_DISCONNECTED"
  | "STREAM_ENDED_EARLY"
  | "INTERNAL_ERROR";

export type StreamEvent =
  | { type: "request.started"; request_id: string; status: string }
  | { type: "assistant.delta"; request_id: string; text: string }
  | { type: "tool.status"; request_id: string; tool: ToolName; status: ToolState; summary: string }
  | { type: "evidence.ready"; request_id: string; sources: Source[] }
  | {
      type: "assistant.final";
      request_id: string;
      answer: string;
      sources: Source[];
      limitations?: string[];
    }
  | {
      type: "request.error";
      request_id: string;
      error_code: ErrorCode;
      message: string;
      retryable: boolean;
    }
  | { type: "request.done"; request_id: string };

/** A chat transport. Stage 2 uses a mock; Stage 4 swaps in the real SSE client. */
export type ChatStream = (request: ChatRequest, signal: AbortSignal) => AsyncIterable<StreamEvent>;

export function toChatRequest(message: string, email: EmailContext | null): ChatRequest {
  return {
    message,
    email_context: email ? { subject: email.subject, body_text: email.bodyText } : null,
    conversation_id: null,
  };
}
