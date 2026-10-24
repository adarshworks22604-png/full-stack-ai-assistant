import { describe, expect, it } from "vitest";
import {
  chatReducer,
  initialChatState,
  selectStatus,
  type AssistantMessage,
  type ChatState,
} from "../src/app/chatReducer";
import type { Source, StreamEvent } from "../src/types/api";

const bug: Source = { source_id: "BUG-1", source_type: "bug", title: "A bug" };
const doc: Source = { source_id: "DOC-1", source_type: "documentation", title: "A doc", uri: "https://example.invalid/d" };

function submit(state: ChatState = initialChatState): ChatState {
  return chatReducer(state, { type: "submit", userId: "u1", assistantId: "a1", text: "hi" });
}
const ev = (state: ChatState, event: StreamEvent) => chatReducer(state, { type: "event", event });
const last = (s: ChatState) => s.messages[s.messages.length - 1] as AssistantMessage;

describe("chatReducer", () => {
  it("walks the happy path: submitting -> streaming -> enriching -> complete", () => {
    let s = submit();
    expect(selectStatus(s)).toBe("submitting");

    s = ev(s, { type: "request.started", request_id: "r1", status: "started" });
    expect(selectStatus(s)).toBe("streaming");

    s = ev(s, { type: "assistant.delta", request_id: "r1", text: "Checking " });
    s = ev(s, { type: "assistant.delta", request_id: "r1", text: "now." });
    expect(last(s).preliminaryText).toBe("Checking now.");

    s = ev(s, { type: "tool.status", request_id: "r1", tool: "get_bug_details", status: "running", summary: "x" });
    expect(selectStatus(s)).toBe("enriching");

    s = ev(s, { type: "evidence.ready", request_id: "r1", sources: [bug] });
    s = ev(s, { type: "evidence.ready", request_id: "r1", sources: [bug, doc] });
    expect(last(s).evidence.map((e) => e.source_id)).toEqual(["BUG-1", "DOC-1"]); // no duplicates

    s = ev(s, { type: "assistant.final", request_id: "r1", answer: "Final.", sources: [bug, doc], limitations: ["l1"] });
    expect(selectStatus(s)).toBe("complete");
    expect(last(s).finalText).toBe("Final.");
    expect(last(s).preliminaryText).toBe("Checking now."); // kept, but final replaces it in the UI
    expect(last(s).limitations).toEqual(["l1"]);
  });

  it("replaces a tool's status instead of duplicating it", () => {
    let s = ev(submit(), { type: "request.started", request_id: "r1", status: "started" });
    s = ev(s, { type: "tool.status", request_id: "r1", tool: "search_documentation", status: "running", summary: "a" });
    s = ev(s, { type: "tool.status", request_id: "r1", tool: "search_documentation", status: "done", summary: "b" });
    expect(last(s).tools).toEqual([{ tool: "search_documentation", status: "done", summary: "b" }]);
  });

  it("ignores events for a different request id", () => {
    let s = ev(submit(), { type: "request.started", request_id: "r1", status: "started" });
    s = ev(s, { type: "assistant.delta", request_id: "other", text: "STALE" });
    expect(last(s).preliminaryText).toBe("");
  });

  it("ignores non-start events before request.started", () => {
    const s = ev(submit(), { type: "assistant.delta", request_id: "r1", text: "early" });
    expect(last(s).preliminaryText).toBe("");
  });

  it("request.error stops the loading state and keeps the error", () => {
    let s = ev(submit(), { type: "request.started", request_id: "r1", status: "started" });
    s = ev(s, { type: "request.error", request_id: "r1", error_code: "UPSTREAM_TIMEOUT", message: "slow", retryable: true });
    expect(selectStatus(s)).toBe("failed");
    expect(last(s).error).toMatchObject({ code: "UPSTREAM_TIMEOUT", retryable: true });
  });

  it("request.done without a final answer is a failure", () => {
    let s = ev(submit(), { type: "request.started", request_id: "r1", status: "started" });
    s = ev(s, { type: "request.done", request_id: "r1" });
    expect(selectStatus(s)).toBe("failed");
    expect(last(s).error?.code).toBe("STREAM_ENDED_EARLY");
  });

  it("request.done after a final answer changes nothing", () => {
    let s = ev(submit(), { type: "request.started", request_id: "r1", status: "started" });
    s = ev(s, { type: "assistant.final", request_id: "r1", answer: "ok", sources: [] });
    s = ev(s, { type: "request.done", request_id: "r1" });
    expect(selectStatus(s)).toBe("complete");
  });

  it("stream_closed while active becomes a retryable disconnect", () => {
    const s = chatReducer(ev(submit(), { type: "request.started", request_id: "r1", status: "started" }), { type: "stream_closed" });
    expect(selectStatus(s)).toBe("failed");
    expect(last(s).error).toMatchObject({ code: "STREAM_DISCONNECTED", retryable: true });
  });

  it("cancel stops the request and late events are ignored", () => {
    let s = ev(submit(), { type: "request.started", request_id: "r1", status: "started" });
    s = chatReducer(s, { type: "cancel" });
    expect(selectStatus(s)).toBe("cancelled");
    s = ev(s, { type: "assistant.final", request_id: "r1", answer: "late", sources: [] });
    expect(selectStatus(s)).toBe("cancelled");
    expect(last(s).finalText).toBeUndefined();
  });

  it("blocks duplicate submissions while active", () => {
    const s = submit();
    const again = chatReducer(s, { type: "submit", userId: "u2", assistantId: "a2", text: "again" });
    expect(again.messages).toHaveLength(2);
  });

  it("discard_last_turn removes the failed turn so it can be retried", () => {
    let s = ev(submit(), { type: "request.started", request_id: "r1", status: "started" });
    s = chatReducer(s, { type: "stream_closed" });
    s = chatReducer(s, { type: "discard_last_turn" });
    expect(s.messages).toHaveLength(0);
  });

  it("discard_last_turn does nothing while a request is active", () => {
    const s = chatReducer(submit(), { type: "discard_last_turn" });
    expect(s.messages).toHaveLength(2);
  });
});
