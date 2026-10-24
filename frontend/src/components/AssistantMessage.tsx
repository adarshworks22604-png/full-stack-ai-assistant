import { Badge, Body1, Caption1, Spinner, makeStyles, tokens } from "@fluentui/react-components";
import { isActive } from "../app/chatReducer";
import type { AssistantMessage } from "../app/chatReducer";
import { ErrorBanner } from "./ErrorBanner";
import { EvidenceList } from "./EvidenceList";
import { ToolProgress } from "./ToolProgress";

const useStyles = makeStyles({
  root: { display: "flex", flexDirection: "column", gap: tokens.spacingVerticalS },
  text: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
  limits: { margin: 0, paddingLeft: tokens.spacingHorizontalL },
  waiting: { display: "flex", alignItems: "center", gap: tokens.spacingHorizontalS },
});

function StatusBadge({ message }: { message: AssistantMessage }) {
  if (message.status === "complete") {
    return message.sources.length > 0 ? (
      <Badge appearance="tint" color="success">Checked against sources</Badge>
    ) : (
      <Badge appearance="tint" color="informative">No sources found</Badge>
    );
  }
  if (isActive(message.status) && message.preliminaryText) {
    return <Badge appearance="tint" color="warning">Preliminary: still verifying</Badge>;
  }
  return null;
}

export function AssistantMessageView({ message, onRetry }: { message: AssistantMessage; onRetry: () => void }) {
  const styles = useStyles();
  const active = isActive(message.status);
  const text = message.finalText ?? message.preliminaryText;

  return (
    <article className={styles.root} aria-busy={active} aria-label="Assistant answer">
      <StatusBadge message={message} />

      {text ? (
        <Body1 className={styles.text}>{text}</Body1>
      ) : (
        active && (
          <div className={styles.waiting}>
            <Spinner size="tiny" />
            <Caption1>Reading the email…</Caption1>
          </div>
        )
      )}

      {active && <ToolProgress tools={message.tools} />}

      {message.status === "complete" && message.limitations.length > 0 && (
        <section aria-label="Limits of this answer">
          <Caption1>Limits of this answer</Caption1>
          <ul className={styles.limits}>
            {message.limitations.map((l) => (
              <li key={l}>
                <Caption1>{l}</Caption1>
              </li>
            ))}
          </ul>
        </section>
      )}

      {message.status === "complete" ? (
        <EvidenceList sources={message.sources} label="Sources" />
      ) : (
        <EvidenceList sources={message.evidence} label="Found so far" />
      )}

      {message.status === "failed" && message.error && (
        <ErrorBanner
          title="Something went wrong"
          message={message.error.message}
          onRetry={message.error.retryable ? onRetry : undefined}
        />
      )}

      {message.status === "cancelled" && (
        <ErrorBanner title="Stopped" message="You stopped this answer." intent="info" onRetry={onRetry} />
      )}
    </article>
  );
}
