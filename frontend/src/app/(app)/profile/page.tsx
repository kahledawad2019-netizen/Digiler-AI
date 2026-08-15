"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CalendarDays, LogOut } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { dashboardApi, studentApi } from "@/lib/client";
import { useAuth } from "@/store/auth";
import { initials } from "@/lib/utils";

function masteryColor(m: number) {
  return m < 0.4 ? "bg-destructive" : m < 0.7 ? "bg-amber-500" : "bg-emerald-500";
}

export default function ProfilePage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const profile = useQuery({ queryKey: ["student"], queryFn: studentApi.profile });
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });

  const d: any = dash.data;
  const s = profile.data?.summary;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div className="flex items-center gap-4">
          <Avatar className="h-14 w-14">
            <AvatarFallback>{initials(user?.name, user?.email)}</AvatarFallback>
          </Avatar>
          <div className="flex-1">
            <h1 className="text-xl font-semibold">{user?.name || "Student"}</h1>
            <p className="text-sm text-muted-foreground">{user?.email}</p>
          </div>
          <Badge variant="secondary">{user?.role}</Badge>
          <Button variant="outline" size="sm" asChild>
            <Link href="/planner"><CalendarDays className="h-4 w-4" /> Study planner</Link>
          </Button>
          <Button variant="outline" size="sm" onClick={() => { logout(); router.push("/login"); }}>
            <LogOut className="h-4 w-4" /> Sign out
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Overall mastery" value={s ? `${Math.round(s.overall_mastery * 100)}%` : "—"} />
          <Stat label="Concepts tracked" value={s?.n_tracked ?? "—"} />
          <Stat label="Weak / Strong" value={s ? `${s.n_weak} / ${s.n_strong}` : "—"} />
          <Stat label="Study time" value={d ? `${Math.round(d.time_spent?.total_minutes ?? 0)} min` : "—"} />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Mastery by domain</CardTitle></CardHeader>
            <CardContent className="space-y-2.5">
              {(d?.domain_mastery ?? []).map((x: any) => (
                <div key={x.domain}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-muted-foreground">{x.domain}</span>
                    <span className="font-medium">{Math.round(x.mastery * 100)}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-muted">
                    <div className={`h-2 rounded-full ${masteryColor(x.mastery)}`} style={{ width: `${x.mastery * 100}%` }} />
                  </div>
                </div>
              ))}
              {!d && <p className="text-sm text-muted-foreground">No activity yet.</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Recommended next steps</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {(d?.recommendations ?? []).slice(0, 6).map((r: any, i: number) => (
                <div key={i} className="rounded-lg border p-2.5 text-sm">
                  <span className="font-medium capitalize">{r.kind}: {r.concept}</span>
                  <span className="text-muted-foreground"> — {r.reason}</span>
                </div>
              ))}
              {!d?.recommendations?.length && <p className="text-sm text-muted-foreground">Study to get recommendations.</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Weak concepts</CardTitle></CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {(profile.data?.weak ?? []).map((c) => (
                <Badge key={c.concept} variant="warning">{c.concept.replace("concept:", "")}</Badge>
              ))}
              {!profile.data?.weak?.length && <p className="text-sm text-muted-foreground">None tracked.</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Strong concepts</CardTitle></CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {(profile.data?.strong ?? []).map((c) => (
                <Badge key={c.concept} variant="success">{c.concept.replace("concept:", "")}</Badge>
              ))}
              {!profile.data?.strong?.length && <p className="text-sm text-muted-foreground">None yet.</p>}
            </CardContent>
          </Card>
        </div>
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
