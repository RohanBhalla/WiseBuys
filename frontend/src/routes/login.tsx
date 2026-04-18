import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import { PaperCard, Eyebrow, SectionLabel } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { postAuthRedirectRole, useAuth } from "@/lib/auth";
import type { TokenResponse, UserRole } from "@/lib/types";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [{ title: "Sign in — WiseBuys" }],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { setFromLogin, token, ready, role } = useAuth();
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regRole, setRegRole] = useState<UserRole>("customer");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ready || !token) return;
    if (role === "customer") void navigate({ to: "/dashboard" });
    else if (role === "vendor") void navigate({ to: "/vendor" });
    else void navigate({ to: "/" });
  }, [ready, token, role, navigate]);

  const onSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const tr = await apiFetch<TokenResponse>("/api/auth/login", {
        method: "POST",
        skipAuth: true,
        body: JSON.stringify({ email: signInEmail, password: signInPassword }),
      });
      await setFromLogin(tr);
      await postAuthRedirectRole({ role: tr.role, navigate, token: tr.access_token });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  };

  const onRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const tr = await apiFetch<TokenResponse>("/api/auth/register", {
        method: "POST",
        skipAuth: true,
        body: JSON.stringify({ email: regEmail, password: regPassword, role: regRole }),
      });
      await setFromLogin(tr);
      await postAuthRedirectRole({ role: tr.role, navigate, token: tr.access_token });
      toast.success("Welcome aboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create account");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-cream">
      <SiteHeader />
      <main className="flex-1 mx-auto max-w-7xl w-full px-5 sm:px-8 py-14">
        <SectionLabel number="§" label="Account" />
        <h1 className="display-serif text-4xl sm:text-5xl text-charcoal mt-4">Sign in or enlist.</h1>
        <p className="mt-3 text-charcoal/70 max-w-xl">
          Customers get receipts read politely. Brands get vetted, then a catalog. No spam, no drama.
        </p>
        <div className="mt-10 grid gap-8 lg:grid-cols-2">
          <PaperCard className="p-8">
            <Eyebrow>Returning</Eyebrow>
            <h2 className="display-serif text-2xl text-charcoal mt-2">Sign in</h2>
            <form onSubmit={onSignIn} className="mt-6 space-y-4">
              <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
                Email
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={signInEmail}
                  onChange={(e) => setSignInEmail(e.target.value)}
                  className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
                />
              </label>
              <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
                Password
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={signInPassword}
                  onChange={(e) => setSignInPassword(e.target.value)}
                  className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
                />
              </label>
              <button
                type="submit"
                disabled={busy}
                className="w-full bg-charcoal text-cream py-3 text-sm font-semibold rounded-sm hover:bg-terracotta transition-colors disabled:opacity-50"
              >
                {busy ? "…" : "Sign in"}
              </button>
            </form>
          </PaperCard>

          <PaperCard className="p-8">
            <Eyebrow>New here</Eyebrow>
            <h2 className="display-serif text-2xl text-charcoal mt-2">Create account</h2>
            <form onSubmit={onRegister} className="mt-6 space-y-4">
              <div className="flex gap-2">
                {(["customer", "vendor"] as const).map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRegRole(r)}
                    className={`flex-1 py-2 text-xs font-semibold uppercase tracking-wide rounded-sm border ${
                      regRole === r ? "border-terracotta bg-terracotta/10 text-charcoal" : "border-charcoal/15 text-charcoal/70"
                    }`}
                  >
                    {r === "customer" ? "Shopper" : "Brand"}
                  </button>
                ))}
              </div>
              <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
                Email
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
                />
              </label>
              <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
                Password (8+ chars)
                <input
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
                />
              </label>
              <button
                type="submit"
                disabled={busy}
                className="w-full bg-terracotta text-cream py-3 text-sm font-semibold rounded-sm hover:bg-charcoal transition-colors disabled:opacity-50"
              >
                {busy ? "…" : "Create account"}
              </button>
            </form>
          </PaperCard>
        </div>
        <p className="mt-8 text-sm text-charcoal/55">
          <Link to="/" className="underline decoration-terracotta underline-offset-4">
            ← Back home
          </Link>
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
