import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { fetchMessages, sendMessage } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest } from "../../types/cleaning";
import { useAuth } from "../auth/AuthContext";

const QUICK: Record<string, string[]> = {
  STUDENT: ["I am in my room.", "Please knock, I may not hear the bell."],
  WORKER: ["I am on my way.", "I am at your door."],
  SUPERVISOR: ["I am looking into this."],
};

export function TaskChat({ request }: { request: CleaningRequest }) {
  const queryClient = useQueryClient();
  const role = useAuth().user?.role ?? "STUDENT";
  const [text, setText] = useState("");
  const end = useRef<HTMLLIElement>(null);
  const chat = request.chat!;
  const key = ["cleaning", "messages", request.id];
  const { data, error } = useQuery({
    queryKey: key,
    queryFn: () => fetchMessages(request.id),
    refetchInterval: chat.can_send ? 5_000 : false,
  });
  const send = useMutation({
    mutationFn: (body: string) => sendMessage(request.id, body),
    onSuccess: () => setText(""),
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const messages = data?.messages ?? [];
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages.length]);

  return (
    <section className="chat" aria-label="Task chat">
      <h3>Chat about this room</h3>
      {error && (
        <ErrorMessage error={error} fallback="Could not load the chat." />
      )}
      {data && messages.length === 0 && (
        <p className="muted">No messages yet.</p>
      )}
      {messages.length > 0 && (
        <ol className="chat__list">
          {messages.map((message) => (
            <li
              key={message.id}
              className={`chat__item${message.mine ? " chat__item--mine" : ""}`}
            >
              <span className="chat__meta">
                {message.mine ? "You" : message.sender.name} ·{" "}
                {message.time_label}
              </span>
              <p>{message.body}</p>
            </li>
          ))}
          <li ref={end} aria-hidden="true" />
        </ol>
      )}
      {chat.note && <p className="muted">{chat.note}</p>}
      {chat.can_send && (
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) send.mutate(text);
          }}
        >
          <div className="choice-row">
            {(QUICK[role] ?? []).map((line) => (
              <button
                key={line}
                type="button"
                className="btn btn--ghost btn--small"
                disabled={send.isPending}
                onClick={() => send.mutate(line)}
              >
                {line}
              </button>
            ))}
          </div>
          <label className="text-field">
            Message
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={500}
              rows={2}
            />
          </label>
          <div className="choice-row">
            <button
              type="submit"
              className="btn btn--primary"
              disabled={!text.trim() || send.isPending}
            >
              {send.isPending ? "Sending…" : "Send"}
            </button>
          </div>
          {send.isError && (
            <ErrorMessage
              error={send.error}
              fallback="Could not send. Try again."
            />
          )}
        </form>
      )}
    </section>
  );
}
