import { useCallback, useEffect, useState } from "react";
import { getCurrentEmailContext, subscribeToItemChanges } from "../outlook/getCurrentEmailContext";
import { MOCK_EMAILS } from "../outlook/mockEmails";
import type { EmailContext } from "../types/api";

export type EmailSource = "outlook" | "mock";
export type EmailStatus = "loading" | "ready" | "unavailable";

// Mock emails exist only for browser development.
const ALLOW_MOCK = import.meta.env.DEV;

export function useEmailContext() {
  const [email, setEmail] = useState<EmailContext | null>(null);
  const [status, setStatus] = useState<EmailStatus>("loading");
  const [source, setSource] = useState<EmailSource>("outlook");
  const [mockIndex, setMockIndex] = useState(0);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setEmail(await getCurrentEmailContext());
      setSource("outlook");
      setStatus("ready");
    } catch {
      if (ALLOW_MOCK) {
        setEmail(MOCK_EMAILS[0]?.email ?? null);
        setMockIndex(0);
        setSource("mock");
        setStatus("ready");
      } else {
        setEmail(null);
        setStatus("unavailable");
      }
    }
  }, []);

  useEffect(() => {
    void load();
    return subscribeToItemChanges(() => void load());
  }, [load]);

  const selectMock = useCallback((index: number) => {
    const entry = MOCK_EMAILS[index];
    if (!entry) return;
    setMockIndex(index);
    setEmail(entry.email);
  }, []);

  return { email, status, source, mockIndex, selectMock, mockLabels: MOCK_EMAILS.map((m) => m.label) };
}
