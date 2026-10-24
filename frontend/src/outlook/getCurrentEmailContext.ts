import { MAX_EMAIL_BODY_CHARS } from "../limits";
import type { EmailContext } from "../types/api";

export class EmailContextUnavailableError extends Error {
  constructor(message = "No readable Outlook message is open.") {
    super(message);
    this.name = "EmailContextUnavailableError";
  }
}

function currentItem(): Office.MessageRead | undefined {
  if (typeof Office === "undefined") return undefined;
  const item = Office.context?.mailbox?.item;
  // Read mode exposes subject as a plain string; compose mode exposes an object.
  if (!item || typeof (item as Office.MessageRead).subject !== "string") return undefined;
  return item as Office.MessageRead;
}

export function isOutlookItemOpen(): boolean {
  return currentItem() !== undefined;
}

/** Collapse runaway whitespace and cap the length so only the minimum is shared. */
export function limitBody(text: string, max = MAX_EMAIL_BODY_CHARS): string {
  const cleaned = text.replace(/\r\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  return cleaned.length > max ? cleaned.slice(0, max) : cleaned;
}

function readBodyText(item: Office.MessageRead): Promise<string> {
  return new Promise((resolve, reject) => {
    item.body.getAsync(Office.CoercionType.Text, (result) => {
      if (result.status === Office.AsyncResultStatus.Succeeded) resolve(result.value ?? "");
      else reject(new Error("Could not read the message body."));
    });
  });
}

/** The only place in the app that talks to Office.js for the open message. */
export async function getCurrentEmailContext(): Promise<EmailContext> {
  const item = currentItem();
  if (!item) throw new EmailContextUnavailableError();
  const body = await readBodyText(item);
  return { subject: item.subject, bodyText: limitBody(body), itemId: item.itemId };
}

/** Calls back when the user selects a different message while the pane stays pinned. */
export function subscribeToItemChanges(onChange: () => void): () => void {
  if (typeof Office === "undefined" || !Office.context?.mailbox?.addHandlerAsync) return () => {};
  const mailbox = Office.context.mailbox;
  mailbox.addHandlerAsync(Office.EventType.ItemChanged, onChange);
  return () => {
    mailbox.removeHandlerAsync?.(Office.EventType.ItemChanged, onChange);
  };
}
