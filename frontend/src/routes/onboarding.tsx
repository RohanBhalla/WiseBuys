import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import { PaperCard, Eyebrow, SectionLabel } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { CustomerProfilePublic, TagPublic } from "@/lib/types";

export const Route = createFileRoute("/onboarding")({
  head: () => ({
    meta: [{ title: "Onboarding — WiseBuys" }],
  }),
  component: OnboardingPage,
});

function OnboardingPage() {
  const auth = useRequireRole("customer");
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [primaryId, setPrimaryId] = useState<number | null>(null);
  const [secondaryIds, setSecondaryIds] = useState<Set<number>>(new Set());
  const [rewardsMode, setRewardsMode] = useState<"points" | "cashback" | "perks">("points");

  const tagsQ = useQuery({
    queryKey: ["tags"],
    queryFn: () => apiFetch<TagPublic[]>("/api/tags"),
    enabled: auth.ready && !!auth.token,
  });

  const profileQ = useQuery({
    queryKey: ["customer", "me"],
    queryFn: () => apiFetch<CustomerProfilePublic>("/api/customers/me"),
    enabled: auth.ready && !!auth.token,
  });

  useEffect(() => {
    const p = profileQ.data;
    if (!p) return;
    if (p.primary_focus) setPrimaryId(p.primary_focus.id);
    setSecondaryIds(new Set(p.secondary_focuses.map((t) => t.id)));
    const mode = p.rewards_preferences?.mode;
    if (mode === "cashback" || mode === "perks" || mode === "points") setRewardsMode(mode);
  }, [profileQ.data]);

  useEffect(() => {
    const p = profileQ.data;
    if (!p || !auth.ready) return;
    const done = p.primary_focus && p.secondary_focuses.length > 0;
    if (done) void navigate({ to: "/dashboard" });
  }, [profileQ.data, auth.ready, navigate]);

  const saveM = useMutation({
    mutationFn: async () => {
      if (primaryId == null) throw new Error("Pick a primary value focus.");
      if (secondaryIds.size === 0) throw new Error("Pick at least one secondary focus (required for rewards).");
      const sec = [...secondaryIds].filter((id) => id !== primaryId);
      if (sec.length === 0) throw new Error("Add a secondary focus different from primary, or adjust primary.");
      return apiFetch<CustomerProfilePublic>("/api/customers/me", {
        method: "PATCH",
        body: JSON.stringify({
          primary_focus_tag_id: primaryId,
          secondary_focus_tag_ids: sec,
          rewards_preferences: { mode: rewardsMode },
        }),
      });
    },
    onSuccess: async () => {
      toast.success("Preferences saved. Points may land in a breath.");
      await qc.invalidateQueries({ queryKey: ["customer", "me"] });
      await qc.invalidateQueries({ queryKey: ["rewards", "me"] });
      void navigate({ to: "/dashboard" });
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Save failed");
    },
  });

  if (!auth.ready || !auth.token) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <span className="text-charcoal/60 text-sm">Loading…</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-cream">
      <SiteHeader />
      <main className="flex-1 mx-auto max-w-3xl w-full px-5 sm:px-8 py-14">
        <SectionLabel number="§ I" label="Values onboarding" />
        <h1 className="display-serif text-4xl text-charcoal mt-4">What should we optimize for?</h1>
        <p className="mt-3 text-charcoal/70">
          Primary focus plus at least one secondary tag unlocks your onboarding bonus and better recommendations.
        </p>

        <PaperCard className="mt-8 p-8">
          <Eyebrow>Primary focus</Eyebrow>
          <div className="mt-4 flex flex-wrap gap-2">
            {(tagsQ.data ?? []).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setPrimaryId(t.id)}
                className={`rounded-sm border px-3 py-2 text-sm font-medium transition-colors ${
                  primaryId === t.id ? "border-terracotta bg-terracotta/10 text-charcoal" : "border-charcoal/15 text-charcoal/80 hover:border-charcoal/30"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {tagsQ.isError && <p className="mt-2 text-sm text-terracotta">Could not load tags.</p>}
        </PaperCard>

        <PaperCard className="mt-6 p-8">
          <Eyebrow>Secondary focuses</Eyebrow>
          <p className="text-sm text-charcoal/60 mt-1">Pick one or more (at least one required).</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {(tagsQ.data ?? []).map((t) => {
              const on = secondaryIds.has(t.id);
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => {
                    const next = new Set(secondaryIds);
                    if (on) next.delete(t.id);
                    else next.add(t.id);
                    setSecondaryIds(next);
                  }}
                  className={`rounded-sm border px-3 py-2 text-sm font-medium transition-colors ${
                    on ? "border-azure bg-azure/15 text-charcoal" : "border-charcoal/15 text-charcoal/80 hover:border-charcoal/30"
                  }`}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
        </PaperCard>

        <PaperCard className="mt-6 p-8">
          <Eyebrow>Rewards preference</Eyebrow>
          <div className="mt-4 flex flex-wrap gap-2">
            {(["points", "cashback", "perks"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setRewardsMode(m)}
                className={`rounded-sm border px-4 py-2 text-xs font-semibold uppercase tracking-wide ${
                  rewardsMode === m ? "border-forest bg-forest/10 text-charcoal" : "border-charcoal/15 text-charcoal/70"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </PaperCard>

        <div className="mt-8 flex flex-wrap gap-3">
          <button
            type="button"
            disabled={saveM.isPending}
            onClick={() => saveM.mutate()}
            className="bg-terracotta text-cream px-8 py-3 text-sm font-semibold rounded-sm hover:bg-charcoal transition-colors disabled:opacity-50"
          >
            {saveM.isPending ? "Saving…" : "Save & continue"}
          </button>
          <Link to="/dashboard" className="inline-flex items-center px-4 py-3 text-sm text-charcoal/70 underline decoration-terracotta underline-offset-4">
            Skip for now
          </Link>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
