"use client";

import { useState } from "react";
import { Check, RotateCcw, Trophy, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Quiz } from "@/types";

const TYPE_LABEL: Record<string, string> = {
  multiple_choice: "Multiple choice",
  true_false: "True / False",
  short_answer: "Short answer",
};

function gradeShort(userText: string, answer: string): boolean {
  const norm = (s: string) => new Set((s.toLowerCase().match(/[a-z]{3,}/g) || []));
  const a = norm(answer);
  const u = norm(userText);
  if (a.size === 0) return userText.trim().length > 2;
  let hit = 0;
  a.forEach((w) => { if (u.has(w)) hit++; });
  return hit / a.size >= 0.4;
}

export function QuizRunner({ quiz, onRetry }: { quiz: Quiz; onRetry: () => void }) {
  const qs = quiz.questions;
  const [idx, setIdx] = useState(0);
  const [choice, setChoice] = useState("");
  const [checked, setChecked] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [done, setDone] = useState(false);

  const q = qs[idx];
  const isChoice = q?.type !== "short_answer";
  const correct = q?.type === "short_answer"
    ? gradeShort(choice, q?.answer ?? "")
    : choice.trim().toLowerCase() === (q?.answer ?? "").trim().toLowerCase();

  const submit = () => {
    if (!choice.trim() || checked) return;
    setChecked(true);
    if (correct) setCorrectCount((c) => c + 1);
  };
  const next = () => {
    if (idx + 1 >= qs.length) { setDone(true); return; }
    setIdx(idx + 1); setChoice(""); setChecked(false);
  };

  if (!qs.length) {
    return <Card><CardContent className="pt-5 text-sm text-muted-foreground">No questions were generated. Try again.</CardContent></Card>;
  }

  if (done) {
    const pct = Math.round((correctCount / qs.length) * 100);
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent">
            <Trophy className="h-6 w-6 text-primary" />
          </div>
          <p className="text-2xl font-semibold">{correctCount} / {qs.length}</p>
          <p className="text-sm text-muted-foreground">You scored {pct}% on {quiz.label}.</p>
          <Button onClick={onRetry}><RotateCcw className="h-4 w-4" /> New quiz</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        {/* progress */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Question {idx + 1} of {qs.length}</span>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{TYPE_LABEL[q.type] ?? q.type}</Badge>
            <span>Score {correctCount}</span>
          </div>
        </div>
        <div className="h-1.5 w-full rounded-full bg-muted">
          <div className="h-1.5 rounded-full bg-primary transition-all" style={{ width: `${(idx / qs.length) * 100}%` }} />
        </div>

        <p className="text-sm font-medium">{q.question}</p>

        {/* answer input */}
        {isChoice ? (
          <div className="space-y-2">
            {q.options.map((opt) => {
              const selected = choice === opt;
              const isAnswer = opt.trim().toLowerCase() === q.answer.trim().toLowerCase();
              const state = !checked ? (selected ? "sel" : "idle")
                : isAnswer ? "right" : selected ? "wrong" : "idle";
              return (
                <button
                  key={opt}
                  disabled={checked}
                  onClick={() => setChoice(opt)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                    state === "idle" && "hover:bg-accent",
                    state === "sel" && "border-primary bg-accent",
                    state === "right" && "border-emerald-500 bg-emerald-50 text-emerald-800",
                    state === "wrong" && "border-destructive bg-red-50 text-destructive",
                  )}
                >
                  <span className={cn("flex h-4 w-4 items-center justify-center rounded-full border",
                    selected && !checked && "border-primary", state === "right" && "border-emerald-600",
                    state === "wrong" && "border-destructive")}>
                    {checked && isAnswer && <Check className="h-3 w-3" />}
                    {checked && state === "wrong" && <X className="h-3 w-3" />}
                  </span>
                  {opt}
                </button>
              );
            })}
          </div>
        ) : (
          <textarea
            value={choice}
            disabled={checked}
            onChange={(e) => setChoice(e.target.value)}
            placeholder="Type your answer…"
            rows={3}
            className="w-full rounded-lg border bg-background p-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        )}

        {/* feedback */}
        {checked && (
          <div className={cn("rounded-lg border p-3 text-sm",
            correct ? "border-emerald-500 bg-emerald-50" : "border-amber-500 bg-amber-50")}>
            <p className="flex items-center gap-1.5 font-medium">
              {correct ? <Check className="h-4 w-4 text-emerald-600" /> : <X className="h-4 w-4 text-amber-600" />}
              {correct ? "Correct" : "Not quite"}
            </p>
            {!isChoice && <p className="mt-1"><span className="text-muted-foreground">Model answer: </span>{q.answer}</p>}
            {q.explanation && <p className="mt-1 text-muted-foreground">{q.explanation}</p>}
          </div>
        )}

        {/* actions */}
        <div className="flex justify-end">
          {!checked ? (
            <Button size="sm" onClick={submit} disabled={!choice.trim()}>Submit answer</Button>
          ) : (
            <Button size="sm" onClick={next}>{idx + 1 >= qs.length ? "See score" : "Next question"}</Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
