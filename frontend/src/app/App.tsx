import { FluentProvider, Subtitle1, makeStyles, tokens, webDarkTheme, webLightTheme } from "@fluentui/react-components";
import { useMemo, useState } from "react";
import { ChatInput } from "../components/ChatInput";
import { EmailContextCard } from "../components/EmailContextCard";
import { MessageList } from "../components/MessageList";
import { useChat } from "../hooks/useChat";
import { useDarkMode } from "../hooks/useColorScheme";
import { useEmailContext } from "../hooks/useEmailContext";
import { createMockChatStream } from "../services/mockChatStream";
import type { ChatStream } from "../types/api";
import { isActive } from "./chatReducer";

const useStyles = makeStyles({
  root: { display: "flex", flexDirection: "column", height: "100vh", backgroundColor: tokens.colorNeutralBackground1 },
  header: { padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalM} 0` },
});

export function App({ stream }: { stream?: ChatStream }) {
  const styles = useStyles();
  const dark = useDarkMode();
  const defaultStream = useMemo(() => createMockChatStream(), []);
  const chat = useChat(stream ?? defaultStream);
  const emailCtx = useEmailContext();
  const [includeEmail, setIncludeEmail] = useState(true);

  const emailToSend = includeEmail ? emailCtx.email : null;
  const busy = isActive(chat.status);

  return (
    <FluentProvider theme={dark ? webDarkTheme : webLightTheme}>
      <div className={styles.root}>
        <header className={styles.header}>
          <Subtitle1 as="h1">Engineering assistant</Subtitle1>
        </header>
        <EmailContextCard
          status={emailCtx.status}
          email={emailCtx.email}
          source={emailCtx.source}
          include={includeEmail}
          onIncludeChange={setIncludeEmail}
          mockLabels={emailCtx.mockLabels}
          mockIndex={emailCtx.mockIndex}
          onSelectMock={emailCtx.selectMock}
        />
        <MessageList
          messages={chat.messages}
          busy={busy}
          onSuggest={(text) => void chat.send(text, emailToSend)}
          onRetry={() => chat.retry(emailToSend)}
        />
        <ChatInput
          busy={busy}
          disabled={emailCtx.status === "unavailable"}
          onSend={(text) => void chat.send(text, emailToSend)}
          onCancel={chat.cancel}
        />
      </div>
    </FluentProvider>
  );
}
