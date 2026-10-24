import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "../src/app/App";
import { createMockChatStream } from "../src/services/mockChatStream";
import type { ChatStream, StreamEvent } from "../src/types/api";

const fast = createMockChatStream({ delayMs: 0 });

describe("<App />", () => {
  it("shows the empty state and the sample email picker in dev", async () => {
    render(<App stream={fast} />);
    expect(await screen.findByText("Ask about this email")).toBeInTheDocument();
    expect(screen.getByLabelText("Sample email (development only)")).toBeInTheDocument();
    expect(screen.getByText("Payment service error BUG-4821")).toBeInTheDocument();
  });

  it("sends a question and shows the checked answer with sources", async () => {
    const user = userEvent.setup();
    render(<App stream={fast} />);
    await screen.findByText("Payment service error BUG-4821");

    await user.type(screen.getByLabelText("Ask about this email", { selector: "textarea" }), "What is the fix?{Enter}");

    expect(await screen.findByText("Checked against sources")).toBeInTheDocument();
    expect(screen.getByText(/Increase the connection pool size/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Payments Service Tuning Guide" });
    expect(link).toHaveAttribute("href", "https://example.invalid/docs/payments-tuning");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByText(/Preliminary/)).not.toBeInTheDocument();
  });

  it("shows a retryable error and recovers on retry", async () => {
    const user = userEvent.setup();
    render(<App stream={fast} />);
    await screen.findByText("Payment service error BUG-4821");

    await user.type(screen.getByLabelText("Ask about this email", { selector: "textarea" }), "simulate error{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("bug tracker took too long");

    // The retry re-sends the same question and hits the same simulated error again, never a stuck spinner.
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getAllByText("simulate error")).toHaveLength(1); // failed turn replaced, not duplicated
  });

  it("disables sending while a request runs and supports Stop", async () => {
    const user = userEvent.setup();
    // A stream that starts and then waits until aborted.
    const hanging: ChatStream = async function* (_req, signal) {
      yield { type: "request.started", request_id: "r1", status: "started" } satisfies StreamEvent;
      await new Promise<void>((_, reject) => signal.addEventListener("abort", () => reject(new DOMException("x", "AbortError"))));
    };
    render(<App stream={hanging} />);
    await screen.findByText("Payment service error BUG-4821");

    await user.type(screen.getByLabelText("Ask about this email", { selector: "textarea" }), "hello{Enter}");
    const stop = await screen.findByRole("button", { name: "Stop" });
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();

    await user.click(stop);
    await waitFor(() => expect(screen.getByText("You stopped this answer.")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  it("does not send email content when sharing is turned off", async () => {
    const user = userEvent.setup();
    let captured: unknown;
    const spy: ChatStream = (req, signal) => {
      captured = req;
      return fast(req, signal);
    };
    render(<App stream={spy} />);
    await screen.findByText("Payment service error BUG-4821");

    await user.click(screen.getByRole("switch", { name: "Share this email with the assistant" }));
    await user.type(screen.getByLabelText("Ask about this email", { selector: "textarea" }), "hi{Enter}");
    await screen.findByText(/couldn't find a bug ID/);
    expect(captured).toMatchObject({ email_context: null });
  });

  it("renders text answers as plain text, never as HTML", async () => {
    const user = userEvent.setup();
    const hostile: ChatStream = async function* () {
      yield { type: "request.started", request_id: "r1", status: "started" };
      yield {
        type: "assistant.final",
        request_id: "r1",
        answer: '<img src=x onerror="window.__pwned=1"> hello',
        sources: [{ source_id: "X-1", source_type: "documentation", title: "Bad link", uri: "javascript:alert(1)" }],
      };
      yield { type: "request.done", request_id: "r1" };
    };
    const { container } = render(<App stream={hostile} />);
    await screen.findByText("Payment service error BUG-4821");
    await user.type(screen.getByLabelText("Ask about this email", { selector: "textarea" }), "x{Enter}");
    await screen.findByText(/hello/);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.queryByRole("link", { name: "Bad link" })).not.toBeInTheDocument(); // unsafe URL is not linked
    expect(screen.getByText("Bad link")).toBeInTheDocument();
  });
});
