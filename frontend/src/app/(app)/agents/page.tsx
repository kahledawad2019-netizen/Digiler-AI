"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Cpu, Loader2, Play, Route } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { agentsApi, rlApi } from "@/lib/client";
import { formatTitle } from "@/lib/utils";

export default function AgentsPage() {
  const roster = useQuery({ queryKey: ["agents"], queryFn: agentsApi.roster });
  const rl = useQuery({ queryKey: ["rl"], queryFn: () => rlApi.status() });
  const [task, setTask] = useState("test me on decision trees");
  const run = useMutation({ mutationFn: () => agentsApi.ask(task) });

  const routes: any[] = roster.data?.coordinator?.routes ?? [];
  const previewRole = (() => {
    const low = task.toLowerCase();
    for (const r of routes) if ((r.keywords as string[]).some((k) => !k.startsWith("(") && low.includes(k))) return r.role;
    return "tutor";
  })();

  const d: any = rl.data;
  const maxUcb = Math.max(1, ...(d?.arms ?? []).map((a: any) => a.ucb));

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div>
          <h1 className="text-xl font-semibold">AI Agents &amp; Reinforcement Learning</h1>
          <p className="text-sm text-muted-foreground">The multi-agent crew and the live adaptive policy that personalises difficulty.</p>
        </div>

        {/* AGENT CREW */}
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><Bot className="h-4 w-4 text-primary" /> Agent crew</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(roster.data?.agents ?? []).map((a: any) => (
              <Card key={a.role}>
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{formatTitle(a.name)} Agent</p>
                    <Badge variant="secondary">{a.role}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{a.description}</p>
                </CardContent>
              </Card>
            ))}
            {roster.isLoading && <p className="text-sm text-muted-foreground">Loading crew…</p>}
          </div>
        </section>

        {/* COORDINATOR RUN */}
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Route className="h-4 w-4 text-primary" /> Coordinator — run a task</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input value={task} onChange={(e) => setTask(e.target.value)} placeholder="e.g. quiz me on SQL joins / plan my revision / explain gradient descent" />
              <Button onClick={() => run.mutate()} disabled={run.isPending}>
                {run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Run
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Intent routing (live): this task routes to <Badge variant="secondary">{previewRole}</Badge> agent.
            </p>
            {run.isPending && (
              <p className="text-sm text-muted-foreground">The agent is retrieving evidence and generating a response with Qwen3 — this can take ~20–30 s.</p>
            )}
            {run.isError && <p className="text-sm text-destructive">The agent run failed. Check the backend is reachable.</p>}
            {run.data && (
              <div className="space-y-2 rounded-lg border bg-muted/40 p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge>Handled by: {(run.data.data?.routed_to ?? run.data.role)} agent</Badge>
                  {(run.data.tools_used ?? []).map((t: string) => <Badge key={t} variant="outline">tool: {t}</Badge>)}
                  {run.data.citations?.length ? <Badge variant="secondary">{run.data.citations.length} citations</Badge> : null}
                </div>
                <p className="whitespace-pre-wrap text-sm">{run.data.output}</p>
              </div>
            )}
            <div className="text-xs text-muted-foreground">
              Coordinator strategy: {roster.data?.coordinator?.strategy}. Study-session flow:{" "}
              {(roster.data?.session_flow ?? []).join(" → ")}.
            </div>
          </CardContent>
        </Card>

        {/* RL POLICY */}
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><Cpu className="h-4 w-4 text-primary" /> Reinforcement-learning policy</h2>
          {d?.available ? (
            <Card>
              <CardContent className="space-y-4 pt-5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{d.algorithm}</Badge>
                  <Badge variant={d.strategy?.startsWith("explor") ? "warning" : "success"}>{d.strategy}</Badge>
                  <span className="text-xs text-muted-foreground">
                    concept <b>{d.concept}</b> · α={d.alpha} · {d.total_interactions} interactions recorded
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-lg border p-2"><p className="text-muted-foreground">Mastery (state)</p><p className="text-base font-semibold">{Math.round(d.context.mastery * 100)}%</p></div>
                  <div className="rounded-lg border p-2"><p className="text-muted-foreground">Recent accuracy</p><p className="text-base font-semibold">{Math.round(d.context.recent_accuracy * 100)}%</p></div>
                  <div className="rounded-lg border p-2"><p className="text-muted-foreground">Exposure</p><p className="text-base font-semibold">{Math.round(d.context.exposure * 100)}%</p></div>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase text-muted-foreground">Difficulty arms — exploitation (value) + exploration (uncertainty) = UCB</p>
                  {d.arms.map((a: any) => (
                    <div key={a.arm} className="flex items-center gap-2 text-xs">
                      <span className="w-10 shrink-0">{a.difficulty}</span>
                      <div className="flex h-4 flex-1 overflow-hidden rounded bg-muted">
                        <div className="h-4 bg-primary" style={{ width: `${(Math.max(0, a.exploitation) / maxUcb) * 100}%` }} title="exploitation" />
                        <div className="h-4 bg-amber-300" style={{ width: `${(a.exploration_bonus / maxUcb) * 100}%` }} title="exploration bonus" />
                      </div>
                      <span className="w-14 text-right">UCB {a.ucb.toFixed(2)}</span>
                      <span className="w-16 text-right text-muted-foreground">{a.count} pulls</span>
                      {a.arm === d.chosen_arm && <Badge variant="success">chosen</Badge>}
                    </div>
                  ))}
                  <div className="flex items-center gap-3 pt-1 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1"><span className="inline-block h-2 w-3 rounded-sm bg-primary" /> exploitation</span>
                    <span className="flex items-center gap-1"><span className="inline-block h-2 w-3 rounded-sm bg-amber-300" /> exploration</span>
                  </div>
                </div>

                <p className="text-sm">
                  Current strategy: it recommends difficulty <b>{d.chosen_difficulty}</b>{" "}
                  ({d.strategy}). As you answer quizzes, the policy updates from the reward and shifts from exploring to exploiting.
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card><CardContent className="pt-5 text-sm text-muted-foreground">{rl.isLoading ? "Loading policy…" : "No RL policy data available yet."}</CardContent></Card>
          )}
        </section>
      </div>
    </div>
  );
}
