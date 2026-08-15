"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { authApi } from "@/lib/client";
import { useAuth } from "@/store/auth";

export default function LoginPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const tokens =
        mode === "register"
          ? await authApi.register(email, password, name)
          : await authApi.login(email, password);
      setTokens(tokens);
      setUser(await authApi.me());
      router.push("/chat");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex justify-center">
          <Logo size={40} />
        </div>
        <Card>
          <CardContent className="pt-6">
            <h1 className="text-lg font-semibold">
              {mode === "login" ? "Sign in to Digiler AI" : "Create your account"}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Grounded, cited answers from your course materials.
            </p>
            <form onSubmit={submit} className="mt-5 space-y-3">
              {mode === "register" && (
                <Input placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} required />
              )}
              <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" disabled={busy}>
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                {mode === "login" ? "Sign in" : "Create account"}
              </Button>
            </form>
            <button
              onClick={() => setMode(mode === "login" ? "register" : "login")}
              className="mt-4 w-full text-center text-sm text-muted-foreground hover:text-foreground"
            >
              {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
            </button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
