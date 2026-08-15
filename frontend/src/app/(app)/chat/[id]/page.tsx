"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChatView } from "@/components/chat/chat-view";
import { chatApi } from "@/lib/client";
import type { ChatMsg } from "@/components/chat/message";

export default function ChatByIdPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const chatId = Number(id);
  const { data, isLoading } = useQuery({
    queryKey: ["chat", chatId],
    queryFn: () => chatApi.messages(chatId),
  });

  if (isLoading) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;

  const initial: ChatMsg[] = (data ?? []).map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    data: m.data,
  }));

  return <ChatView chatId={chatId} initialMessages={initial} />;
}
