"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CalendarDays, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { plannerApi } from "@/lib/client";

const ACT_TONE: Record<string, "default" | "secondary" | "success" | "warning"> = {
  read: "default", watch: "secondary", practice: "warning", quiz: "secondary", revision: "success",
};

export default function PlannerPage() {
  const [goal, setGoal] = useState("Master my weak concepts before the exam");
  const [days, setDays] = useState(14);
  const [minutes, setMinutes] = useState(60);
  const plan = useMutation({ mutationFn: () => plannerApi.plan(goal, days, minutes) });
  const p: any = plan.data;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-5 p-6">
        <h1 className="text-xl font-semibold">Study Planner</h1>
        <Card>
          <CardContent className="grid grid-cols-1 gap-3 pt-5 sm:grid-cols-4">
            <div className="sm:col-span-2">
              <label className="text-xs text-muted-foreground">Goal</label>
              <Input value={goal} onChange={(e) => setGoal(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Deadline (days)</label>
              <Input type="number" value={days} onChange={(e) => setDays(Number(e.target.value))} />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Minutes/day</label>
              <Input type="number" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
            </div>
            <div className="flex gap-2 sm:col-span-4">
              <Button onClick={() => plan.mutate()} disabled={plan.isPending}>
                {plan.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Generate plan
              </Button>
              {p && (
                <Button variant="outline" asChild>
                  <a href={`${plannerApi.calendarUrl}?days=${days}&minutes=${minutes}`}>
                    <CalendarDays className="h-4 w-4" /> Export calendar (.ics)
                  </a>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {p && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {p.stats?.n_days_used}/{p.stats?.deadline_days} days · {p.total_minutes} min ·{" "}
              {Math.round((p.stats?.weak_minutes_share ?? 0) * 100)}% on weak concepts
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {p.days.map((day: any) => (
                <Card key={day.day}>
                  <CardContent className="pt-4">
                    <p className="mb-2 text-sm font-semibold">Day {day.day} <span className="font-normal text-muted-foreground">· {day.minutes} min</span></p>
                    <div className="space-y-1.5">
                      {day.activities.map((a: any, i: number) => (
                        <div key={i} className="flex items-center justify-between text-sm">
                          <span className="truncate">{a.concept}</span>
                          <Badge variant={ACT_TONE[a.type] ?? "secondary"}>{a.type}</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
