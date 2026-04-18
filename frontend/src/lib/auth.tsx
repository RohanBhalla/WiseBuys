import { useNavigate } from "@tanstack/react-router";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiFetch, readStoredAuth, writeStoredAuth, type StoredAuth } from "./api";
import type {
  CustomerProfilePublic,
  TokenResponse,
  UserPublic,
  UserRole,
  VendorApplicationPublic,
} from "./types";

interface AuthState {
  token: string | null;
  role: UserRole | null;
  userId: number | null;
  me: UserPublic | null;
  ready: boolean;
}

interface AuthContextValue extends AuthState {
  setFromLogin: (token: TokenResponse) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchMe(token: string): Promise<UserPublic> {
  return apiFetch<UserPublic>("/api/auth/me", { token });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    role: null,
    userId: null,
    me: null,
    ready: false,
  });

  useEffect(() => {
    const stored = readStoredAuth();
    if (!stored?.token) {
      setState((s) => ({ ...s, ready: true }));
      return;
    }
    void (async () => {
      try {
        const me = await fetchMe(stored.token);
        setState({
          token: stored.token,
          role: me.role,
          userId: me.id,
          me,
          ready: true,
        });
        writeStoredAuth({ token: stored.token, role: me.role, userId: me.id });
      } catch {
        writeStoredAuth(null);
        setState({ token: null, role: null, userId: null, me: null, ready: true });
      }
    })();
  }, []);

  const refreshMe = useCallback(async () => {
    if (!state.token) return;
    const me = await fetchMe(state.token);
    setState((prev) => ({
      ...prev,
      me,
      role: me.role,
      userId: me.id,
    }));
    writeStoredAuth({ token: state.token, role: me.role, userId: me.id });
  }, [state.token]);

  const setFromLogin = useCallback(async (tr: TokenResponse) => {
    const me = await fetchMe(tr.access_token);
    writeStoredAuth({ token: tr.access_token, role: me.role, userId: me.id });
    setState({
      token: tr.access_token,
      role: me.role,
      userId: me.id,
      me,
      ready: true,
    });
  }, []);

  const logout = useCallback(() => {
    writeStoredAuth(null);
    setState({ token: null, role: null, userId: null, me: null, ready: true });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      setFromLogin,
      logout,
      refreshMe,
    }),
    [state, setFromLogin, logout, refreshMe]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useRequireAuth(options?: { redirectTo?: string }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const redirectTo = options?.redirectTo ?? "/login";

  useEffect(() => {
    if (!auth.ready) return;
    if (!auth.token) void navigate({ to: redirectTo });
  }, [auth.ready, auth.token, navigate, redirectTo]);

  return auth;
}

export function useRequireRole(role: UserRole, options?: { redirectTo?: string }) {
  const auth = useRequireAuth(options);
  const navigate = useNavigate();
  const redirectTo = options?.redirectTo;

  useEffect(() => {
    if (!auth.ready || !auth.token) return;
    if (auth.role === role) return;
    const fallback =
      auth.role === "vendor" ? "/vendor" : auth.role === "customer" ? "/dashboard" : "/login";
    void navigate({ to: redirectTo ?? fallback });
  }, [auth.ready, auth.token, auth.role, role, navigate, redirectTo]);

  return auth;
}

/** After login/register, send user to the right first screen. */
export async function postAuthRedirectRole(args: {
  role: UserRole;
  navigate: ReturnType<typeof useNavigate>;
  token: string;
}) {
  const { role, navigate, token } = args;
  if (role === "customer") {
    try {
      const profile = await apiFetch<CustomerProfilePublic>("/api/customers/me", { token });
      const done = profile.primary_focus && profile.secondary_focuses.length > 0;
      if (!done) void navigate({ to: "/onboarding" });
      else void navigate({ to: "/dashboard" });
    } catch {
      void navigate({ to: "/onboarding" });
    }
    return;
  }
  if (role === "vendor") {
    try {
      const apps = await apiFetch<VendorApplicationPublic[]>("/api/vendors/applications/me", { token });
      const approved = apps.some((a) => a.status === "approved");
      if (approved) {
        void navigate({ to: "/vendor" });
        return;
      }
      const open = apps.some((a) => a.status === "submitted" || a.status === "needs_info");
      if (open) {
        void navigate({ to: "/vendor" });
        return;
      }
      void navigate({ to: "/vendor/apply" });
    } catch {
      void navigate({ to: "/vendor/apply" });
    }
  }
}
