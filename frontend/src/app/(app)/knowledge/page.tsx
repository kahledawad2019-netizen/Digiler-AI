"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FileText, Film, Loader2, Notebook, Presentation, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { knowledgeApi, quizApi, uploadApi } from "@/lib/client";
import { streamSummary } from "@/lib/stream";
import { QuizRunner } from "@/components/quiz/quiz-runner";
import { cn, formatCourse, formatTitle } from "@/lib/utils";
import type { ResourceNode } from "@/types";

const DOC_ICON: Record<string, typeof FileText> = {
  reference: FileText, textbook: FileText, lesson_page: FileText,
  lecture_slides: Presentation, video: Film, notebook: Notebook,
};

export default function KnowledgePage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["knowledge-tree"], queryFn: knowledgeApi.tree });
  const [openCourse, setOpenCourse] = useState<string | null>(null);
  const [selected, setSelected] = useState<ResourceNode | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => uploadApi.upload(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge-tree"] }),
  });

  return (
    <div className="flex h-full">
      <div className="flex w-80 shrink-0 flex-col border-r">
        <div className="flex h-14 items-center justify-between border-b px-4">
          <h2 className="text-sm font-semibold">Knowledge Base</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {isLoading && <p className="p-3 text-sm text-muted-foreground">Loading…</p>}
          {data?.courses.map((course) => (
            <div key={course.course} className="mb-1">
              <button
                onClick={() => setOpenCourse(openCourse === course.course ? null : course.course)}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium hover:bg-accent"
              >
                <ChevronRight className={cn("h-4 w-4 transition-transform", openCourse === course.course && "rotate-90")} />
                <span className="truncate">{formatCourse(course.course)}</span>
              </button>
              {openCourse === course.course && (
                <div className="ml-4 border-l pl-2">
                  {course.modules.map((mod) => (
                    <div key={mod.module} className="py-1">
                      <p className="px-2 py-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{formatTitle(mod.module)}</p>
                      {mod.resources.map((r) => {
                        const Icon = DOC_ICON[r.doc_type] ?? FileText;
                        return (
                          <button
                            key={r.resource_id}
                            onClick={() => setSelected(r)}
                            className={cn(
                              "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent",
                              selected?.resource_id === r.resource_id && "bg-accent text-accent-foreground"
                            )}
                          >
                            <Icon className="h-3.5 w-3.5 shrink-0 text-primary" />
                            <span className="truncate">{formatTitle(r.title)}</span>
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="border-t p-3">
          <input ref={fileRef} type="file" hidden
            accept=".pdf,.pptx,.docx,.txt,.md,.ipynb,.vtt,.srt,.png,.jpg,.jpeg"
            onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
          <Button variant="outline" className="w-full" disabled={upload.isPending} onClick={() => fileRef.current?.click()}>
            {upload.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Upload material
          </Button>
          {upload.data && (
            <p className="mt-2 text-xs text-muted-foreground">
              {upload.data.status === "indexed"
                ? `Indexed ${upload.data.resource_id}`
                : `Upload ${upload.data.status}: ${upload.data.detail}`}
            </p>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {selected ? <ResourcePanel resource={selected} /> : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Select a resource to summarize, quiz, or explore related concepts.
          </div>
        )}
      </div>
    </div>
  );
}

function ResourcePanel({ resource }: { resource: ResourceNode }) {
  const [summaryText, setSummaryText] = useState("");
  const [summarizing, setSummarizing] = useState(false);
  const related = useQuery({ queryKey: ["related", resource.resource_id], queryFn: () => knowledgeApi.related(resource.resource_id) });
  const quiz = useMutation({ mutationFn: () => quizApi.generate(resource.resource_id, 4, "medium") });

  // Streaming summary — the summary is LLM-generated (can take tens of seconds); streaming
  // shows tokens progressively and never trips the proxy timeout.
  const runSummary = async () => {
    setSummaryText("");
    setSummarizing(true);
    await streamSummary(resource.resource_id, {
      onToken: (t) => setSummaryText((s) => s + t),
      onFinal: () => {},
      onDone: () => setSummarizing(false),
      onError: () => { setSummaryText("Sorry — the summary could not be generated."); setSummarizing(false); },
    });
    setSummarizing(false);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <Badge variant="secondary">{formatTitle(resource.doc_type)}</Badge>
        <h1 className="mt-2 text-xl font-semibold">{formatTitle(resource.title)}</h1>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={runSummary} disabled={summarizing}>
          {summarizing && <Loader2 className="h-4 w-4 animate-spin" />} Summarize
        </Button>
        <Button size="sm" variant="outline" onClick={() => quiz.mutate()} disabled={quiz.isPending}>
          {quiz.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Generate Quiz
        </Button>
      </div>

      {(summaryText || summarizing) && (
        <Card><CardContent className="prose-answer pt-5 text-sm">
          {summaryText}
          {summarizing && <span className="typing-dot text-primary">▍</span>}
        </CardContent></Card>
      )}
      {quiz.isPending && (
        <Card><CardContent className="flex items-center gap-2 pt-5 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Generating an interactive quiz from the course material…
        </CardContent></Card>
      )}
      {quiz.isError && (
        <Card><CardContent className="pt-5 text-sm text-destructive">Could not generate a quiz for this resource.</CardContent></Card>
      )}
      {quiz.data && <QuizRunner quiz={quiz.data} onRetry={() => quiz.mutate()} />}
      {related.data?.concepts?.length ? (
        <Card><CardContent className="pt-5">
          <p className="text-xs font-medium uppercase text-muted-foreground">Related concepts</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {related.data.concepts.map((c: any) => <Badge key={c.concept_id}>{c.concept}</Badge>)}
          </div>
        </CardContent></Card>
      ) : null}
    </div>
  );
}
