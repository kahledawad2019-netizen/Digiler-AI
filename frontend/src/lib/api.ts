import axios, { AxiosError } from "axios";
import { authStore } from "@/store/auth";

/** Same-origin: Next rewrites /api → backend (see next.config.mjs). */
export const api = axios.create({ baseURL: "/api", headers: { "Content-Type": "application/json" } });

api.interceptors.request.use((config) => {
  const token = authStore.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  const rt = authStore.getState().refreshToken;
  if (!rt) return null;
  try {
    const { data } = await axios.post("/api/auth/refresh", { refresh_token: rt });
    authStore.getState().setTokens(data);
    return data.access_token as string;
  } catch {
    authStore.getState().logout();
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (typeof error.config & { _retry?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      refreshing = refreshing ?? refreshAccess();
      const token = await refreshing;
      refreshing = null;
      if (token) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${token}`;
        return api(original);
      }
      if (typeof window !== "undefined") window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
