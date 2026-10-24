import { Button, Caption1, Textarea, makeStyles, tokens } from "@fluentui/react-components";
import { Send20Regular, Stop20Regular } from "@fluentui/react-icons";
import { useEffect, useRef, useState } from "react";
import { MAX_MESSAGE_CHARS } from "../limits";

const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    gap: tokens.spacingVerticalXS,
    padding: tokens.spacingHorizontalM,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  row: { display: "flex", gap: tokens.spacingHorizontalS, alignItems: "flex-end" },
  field: { flex: 1 },
});

interface Props {
  busy: boolean;
  disabled?: boolean;
  onSend: (text: string) => void;
  onCancel: () => void;
}

export function ChatInput({ busy, disabled = false, onSend, onCancel }: Props) {
  const styles = useStyles();
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const wasBusy = useRef(false);

  // Return focus to the input when an answer finishes.
  useEffect(() => {
    if (wasBusy.current && !busy) ref.current?.focus();
    wasBusy.current = busy;
  }, [busy]);

  const canSend = !busy && !disabled && value.trim().length > 0;

  const submit = () => {
    if (!canSend) return;
    onSend(value);
    setValue("");
  };

  return (
    <div className={styles.root}>
      <div className={styles.row}>
        <Textarea
          ref={ref}
          className={styles.field}
          aria-label="Ask about this email"
          placeholder="Ask about this email"
          resize="none"
          rows={2}
          maxLength={MAX_MESSAGE_CHARS}
          value={value}
          disabled={disabled}
          onChange={(_, data) => setValue(data.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {busy ? (
          <Button icon={<Stop20Regular />} onClick={onCancel} aria-label="Stop">
            Stop
          </Button>
        ) : (
          <Button appearance="primary" icon={<Send20Regular />} disabled={!canSend} onClick={submit} aria-label="Send" />
        )}
      </div>
      <Caption1>Enter to send, Shift+Enter for a new line</Caption1>
    </div>
  );
}

