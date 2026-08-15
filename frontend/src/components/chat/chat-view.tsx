"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Globe, Loader2, Send, Square } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Message, type ChatMsg } from "@/components/chat/message";
import { researchApi } from "@/lib/client";
import { streamChat } from "@/lib/stream";

const SUGGESTIONS = [
  "Explain convolutional neural networks",
  "What is a foreign key in SQL?",
  "How does gradient descent work?",
  "Summarize the key ideas of k-means clustering",
];

export function ChatView({ chatId: initialChatId, initialMessages = [] }: {
  chatId?: number;
  initialMessages?: ChatMsg[];
}) {
  const [messages, setMessages] = useState<ChatMsg[]>(initialMessages);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [chatId, setChatId] = useState<number | undefined>(initialChatId);
  const [webPrompt, setWebPrompt] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const qc = useQueryClient();

  // keep a live ref of messages for use inside streaming callbacks
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  useEffect(() => setMessages(initialMessages), [initialChatId]); // eslint-disable-line
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const patchLast = (patch: Partial<ChatMsg>) =>
    setMessages((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, ...patch } : x)));
  const appendToLast = (t: string) =>
    setMessages((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, content: x.content + t } : x)));

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    setInput("");
    setWebPrompt(null);
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: question },
      { id: `a-${Date.now()}`, role: "assistant", content: "", streaming: true }]);
    setBusy(true);
    const ac = new AbortController();
    abortRef.current = ac;
    await streamChat(question, chatId ?? null, {
      onToken: (t) => appendToLast(t),
      onFinal: (final) => patchLast({ data: final, streaming: false }),
      onDone: (info) => {
        const newId = info.chat_id as number | undefined;
        if (!chatId && newId) {
          setChatId(newId);
          window.history.replaceState(null, "", `/chat/${newId}`);
        }
        qc.invalidateQueries({ queryKey: ["chats"] });
      },
      onError: () => patchLast({ content: "Sorry — something went wrong.", streaming: false }),
    }, ac.signal);
    setBusy(false);
    const last = messagesRef.current.at(-1);
    if (last?.data?.needs_web) setWebPrompt(question);
  }

  function stop() {
    abortRef.current?.abort();
    setBusy(false);
    patchLast({ streaming: false });
  }

  async function approveWeb() {
    if (!webPrompt) return;
    const question = webPrompt;
    setWebPrompt(null);
    setBusy(true);
    setMessages((m) => [...m, { id: `a-${Date.now()}`, role: "assistant", content: "Searching the web…", streaming: true }]);
    try {
      const r = await researchApi.ask(question, false);
      patchLast({ content: r.answer, streaming: false,
        data: { confidence: r.confidence, used_web: r.used_web, generator: "research",
          citations: (r.sources ?? []).map((s: any, i: number) => ({ cid: `W${i + 1}`, label: s.domain || s.title, source_type: "web", locator: "", link: s.url, resolvable: !!s.url })) } });
    } finally {
      setBusy(false);
    }
  }

  const empty = messages.length === 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        {empty ? (
          <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center px-4 text-center">
            <Logo size={44} withWordmark={false} />
            <h1 className="mt-4 text-2xl font-semibold tracking-tight">How can I help you learn today?</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Ask anything about your courses. Every answer is grounded in your Knowledge Base with citations.
            </p>
            <div className="mt-6 grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}
                  className="rounded-lg border bg-card p-3 text-left text-sm text-card-foreground shadow-soft transition-colors hover:border-primary/40 hover:bg-accent">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-5 px-4 py-6">
            {messages.map((m) => <Message key={m.id} msg={m} />)}
            {webPrompt && (
              <div className="animate-fade-in rounded-lg border border-primary/30 bg-accent p-4">
                <p className="flex items-center gap-2 text-sm font-medium text-accent-foreground">
                  <Globe className="h-4 w-4" /> This answer requires Web Search.
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Confidence is low. Search the web and merge trusted sources? Nothing is saved without your approval.
                </p>
                <div className="mt-3 flex gap-2">
                  <Button size="sm" onClick={approveWeb}>Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => setWebPrompt(null)}>Cancel</Button>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div className="border-t bg-background/80 backdrop-blur">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <div className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-card">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
              placeholder="Ask Digiler AI…"
              rows={1}
              className="border-0 shadow-none focus-visible:ring-0"
            />
            {busy ? (
              <Button size="icon" variant="secondary" onClick={stop} aria-label="Stop">
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button size="icon" onClick={() => send(input)} disabled={!input.trim()} aria-label="Send">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            )}
          </div>
          <p className="mt-1.5 text-center text-xs text-muted-foreground">
            Answers are grounded in your Knowledge Base and cited. Web search runs only with your approval.
          </p>
        </div>
      </div>
    </div>
  );
}
