import { Caption1, Link, Text, makeStyles, tokens } from "@fluentui/react-components";
import { Bug20Regular, Document20Regular } from "@fluentui/react-icons";
import type { Source } from "../types/api";
import { safeUrl } from "../utils/safeUrl";

const useStyles = makeStyles({
  list: { listStyleType: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: tokens.spacingVerticalXS },
  item: { display: "flex", alignItems: "flex-start", gap: tokens.spacingHorizontalS },
  icon: { color: tokens.colorNeutralForeground3, flexShrink: 0, marginTop: "2px" },
  text: { display: "flex", flexDirection: "column", minWidth: 0 },
});

export function EvidenceList({ sources, label }: { sources: Source[]; label: string }) {
  const styles = useStyles();
  if (sources.length === 0) return null;
  return (
    <section aria-label={label}>
      <Caption1>{label}</Caption1>
      <ul className={styles.list}>
        {sources.map((s) => {
          const href = safeUrl(s.uri);
          return (
            <li key={s.source_id} className={styles.item}>
              <span className={styles.icon} aria-hidden>
                {s.source_type === "bug" ? <Bug20Regular /> : <Document20Regular />}
              </span>
              <span className={styles.text}>
                {href ? (
                  <Link href={href} target="_blank" rel="noopener noreferrer">
                    {s.title}
                  </Link>
                ) : (
                  <Text>{s.title}</Text>
                )}
                <Caption1>{s.source_id}</Caption1>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
