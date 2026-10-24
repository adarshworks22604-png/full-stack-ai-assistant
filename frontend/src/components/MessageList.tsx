import { Body1, Button, Subtitle2, makeStyles, tokens } from "@fluentui/react-components";
import { useEffect, useRef } from "react";
import type { ChatMessage } from "../app/chatReducer";
import { AssistantMessageView } from "./AssistantMessage";

const SUGGESTIONS = [
  "What is the likely cause and fix?",
  "What is the current status of this bug?",
  "Find related documentation.",
];

const useStyles = makeStyles({
  root: {
    flex: 1,
    overflowY: "auto",
    padding: tokens.spacingHorizontalM,
    display: "flex",
    flexDirection: "column",
    gap: tokens.spacingVerticalL,
  },
  user: {
    alignSelf: "flex-end",
    maxWidth: "90%",
    backgroundColor: tokens.colorBrandBackground2,
    color: tokens.colorNeutralForeground1,
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalM}`,
    borderRadius: tokens.borderRadiusLarge,
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
  },
  empty: { display: "flex", flexDirection: "column", gap: tokens.spacingVerticalS, alignItems: "flex-start" },
});

interface Props {
  messages: ChatMessage[];
  busy: boolean;
  onSuggest: (text: string) => void;
  onRetry: () => void;
}

export function MessageList({ messages, busy, onSuggest, onRetry }: Props) {
  const styles = useStyles();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);

  return (
    <div className={styles.root} role="log" aria-live="polite" aria-label="Conversation">
      {messages.length === 0 && (
        <div className={styles.empty}>
          <Subtitle2>Ask about this email</Subtitle2>
          <Body1>I look up bug IDs and documentation, and tell you what each source says.</Body1>
          {SUGGESTIONS.map((s) => (
            <Button key={s} appearance="outline" size="small" disabled={busy} onClick={() => onSuggest(s)}>
              {s}
            </Button>
          ))}
        </div>
      )}
      {messages.map((m) =>
        m.role === "user" ? (
          <div key={m.id} className={styles.user}>
            {m.text}
          </div>
        ) : (
          <AssistantMessageView key={m.id} message={m} onRetry={onRetry} />
        ),
      )}
      <div ref={endRef} />
    </div>
  );
}
