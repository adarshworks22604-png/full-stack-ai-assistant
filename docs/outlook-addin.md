# Outlook add-in (task pane)

## What it does
Opens beside a **read-mode message**, reads the subject and the start of the body through Office.js, and lets the
user ask questions about it. In Stage 2 the answers come from a **mock assistant with synthetic data**.

## Permissions
`<Permissions>ReadItem</Permissions>` and requirement set `Mailbox 1.8`.

| Need | Why | Not requested |
|---|---|---|
| Read the open message (subject, body text) | Detect bug IDs and give the assistant context | Read/write mailbox, send mail, calendar, contacts |

The user can turn off **Share this email with the assistant**; nothing from the email is then sent. Only the subject
and the first 4,000 characters of the body are ever included (`frontend/src/limits.ts`).

## Code map
| File | Role |
|---|---|
| `src/outlook/getCurrentEmailContext.ts` | The only Office.js access. Read mode only; limits body length |
| `src/outlook/mockEmails.ts` | Synthetic emails for browser development (dev builds only) |
| `src/app/chatReducer.ts` | Pure state machine: idle, submitting, streaming, enriching, complete, failed, cancelled |
| `src/services/mockChatStream.ts` | Mock SSE-style event stream. Replaced by the real client in Stage 4 |
| `src/hooks/useChat.ts` | Runs a stream, handles cancel, retry, disconnects |
| `src/components/*` | ChatInput, MessageList, AssistantMessage, EvidenceList, ToolProgress, ErrorBanner, EmailContextCard |

## Run in a browser (no Outlook needed)
`npm run dev`, then use the sample-email dropdown. Type `simulate error` as the question to see the error and retry state.

## Run inside Outlook (sideloading)
1. Install trusted localhost certificates once: `npx office-addin-dev-certs install`
2. `npm run dev` and confirm `https://localhost:3000/index.html` opens without a certificate warning.
3. Validate the manifest: `npx office-addin-manifest validate public/manifest.xml`
4. Sideload `public/manifest.xml` into a **test mailbox** (never a real work mailbox with real mail).
   Follow the current Microsoft guide: https://learn.microsoft.com/office/dev/add-ins/outlook/sideload-outlook-add-ins-for-testing
5. Open a message and click **Engineering Assistant** in the ribbon.

## Status of verification
- Verified by automated tests in a simulated browser (jsdom): state transitions, UI flows, Office.js adapter with a faked `Office` object.
- **Not yet verified:** loading in a real Outlook client and `office-addin-manifest validate`. Do this before calling Stage 2 final.

## Known limitations (Stage 2)
- Mock assistant only; no backend, no authentication.
- Read mode only. Compose mode shows "No message open".
- Placeholder icons. The manifest points at `https://localhost:3000`; production URLs come in Stage 10.
