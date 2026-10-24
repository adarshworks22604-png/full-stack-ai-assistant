import { afterEach, describe, expect, it, vi } from "vitest";
import { MAX_EMAIL_BODY_CHARS } from "../src/limits";
import {
  EmailContextUnavailableError,
  getCurrentEmailContext,
  isOutlookItemOpen,
  limitBody,
} from "../src/outlook/getCurrentEmailContext";

function stubOffice(item: unknown, bodyResult: { status: string; value?: string } = { status: "succeeded", value: "" }) {
  vi.stubGlobal("Office", {
    context: { mailbox: { item } },
    CoercionType: { Text: "text" },
    AsyncResultStatus: { Succeeded: "succeeded", Failed: "failed" },
  });
  return bodyResult;
}

afterEach(() => vi.unstubAllGlobals());

describe("limitBody", () => {
  it("collapses blank lines and trims", () => {
    expect(limitBody("a\r\n\r\n\r\n\r\nb  \n")).toBe("a\n\nb");
  });
  it("caps the length", () => {
    expect(limitBody("x".repeat(MAX_EMAIL_BODY_CHARS + 500))).toHaveLength(MAX_EMAIL_BODY_CHARS);
  });
});

describe("getCurrentEmailContext", () => {
  it("throws when Office is not available (plain browser)", async () => {
    await expect(getCurrentEmailContext()).rejects.toBeInstanceOf(EmailContextUnavailableError);
    expect(isOutlookItemOpen()).toBe(false);
  });

  it("throws in compose mode (subject is an object)", async () => {
    stubOffice({ subject: { getAsync: () => {} } });
    await expect(getCurrentEmailContext()).rejects.toBeInstanceOf(EmailContextUnavailableError);
  });

  it("returns subject and a length-limited body in read mode", async () => {
    const long = "y".repeat(MAX_EMAIL_BODY_CHARS * 2);
    stubOffice({
      subject: "BUG-4821 timeouts",
      itemId: "item-1",
      body: { getAsync: (_t: string, cb: (r: unknown) => void) => cb({ status: "succeeded", value: long }) },
    });
    const ctx = await getCurrentEmailContext();
    expect(ctx.subject).toBe("BUG-4821 timeouts");
    expect(ctx.itemId).toBe("item-1");
    expect(ctx.bodyText).toHaveLength(MAX_EMAIL_BODY_CHARS);
  });

  it("rejects when the body cannot be read", async () => {
    stubOffice({
      subject: "s",
      body: { getAsync: (_t: string, cb: (r: unknown) => void) => cb({ status: "failed" }) },
    });
    await expect(getCurrentEmailContext()).rejects.toThrow("Could not read the message body.");
  });
});
