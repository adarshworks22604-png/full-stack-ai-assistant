import type { ChatRequest, ChatStream, Source, StreamEvent } from "../types/api";

// Synthetic data only. Replaced by the real SSE client in Stage 4.
const BUGS: Record<string, { title: string; status: string; resolution: string | null; docId: string }> = {
  "BUG-4821": {
    title: "Payment service times out under load",
    status: "Resolved",
    resolution: "Increase the connection pool size and add retry with backoff (fixed in 2.3.2).",
    docId: "DOC-001",
  },
  "BUG-1002": {
    title: "Login page renders blank on Safari",
    status: "Open",
    resolution: null,
    docId: "DOC-002",
  },
};

const DOCS: Record<string, Source & { excerpt: string }> = {
  "DOC-001": {
    source_id: "DOC-001",
    source_type: "documentation",
    title: "Payments Service Tuning Guide",
    uri: "https://example.invalid/docs/payments-tuning",
    excerpt: "Raise the connection pool size and enable retry with exponential backoff for timeouts under load.",
  },
  "DOC-002": {
    source_id: "DOC-002",
    source_type: "documentation",
    title: "Web Portal Browser Support",
    uri: "https://example.invalid/docs/portal-browsers",
    excerpt: "Safari 17 is supported from portal version 1.9; earlier versions may render blank pages.",
  },
};

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

let counter = 0;

export function createMockChatStream({ delayMs = 500 }: { delayMs?: number } = {}): ChatStream {
  return async function* mockStream(request: ChatRequest, signal: AbortSignal): AsyncGenerator<StreamEvent> {
    const id = `mock-req-${++counter}`;
    const wait = (factor = 1) => sleep(delayMs * factor, signal);
    const text = `${request.email_context?.subject ?? ""} ${request.email_context?.body_text ?? ""} ${request.message}`;
    const ids = Array.from(new Set(text.match(/BUG-\d+/g) ?? [])).slice(0, 3);

    yield { type: "request.started", request_id: id, status: "started" };
    await wait(0.5);

    if (/simulate error/i.test(request.message)) {
      yield {
        type: "request.error",
        request_id: id,
        error_code: "UPSTREAM_TIMEOUT",
        message: "The bug tracker took too long to respond. Try again in a moment.",
        retryable: true,
      };
      return;
    }

    if (ids.length === 0) {
      yield {
        type: "assistant.final",
        request_id: id,
        answer:
          "I couldn't find a bug ID in this email. Tell me which bug you mean (for example BUG-1234) and I'll look it up.",
        sources: [],
        limitations: ["No bug ID was detected, so nothing was looked up."],
      };
      yield { type: "request.done", request_id: id };
      return;
    }

    const preliminary =
      `This email mentions ${ids.join(" and ")}. I'm checking the bug record and the documentation ` +
      `before saying anything about cause or status.`;
    for (const word of preliminary.split(" ")) {
      yield { type: "assistant.delta", request_id: id, text: word + " " };
      await wait(0.08);
    }

    yield { type: "tool.status", request_id: id, tool: "get_bug_details", status: "running", summary: `Checking ${ids.join(", ")}` };
    yield { type: "tool.status", request_id: id, tool: "search_documentation", status: "running", summary: "Searching documentation" };
    await wait(1.5);

    const found = ids.filter((b) => b in BUGS);
    const missing = ids.filter((b) => !(b in BUGS));
    const bugSources: Source[] = found.map((b) => ({
      source_id: b,
      source_type: "bug",
      title: `${b}: ${BUGS[b]!.title}`,
    }));

    yield {
      type: "tool.status",
      request_id: id,
      tool: "get_bug_details",
      status: found.length > 0 ? "done" : "failed",
      summary: found.length > 0 ? `Found ${found.join(", ")}` : `${missing.join(", ")} not found`,
    };
    if (bugSources.length > 0) yield { type: "evidence.ready", request_id: id, sources: bugSources };
    await wait(1);

    const docs = found.map((b) => DOCS[BUGS[b]!.docId]!).filter(Boolean);
    yield {
      type: "tool.status",
      request_id: id,
      tool: "search_documentation",
      status: "done",
      summary: docs.length > 0 ? `${docs.length} relevant passage(s)` : "No relevant documentation",
    };
    const docSources: Source[] = docs.map(({ source_id, source_type, title, uri }) => ({ source_id, source_type, title, uri }));
    if (docSources.length > 0) yield { type: "evidence.ready", request_id: id, sources: docSources };
    await wait(1);

    const parts: string[] = [];
    for (const b of found) {
      const bug = BUGS[b]!;
      const fix = bug.resolution ? ` Fix: ${bug.resolution}` : " No resolution is recorded yet.";
      parts.push(`${b} (${bug.title}) is ${bug.status}.${fix} [${b}]`);
      const doc = DOCS[bug.docId];
      if (doc) parts.push(`Related guidance: ${doc.excerpt} [${doc.source_id}]`);
    }
    for (const b of missing) parts.push(`I couldn't find ${b} in the bug tracker, so I can't confirm its status or cause.`);

    const limitations = missing.map((b) => `${b} was not found in the bug tracker.`);
    if (docs.length === 0) limitations.push("No documentation matched this question.");

    yield {
      type: "assistant.final",
      request_id: id,
      answer: parts.join("\n\n"),
      sources: [...bugSources, ...docSources],
      limitations,
    };
    yield { type: "request.done", request_id: id };
  };
}
