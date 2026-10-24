import { describe, expect, it } from "vitest";
import { createMockChatStream } from "../src/services/mockChatStream";
import { toChatRequest, type StreamEvent } from "../src/types/api";

async function collect(message: string, email: { subject: string; bodyText: string } | null) {
  const events: StreamEvent[] = [];
  const stream = createMockChatStream({ delayMs: 0 });
  for await (const e of stream(toChatRequest(message, email), new AbortController().signal)) events.push(e);
  return events;
}
const types = (events: StreamEvent[]) => events.map((e) => e.type);

describe("mock chat stream", () => {
  it("emits events in contract order for a known bug", async () => {
    const events = await collect("cause?", { subject: "BUG-4821", bodyText: "" });
    const t = types(events);
    expect(t[0]).toBe("request.started");
    expect(t.indexOf("assistant.delta")).toBeLessThan(t.indexOf("tool.status"));
    expect(t.indexOf("evidence.ready")).toBeLessThan(t.indexOf("assistant.final"));
    expect(t.at(-2)).toBe("assistant.final");
    expect(t.at(-1)).toBe("request.done");
    expect(new Set(events.map((e) => e.request_id)).size).toBe(1);
  });

  it("does not claim a cause in the preliminary text", async () => {
    const events = await collect("cause?", { subject: "BUG-4821", bodyText: "" });
    const preliminary = events.filter((e) => e.type === "assistant.delta").map((e) => (e as { text: string }).text).join("");
    expect(preliminary.toLowerCase()).not.toContain("connection pool");
  });

  it("reports an unknown bug honestly with a limitation and no bug source", async () => {
    const events = await collect("status?", { subject: "BUG-9999", bodyText: "" });
    const final = events.find((e) => e.type === "assistant.final");
    expect(final).toMatchObject({ type: "assistant.final" });
    if (final?.type === "assistant.final") {
      expect(final.sources).toHaveLength(0);
      expect(final.limitations?.join(" ")).toContain("BUG-9999");
    }
  });

  it("asks for an ID when none is present", async () => {
    const events = await collect("help", { subject: "Question", bodyText: "no id" });
    expect(types(events)).not.toContain("tool.status");
    expect(types(events)).toContain("assistant.final");
  });

  it("can simulate a retryable error", async () => {
    const events = await collect("please simulate error", null);
    expect(events.at(-1)).toMatchObject({ type: "request.error", retryable: true });
  });

  it("stops when aborted", async () => {
    const controller = new AbortController();
    const stream = createMockChatStream({ delayMs: 50 });
    const it = stream(toChatRequest("x", { subject: "BUG-4821", bodyText: "" }), controller.signal)[Symbol.asyncIterator]();
    await it.next();
    controller.abort();
    await expect(it.next()).rejects.toMatchObject({ name: "AbortError" });
  });
});
