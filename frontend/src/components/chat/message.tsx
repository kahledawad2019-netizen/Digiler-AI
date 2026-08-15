"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, ChevronDown, Copy, FileText, Film, Presentation } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Answer, Citation, Evidence } from "@/types";

const ICON: Record<string, typeof FileText> = { pdf: FileText, slide: Presentation, video: Film };

function confidenceTone(c: number): "success" | "warning" | "secondary" {
  return c >= 0.7 ? "success" : c >= 0.5 ? "warning" : "secondary";
}

export interface ChatMsg {
  id: string | number;
  role: "user" | "assistant";
  content: string;
  data?: Partial<Answer>;
  streaming?: boolean;
}

export function Message({ msg }: { msg: ChatMsg }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const data = msg.data;

  if (msg.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground shadow-soft">
          {msg.content}
        </div>
      </div>
    );
  }

  const copy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="animate-fade-in space-y-2">
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm border bg-card px-4 py-3 shadow-soft">
        <div className="prose-answer text-card-foreground">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content || "…"}</ReactMarkdown>
          {msg.streaming && <span className="typing-dot text-primary">▍</span>}
        </div>

        {!msg.streaming && data && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-2.5">
            {typeof data.confidence === "number" && (
              <Badge variant={confidenceTone(data.confidence)}>
                Confidence {Math.round(data.confidence * 100)}%
              </Badge>
            )}
            {data.generator && <Badge variant="secondary">{data.generator}</Badge>}
            {(data.citations?.length ?? 0) > 0 && (
              <button
                onClick={() => setOpen((v) => !v)}
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                {data.citations!.length} sources <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
              </button>
            )}
            <button onClick={copy} className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} Copy
            </button>
          </div>
        )}

        {open && data && <Sources citations={data.citations ?? []} evidence={data.evidence ?? []} />}
      </div>
    </div>
  );
}

function Sources({ citations, evidence }: { citations: Citation[]; evidence: Evidence[] }) {
  return (
    <div className="mt-3 space-y-2 rounded-lg bg-muted/60 p-3">
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c) => {
          const Icon = ICON[c.source_type] ?? FileText;
          const inner = (
            <span className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2 py-1 text-xs">
              <Icon className="h-3 w-3 text-primary" />
              <span className="font-medium">[{c.cid}]</span>
              <span className="max-w-[160px] truncate text-muted-foreground">{c.label}</span>
              {c.locator && <span className="text-primary">{c.locator}</span>}
            </span>
          );
          return c.resolvable && c.link ? (
            <a key={c.cid} href={c.link} target="_blank" rel="noreferrer" className="hover:opacity-80">{inner}</a>
          ) : (
            <span key={c.cid}>{inner}</span>
          );
        })}
      </div>
      {evidence.slice(0, 4).map((e, i) => (
        <div key={i} className="rounded-md border bg-background p-2 text-xs">
          <p className="mb-1 font-medium text-muted-foreground">{e.citation || e.resource_id}</p>
          <p className="line-clamp-3 text-foreground/80">{e.text}</p>
        </div>
      ))}
    </div>
  );
}
