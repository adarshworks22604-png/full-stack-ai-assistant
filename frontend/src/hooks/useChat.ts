import { useCallback, useReducer, useRef } from "react";
import { chatReducer, initialChatState, selectLastUserText, selectStatus } from "../app/chatReducer";
import { toChatRequest } from "../types/api";
import type { ChatStream, EmailContext } from "../types/api";

let idCounter = 0;
const newId = () => `msg-${++idCounter}`;

export function useChat(stream: ChatStream) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const stateRef = useRef(state);
  stateRef.current = state;
  const controllerRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (text: string, email: EmailContext | null) => {
      const trimmed = text.trim();
      if (!trimmed || controllerRef.current) return; // empty or already running
      const controller = new AbortController();
      controllerRef.current = controller;
      dispatch({ type: "submit", userId: newId(), assistantId: newId(), text: trimmed });
      try {
        for await (const event of stream(toChatRequest(trimmed, email), controller.signal)) {
          if (controller.signal.aborted) return;
          dispatch({ type: "event", event });
        }
        if (!controller.signal.aborted) dispatch({ type: "stream_closed" });
      } catch {
        if (!controller.signal.aborted) {
          dispatch({
            type: "connection_failed",
            error: {
              code: "STREAM_DISCONNECTED",
              message: "Couldn't reach the assistant. Check your connection and try again.",
              retryable: true,
            },
          });
        }
      } finally {
        if (controllerRef.current === controller) controllerRef.current = null;
      }
    },
    [stream],
  );

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    dispatch({ type: "cancel" });
  }, []);

  const retry = useCallback(
    (email: EmailContext | null) => {
      const text = selectLastUserText(stateRef.current);
      if (!text || controllerRef.current) return;
      dispatch({ type: "discard_last_turn" });
      void send(text, email);
    },
    [send],
  );

  return { messages: state.messages, status: selectStatus(state), send, cancel, retry };
}
