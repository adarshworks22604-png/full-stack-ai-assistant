import { Button, MessageBar, MessageBarActions, MessageBarBody, MessageBarTitle } from "@fluentui/react-components";

interface Props {
  title: string;
  message: string;
  intent?: "error" | "info" | "warning";
  onRetry?: () => void;
}

export function ErrorBanner({ title, message, intent = "error", onRetry }: Props) {
  return (
    <MessageBar intent={intent} role={intent === "error" ? "alert" : "status"}>
      <MessageBarBody>
        <MessageBarTitle>{title}</MessageBarTitle>
        {message}
      </MessageBarBody>
      {onRetry && (
        <MessageBarActions>
          <Button size="small" onClick={onRetry}>
            Try again
          </Button>
        </MessageBarActions>
      )}
    </MessageBar>
  );
}
