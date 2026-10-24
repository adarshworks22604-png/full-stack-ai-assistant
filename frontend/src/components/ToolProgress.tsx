import { Caption1, Spinner, makeStyles, tokens } from "@fluentui/react-components";
import { CheckmarkCircle20Regular, ErrorCircle20Regular } from "@fluentui/react-icons";
import type { ToolProgress as ToolProgressItem } from "../app/chatReducer";
import type { ToolName } from "../types/api";

const LABELS: Record<ToolName, string> = {
  get_bug_details: "Bug record",
  search_documentation: "Documentation",
};

const useStyles = makeStyles({
  list: { listStyleType: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: tokens.spacingVerticalXS },
  row: { display: "flex", alignItems: "center", gap: tokens.spacingHorizontalS },
  done: { color: tokens.colorPaletteGreenForeground1 },
  failed: { color: tokens.colorPaletteRedForeground1 },
});

export function ToolProgress({ tools }: { tools: ToolProgressItem[] }) {
  const styles = useStyles();
  if (tools.length === 0) return null;
  return (
    <ul className={styles.list} aria-label="Lookup progress">
      {tools.map((t) => (
        <li key={t.tool} className={styles.row}>
          {t.status === "running" && <Spinner size="extra-tiny" aria-label="In progress" />}
          {t.status === "done" && <CheckmarkCircle20Regular className={styles.done} aria-label="Done" />}
          {t.status === "failed" && <ErrorCircle20Regular className={styles.failed} aria-label="Failed" />}
          <Caption1>
            {LABELS[t.tool]}: {t.summary}
          </Caption1>
        </li>
      ))}
    </ul>
  );
}
