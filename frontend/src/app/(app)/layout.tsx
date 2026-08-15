"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { Logo } from "@/components/logo";
import { authApi } from "@/lib/client";
import { useAuth } from "@/store/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { accessToken, user, setUser, logout } = useAuth();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!accessToken) {
      router.replace("/login");
      return;
    }
    if (user) {
      setReady(true);
      return;
    }
    authApi
      .me()
      .then((u) => { setUser(u); setReady(true); })
      .catch(() => { logout(); router.replace("/login"); });
  }, [accessToken]); // eslint-disable-line

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Logo size={40} />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
