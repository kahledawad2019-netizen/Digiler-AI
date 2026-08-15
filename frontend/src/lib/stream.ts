import { authStore } from "@/store/auth";
import type { Answer } from "@/types";

interface StreamHandlers {
  onToken: (text: string) => void;
  onFinal: (final: Partial<Answer>) => void;
  onDone: (info: Record<string, unknown>) => void;
  onError?: (err: unknown) => void;
}

function authHeaders(json = true): Record<string, string> {
  const token = authStore.getState().accessToken;
  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/** Base URL for STREAMING requests.
 *
 *  The Next.js dev rewrite proxy BUFFERS SSE responses (headers are held and every token
 *  arrives in one burst at the end), which makes streaming answers look dead in the browser.
 *  So streaming must talk directly to the backend origin, which streams incrementally and is
 *  CORS-enabled for the frontend origin. In production (served same-origin behind nginx, which
 *  streams fine) this resolves to a relative URL. Non-streaming JSON keeps using the proxy. */
function streamBase(): string {
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (env) return env.replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location.port === "3000") {
    // standard dev setup: frontend :3000 → backend :8000 (bypass the buffering proxy)
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return ""; // production: same-origin through nginx
}

/** Read an SSE (fetch) body and dispatch token / final / done events. Shared by every
 *  streaming endpoint so long-running LLM generation never blocks or resets a socket. */
async function pumpSSE(res: Response, handlers: StreamHandlers): Promise<void> {
  if (!res.ok || !res.body) {
    handlers.onError?.(new Error(`stream failed: ${res.status}`));
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (frame: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    let payload: any;
    try {
      payload = JSON.parse(dataLines.join("\n"));
    } catch {
      return;
    }
    if (event === "done") handlers.onDone(payload);
    else if (payload.type === "token") handlers.onToken(payload.text ?? "");
    else if (payload.type === "final") handlers.onFinal(payload);
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        if (frame.trim()) dispatch(frame);
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") handlers.onError?.(err);
  }
}

/** Stream a grounded answer token-by-token from POST /api/chat/stream. */
export async function streamChat(
  message: string,
  chatId: number | null | undefined,
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${streamBase()}/api/chat/stream`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ message, chat_id: chatId ?? null }),
    signal,
  });
  await pumpSSE(res, handlers);
}

/** Stream a retrieval-grounded summary of a resource (SSE) — no proxy timeout. */
export async function streamSummary(
  resourceId: string,
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(
    `${streamBase()}/api/knowledge/resource/${encodeURIComponent(resourceId)}/summarize/stream`,
    { method: "POST", headers: authHeaders(), signal }
  );
  await pumpSSE(res, handlers);
}
