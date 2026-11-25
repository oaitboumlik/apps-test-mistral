import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useRef, useState } from "react";

import { useAppName } from "../app-name";
import { unwrap } from "../api/unwrap";
import { v1Chat } from "../api/generated/sdk.gen";

type ChatRole = "user" | "assistant";

interface ChatTurn {
  role: ChatRole;
  content: string;
}

const Chat = () => {
  const appName = useAppName();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [state, setState] = useState<"idle" | "thinking" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const busy = state === "thinking";

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) {
      return;
    }

    const history: ChatTurn[] = [...turns, { role: "user", content: text }];
    setDraft("");
    setTurns(history);
    setError(null);
    setState("thinking");

    try {
      const data = await unwrap(
        v1Chat({
          body: { messages: history.map(({ role, content }) => ({ role, content })) },
          throwOnError: true,
        }),
      );
      setTurns([...history, { role: "assistant", content: data.content }]);
      setState("idle");
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "The request failed.");
    } finally {
      requestAnimationFrame(() => {
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
      });
    }
  };

  const status = useMemo(() => {
    if (state === "thinking") {
      return "Thinking…";
    }
    if (state === "error") {
      return error ?? "The request failed.";
    }
    return null;
  }, [state, error]);

  return (
    <main className="mx-auto flex h-full max-w-2xl flex-col gap-2 p-4">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">{appName}</h1>
        <Link className="text-sm underline" to="/weather">
          ← World weather map
        </Link>
      </header>
      <p className="text-xs opacity-60">Ask anything about the weather — for example: “What's the weather in Casablanca?”</p>
      <div ref={listRef} className="min-h-0 flex-1 space-y-2 overflow-y-auto rounded-lg border p-4">
        {turns.length === 0 ? (
          <p className="text-sm opacity-60">Say hello to start chatting with mistral-small-latest.</p>
        ) : null}
        {turns.map((turn, index) => (
          <div key={index} className={turn.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <p
              className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-3 py-2 ${
                turn.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
              }`}
            >
              {turn.content}
            </p>
          </div>
        ))}
      </div>
      {status ? <p className="px-1 text-xs opacity-70">{status}</p> : null}
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <input
          className="flex-1 rounded-lg border px-3 py-2"
          placeholder="Type a message…"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={busy}
        />
        <button
          type="submit"
          className="rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50"
          disabled={busy || draft.trim().length === 0}
        >
          Send
        </button>
      </form>
    </main>
  );
};

export const Route = createFileRoute("/chat")({
  component: Chat,
});
