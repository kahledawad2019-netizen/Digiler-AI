"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { instructorApi } from "@/lib/client";
import { useAuth } from "@/store/auth";

function masteryColor(m: number) {
  return m < 0.4 ? "bg-destructive" : m < 0.7 ? "bg-amber-500" : "bg-emerald-500";
}

export default function InstructorPage() {
  const { user } = useAuth();
  if (user && !["instructor", "admin"].includes(user.role)) {
    return <div className="p-6 text-sm text-muted-foreground">Instructor access required.</div>;
  }
  return <InstructorPanel />;
}

function InstructorPanel() {
  const overview = useQuery({ queryKey: ["inst-overview"], queryFn: instructorApi.overview });
  const cohort = useQuery({ queryKey: ["inst-students"], queryFn: instructorApi.students });
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: ["inst-student", selected],
    queryFn: () => instructorApi.student(selected as string),
    enabled: !!selected,
  });

  const o: any = overview.data;
  const dist: Record<string, number> = o?.students?.mastery_distribution ?? {};
  const maxBucket = Math.max(1, ...Object.values(dist));

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <h1 className="text-xl font-semibold">Instructor</h1>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Registered" value={o?.students?.registered ?? "—"} />
          <Stat label="Active" value={o?.students?.active ?? "—"} />
          <Stat label="Avg mastery" value={o ? `${Math.round(o.students.avg_mastery * 100)}%` : "—"} />
          <Stat label="Resources" value={o?.content?.resources ?? "—"} />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Mastery distribution</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {Object.entries(dist).map(([bucket, n]) => (
                <div key={bucket} className="flex items-center gap-2 text-xs">
                  <span className="w-14 text-muted-foreground">{bucket}%</span>
                  <div className="h-4 flex-1 rounded bg-muted">
                    <div className="h-4 rounded bg-primary" style={{ width: `${(n / maxBucket) * 100}%` }} />
                  </div>
                  <span className="w-6 text-right font-medium">{n}</span>
                </div>
              ))}
              {!o && <p className="text-sm text-muted-foreground">Loading…</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Most common weak concepts</CardTitle></CardHeader>
            <CardContent className="space-y-1.5">
              {(o?.common_weak_concepts ?? []).map((c: any) => (
                <div key={c.concept} className="flex items-center justify-between text-sm">
                  <span className="truncate">{c.concept.replace("concept:", "")}</span>
                  <Badge variant="warning">{c.students} students</Badge>
                </div>
              ))}
              {o && !o.common_weak_concepts?.length && (
                <p className="text-sm text-muted-foreground">No weak concepts recorded yet.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle>Content inventory</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {Object.entries(o?.content?.by_type ?? {}).map(([t, n]) => (
              <Badge key={t} variant="secondary">{t}: {n as number}</Badge>
            ))}
            {!o && <p className="text-sm text-muted-foreground">Loading…</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Students</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            {cohort.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Student</th>
                  <th className="py-2 pr-3 font-medium">Mastery</th>
                  <th className="py-2 pr-3 font-medium">Tracked</th>
                  <th className="py-2 pr-3 font-medium">Weak</th>
                  <th className="py-2 pr-3 font-medium">Events</th>
                </tr>
              </thead>
              <tbody>
                {(cohort.data?.students ?? []).map((st: any) => (
                  <tr key={st.student_id}
                    onClick={() => setSelected(st.student_id === selected ? null : st.student_id)}
                    className="cursor-pointer border-b last:border-0 hover:bg-accent">
                    <td className="py-2 pr-3">
                      <span className="font-medium">{st.name || st.student_id}</span>
                      <span className="ml-2 text-xs text-muted-foreground">{st.email}</span>
                    </td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-20 rounded-full bg-muted">
                          <div className={`h-2 rounded-full ${masteryColor(st.overall_mastery)}`}
                            style={{ width: `${st.overall_mastery * 100}%` }} />
                        </div>
                        <span className="text-xs">{Math.round(st.overall_mastery * 100)}%</span>
                      </div>
                    </td>
                    <td className="py-2 pr-3">{st.n_tracked}</td>
                    <td className="py-2 pr-3">{st.n_weak}</td>
                    <td className="py-2 pr-3">{st.n_events}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {cohort.data && !cohort.data.students?.length && (
              <p className="text-sm text-muted-foreground">No registered students yet.</p>
            )}
          </CardContent>
        </Card>

        {selected && detail.data && (
          <Card>
            <CardHeader><CardTitle>{selected} — concept detail</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1.5 text-xs font-medium uppercase text-muted-foreground">Weak concepts</p>
                <div className="flex flex-wrap gap-1.5">
                  {(detail.data.weak ?? []).map((c: any) => (
                    <Badge key={c.concept} variant="warning">{c.concept.replace("concept:", "")}</Badge>
                  ))}
                  {!detail.data.weak?.length && <span className="text-sm text-muted-foreground">None</span>}
                </div>
              </div>
              <div>
                <p className="mb-1.5 text-xs font-medium uppercase text-muted-foreground">Strong concepts</p>
                <div className="flex flex-wrap gap-1.5">
                  {(detail.data.strong ?? []).map((c: any) => (
                    <Badge key={c.concept} variant="success">{c.concept.replace("concept:", "")}</Badge>
                  ))}
                  {!detail.data.strong?.length && <span className="text-sm text-muted-foreground">None</span>}
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <p className="text-2xl font-semibold">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}
