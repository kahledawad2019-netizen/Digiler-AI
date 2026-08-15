"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { adminApi } from "@/lib/client";
import { useAuth } from "@/store/auth";

const ROLES = ["student", "instructor", "admin"];

export default function AdminPage() {
  const { user } = useAuth();
  if (user && user.role !== "admin") {
    return <div className="p-6 text-sm text-muted-foreground">Admin access required.</div>;
  }
  return <AdminPanel selfId={user?.id} />;
}

function AdminPanel({ selfId }: { selfId?: number }) {
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: adminApi.users });
  const stats = useQuery({ queryKey: ["admin-stats"], queryFn: adminApi.stats });
  const health = useQuery({ queryKey: ["admin-health"], queryFn: adminApi.health });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-users"] });
    qc.invalidateQueries({ queryKey: ["admin-stats"] });
  };
  const setRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: string }) => adminApi.setRole(id, role),
    onSuccess: invalidate,
  });
  const remove = useMutation({ mutationFn: (id: number) => adminApi.remove(id), onSuccess: invalidate });

  const s: any = stats.data;
  const h: any = health.data;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <h1 className="text-xl font-semibold">Admin</h1>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Users" value={s?.users?.total ?? "—"} />
          <Stat label="Chats" value={s?.chats ?? "—"} />
          <Stat label="Messages" value={s?.messages ?? "—"} />
          <Stat label="KB resources" value={s?.knowledge?.catalog_resources ?? "—"} />
        </div>

        <Card>
          <CardHeader><CardTitle>Users</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            {users.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Name</th>
                  <th className="py-2 pr-3 font-medium">Email</th>
                  <th className="py-2 pr-3 font-medium">Role</th>
                  <th className="py-2 pr-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {(users.data?.users ?? []).map((u: any) => (
                  <tr key={u.id} className="border-b last:border-0">
                    <td className="py-2 pr-3 font-medium">{u.name || "—"}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{u.email}</td>
                    <td className="py-2 pr-3">
                      <select
                        value={u.role}
                        disabled={setRole.isPending}
                        onChange={(e) => setRole.mutate({ id: u.id, role: e.target.value })}
                        className="rounded-md border bg-background px-2 py-1 text-sm"
                      >
                        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </td>
                    <td className="py-2 pr-3 text-right">
                      {u.id !== selfId && (
                        <Button variant="ghost" size="sm" disabled={remove.isPending}
                          onClick={() => remove.mutate(u.id)} aria-label="Delete user">
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(setRole.error || remove.error) && (
              <p className="mt-2 text-xs text-destructive">
                {(((setRole.error || remove.error) as any)?.response?.data?.detail) ?? "Action failed."}
              </p>
            )}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Users by role</CardTitle></CardHeader>
            <CardContent className="space-y-1.5 text-sm">
              {Object.entries(s?.users?.by_role ?? {}).map(([role, n]) => (
                <div key={role} className="flex justify-between">
                  <span className="capitalize text-muted-foreground">{role}</span>
                  <span className="font-medium">{n as number}</span>
                </div>
              ))}
              {!s && <p className="text-muted-foreground">Loading…</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Component health</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <HealthRow label="LLM" ok={h?.llm?.reachable}
                detail={h?.llm ? `${h.llm.provider}/${h.llm.model}` : ""}
                okText="Connected" badText="Offline (fallback)" />
              <HealthRow label="Catalog" ok={h?.catalog?.ok}
                detail={h ? `${h.catalog.resources} resources` : ""} />
              <HealthRow label="Concept graph" ok={h?.graph?.ok}
                detail={h ? `${h.graph.nodes} nodes / ${h.graph.edges} edges` : ""} />
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Vector store</span>
                <span className="max-w-[200px] truncate font-medium">{h?.vector_store?.location ?? "—"}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function HealthRow({ label, ok, detail, okText = "OK", badText = "Down" }: {
  label: string; ok?: boolean; detail?: string; okText?: string; badText?: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        {detail && <span className="text-xs text-muted-foreground">{detail}</span>}
        <Badge variant={ok ? "success" : "warning"}>{ok ? okText : badText}</Badge>
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
