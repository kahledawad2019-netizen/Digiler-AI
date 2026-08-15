import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Tokens, User } from "@/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  setTokens: (t: Tokens) => void;
  setUser: (u: User | null) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setTokens: (t) => set({ accessToken: t.access_token, refreshToken: t.refresh_token }),
      setUser: (u) => set({ user: u }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    { name: "digiler-auth" }
  )
);

/** Non-hook accessor for interceptors. */
export const authStore = useAuth;
