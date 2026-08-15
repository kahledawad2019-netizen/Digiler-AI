"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Bot, CalendarDays, GraduationCap, LayoutList, Plus, Settings, ShieldCheck, User as UserIcon, Users } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { chatApi } from "@/lib/client";
import { useAuth } from "@/store/auth";
import { cn, initials } from "@/lib/utils";

const NAV = [
  { href: "/knowledge", label: "Knowledge Base", icon: BookOpen },
  { href: "/courses", label: "Courses", icon: GraduationCap },
  { href: "/planner", label: "Study Planner", icon: CalendarDays },
  { href: "/agents", label: "Agents & RL", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
];

// Role-gated entries — students never see these; the base sidebar stays as specified.
const STAFF_NAV = [
  { href: "/instructor", label: "Instructor", icon: Users, roles: ["instructor", "admin"] },
  { href: "/admin", label: "Admin", icon: ShieldCheck, roles: ["admin"] },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const staffNav = STAFF_NAV.filter((n) => user && n.roles.includes(user.role));
  const { data: chats } = useQuery({ queryKey: ["chats"], queryFn: chatApi.list });

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r bg-card">
      <div className="flex h-14 items-center px-4">
        <Logo />
      </div>

      <div className="px-3">
        <Button className="w-full justify-start" onClick={() => router.push("/chat")}>
          <Plus className="h-4 w-4" /> New Chat
        </Button>
      </div>

      <nav className="mt-3 space-y-0.5 px-3">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              pathname.startsWith(href)
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4" /> {label}
          </Link>
        ))}
        {staffNav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              pathname.startsWith(href)
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4" /> {label}
          </Link>
        ))}
      </nav>

      <div className="mt-5 flex items-center gap-2 px-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <LayoutList className="h-3.5 w-3.5" /> Recent Chats
      </div>
      <div className="mt-1 flex-1 space-y-0.5 overflow-y-auto px-3 pb-2">
        {(chats ?? []).map((c) => (
          <Link
            key={c.id}
            href={`/chat/${c.id}`}
            className={cn(
              "block truncate rounded-lg px-3 py-2 text-sm transition-colors",
              pathname === `/chat/${c.id}`
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            {c.title}
          </Link>
        ))}
        {chats && chats.length === 0 && (
          <p className="px-3 py-2 text-sm text-muted-foreground">No chats yet.</p>
        )}
      </div>

      <Link href="/profile" className="flex items-center gap-3 border-t px-4 py-3 hover:bg-accent">
        <Avatar>
          <AvatarFallback>{initials(user?.name, user?.email)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{user?.name || "Profile"}</p>
          <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
        </div>
        <UserIcon className="h-4 w-4 text-muted-foreground" />
      </Link>
    </aside>
  );
}
