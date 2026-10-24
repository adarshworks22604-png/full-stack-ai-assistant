import { Caption1, Select, Switch, Text, makeStyles, tokens } from "@fluentui/react-components";
import type { EmailSource } from "../hooks/useEmailContext";
import type { EmailContext } from "../types/api";
import { ErrorBanner } from "./ErrorBanner";

const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    gap: tokens.spacingVerticalXS,
    padding: tokens.spacingHorizontalM,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  subject: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
});

interface Props {
  status: "loading" | "ready" | "unavailable";
  email: EmailContext | null;
  source: EmailSource;
  include: boolean;
  onIncludeChange: (value: boolean) => void;
  mockLabels: string[];
  mockIndex: number;
  onSelectMock: (index: number) => void;
}

export function EmailContextCard(p: Props) {
  const styles = useStyles();

  if (p.status === "unavailable") {
    return (
      <div className={styles.root}>
        <ErrorBanner
          intent="info"
          title="No message open"
          message="Open a message in Outlook, then open this assistant from the ribbon."
        />
      </div>
    );
  }

  return (
    <div className={styles.root}>
      {p.source === "mock" && (
        <Select
          aria-label="Sample email (development only)"
          value={p.mockLabels[p.mockIndex]}
          onChange={(e) => p.onSelectMock(e.target.selectedIndex)}
        >
          {p.mockLabels.map((l) => (
            <option key={l}>{l}</option>
          ))}
        </Select>
      )}
      <Text weight="semibold" className={styles.subject} title={p.email?.subject}>
        {p.status === "loading" ? "Reading the open message…" : p.email?.subject || "(no subject)"}
      </Text>
      <Switch
        checked={p.include}
        onChange={(_, d) => p.onIncludeChange(d.checked)}
        label="Share this email with the assistant"
      />
      <Caption1>
        {p.include
          ? "Only the subject and the start of the body are sent."
          : "The email is not shared. I can only answer from what you type."}
      </Caption1>
    </div>
  );
}
