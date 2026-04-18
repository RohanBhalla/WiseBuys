import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  Coffee,
  Leaf,
  MapPin,
  ShoppingBag,
  Sparkles,
  Trophy,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import heroCustomer from "@/assets/hero-customer.jpg";
import { PaperCard, Stamp, Eyebrow, SectionLabel } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type {
  CustomerProfilePublic,
  MerchantAccountPublic,
  RecommendationItem,
  RewardSummary,
  SpendingInsight,
  TagPublic,
} from "@/lib/types";

export const Route = createFileRoute("/dashboard/")({
  head: () => ({
    meta: [{ title: "Dashboard — WiseBuys" }],
  }),
  component: CustomerDashboard,
});

function CustomerDashboard() {
  const auth = useRequireRole("customer");
  const qc = useQueryClient();
  const meQ = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiFetch<{ id: number; email: string }>("/api/auth/me"),
    enabled: auth.ready && !!auth.token,
  });

  const profileQ = useQuery({
    queryKey: ["customer", "me"],
    queryFn: () => apiFetch<CustomerProfilePublic>("/api/customers/me"),
    enabled: auth.ready && !!auth.token,
  });

  const tagsQ = useQuery({
    queryKey: ["tags"],
    queryFn: () => apiFetch<TagPublic[]>("/api/tags"),
    enabled: auth.ready && !!auth.token,
  });

  const recsQ = useQuery({
    queryKey: ["recommendations", "me"],
    queryFn: () => apiFetch<RecommendationItem[]>("/api/recommendations/me?limit=10"),
    enabled: auth.ready && !!auth.token,
  });

  const rewardsQ = useQuery({
    queryKey: ["rewards", "me"],
    queryFn: () => apiFetch<RewardSummary>("/api/rewards/me"),
    enabled: auth.ready && !!auth.token,
  });

  const spendingQ = useQuery({
    queryKey: ["insights", "spending"],
    queryFn: () => apiFetch<SpendingInsight[]>("/api/insights/spending"),
    enabled: auth.ready && !!auth.token,
  });

  const accountsQ = useQuery({
    queryKey: ["knot", "accounts"],
    queryFn: () => apiFetch<MerchantAccountPublic[]>("/api/knot/merchant-accounts"),
    enabled: auth.ready && !!auth.token,
  });

  const tagBySlug = useMemo(() => {
    const m = new Map<string, TagPublic>();
    (tagsQ.data ?? []).forEach((t) => m.set(t.slug, t));
    return m;
  }, [tagsQ.data]);

  const [values, setValues] = useState({
    sustainable: false,
    local: false,
    blackOwned: false,
    womenOwned: false,
    independent: false,
  });

  useEffect(() => {
    const p = profileQ.data;
    if (!p) return;
    const sec = new Set(p.secondary_focuses.map((t) => t.slug));
    const pri = p.primary_focus?.slug;
    if (pri) sec.add(pri);
    setValues({
      sustainable: sec.has("sustainability"),
      local: sec.has("local"),
      blackOwned: sec.has("black_owned"),
      womenOwned: sec.has("women_owned"),
      independent: sec.has("ethically_sourced"),
    });
  }, [profileQ.data]);

  const patchProfileM = useMutation({
    mutationFn: (body: {
      primary_focus_tag_id: number | null;
      secondary_focus_tag_ids: number[];
    }) => apiFetch<CustomerProfilePublic>("/api/customers/me", { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["customer", "me"] }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not update values"),
  });

  const buildPatchFromToggles = (next: typeof values) => {
    const ids: number[] = [];
    const primary =
      profileQ.data?.primary_focus?.id ??
      (() => {
        const t = tagBySlug.get("sustainability");
        return t?.id;
      })();
    const map: [keyof typeof values, string][] = [
      ["sustainable", "sustainability"],
      ["local", "local"],
      ["blackOwned", "black_owned"],
      ["womenOwned", "women_owned"],
      ["independent", "ethically_sourced"],
    ];
    for (const [key, slug] of map) {
      if (next[key]) {
        const t = tagBySlug.get(slug);
        if (t) ids.push(t.id);
      }
    }
    const primaryId = primary ?? ids[0] ?? null;
    const secondary = ids.filter((id) => id !== primaryId);
    return { primary_focus_tag_id: primaryId, secondary_focus_tag_ids: secondary };
  };

  const onToggle = (key: keyof typeof values) => {
    const next = { ...values, [key]: !values[key] };
    setValues(next);
    const patch = buildPatchFromToggles(next);
    if (patch.primary_focus_tag_id == null || patch.secondary_focus_tag_ids.length === 0) {
      toast.message("Pick at least one value tag.");
      return;
    }
    patchProfileM.mutate(patch);
  };

  const displayName = meQ.data?.email?.split("@")[0] ?? "there";
  const totalSpent = (spendingQ.data ?? []).reduce((s, i) => s + (i.total_spent ?? 0), 0);
  const merchantCount = (accountsQ.data ?? []).length;
  const balance = rewardsQ.data?.balance ?? 0;

  const vendorPoints = useMemo(() => {
    const map = new Map<number, number>();
    for (const ev of rewardsQ.data?.events ?? []) {
      if (ev.related_vendor_user_id == null) continue;
      map.set(ev.related_vendor_user_id, (map.get(ev.related_vendor_user_id) ?? 0) + ev.points);
    }
    return [...map.entries()].slice(0, 5);
  }, [rewardsQ.data?.events]);

  if (!auth.ready || !auth.token) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <span className="text-charcoal/60 text-sm">Loading…</span>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col">
      <Greeting displayName={displayName} />
      <Stats merchantCount={merchantCount} balance={balance} totalSpent={totalSpent} recCount={recsQ.data?.length ?? 0} />
      <RecommendationsFeed items={recsQ.data ?? []} loading={recsQ.isLoading} />
      <RewardsAndValues
        balance={balance}
        vendorPoints={vendorPoints}
        values={values}
        onToggle={onToggle}
        patchBusy={patchProfileM.isPending}
        showConnectCta={merchantCount === 0}
      />
    </main>
  );
}

function Greeting({ displayName }: { displayName: string }) {
  return (
    <section className="border-b border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-10 md:py-14 grid md:grid-cols-12 gap-8 items-end">
        <div className="md:col-span-8">
          <Eyebrow>Your edition · WiseBuys</Eyebrow>
          <h1 className="display-serif text-4xl sm:text-6xl text-charcoal mt-3 leading-[0.98]">
            Good day, <span className="italic text-terracotta">{displayName}</span>.
          </h1>
          <p className="mt-4 text-charcoal/70 max-w-xl">
            Linked merchants, spending totals, and recommendations below are live from your WiseBuys API.
          </p>
        </div>
        <div className="md:col-span-4">
          <PaperCard className="p-2">
            <img src={heroCustomer} alt="" width={1024} height={896} loading="lazy" className="w-full h-auto block" />
          </PaperCard>
        </div>
      </div>
    </section>
  );
}

function Stats({
  merchantCount,
  balance,
  totalSpent,
  recCount,
}: {
  merchantCount: number;
  balance: number;
  totalSpent: number;
  recCount: number;
}) {
  const stats = [
    { num: String(merchantCount), label: "linked merchants", caption: "Connect more in one tap." },
    { num: `$${totalSpent.toFixed(0)}`, label: "tracked spend (insights)", caption: "From synced Knot purchases." },
    { num: String(balance), label: "reward points", caption: `${recCount} live recommendations below.` },
  ];
  return (
    <section className="bg-cream-deep border-b border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <SectionLabel number="§ A" label="Summary" />
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {stats.map((s) => (
            <PaperCard key={s.label} className="p-7">
              <div className="num-display text-charcoal text-5xl sm:text-6xl">{s.num}</div>
              <div className="ink-divider my-4" />
              <div className="display-serif text-charcoal text-lg">{s.label}</div>
              <div className="text-sm text-charcoal/60 italic mt-1">{s.caption}</div>
            </PaperCard>
          ))}
        </div>
      </div>
    </section>
  );
}

function recIcon(category: string | null | undefined) {
  const c = (category ?? "").toLowerCase();
  if (c.includes("clean") || c.includes("home")) return Leaf;
  if (c.includes("coffee") || c.includes("food")) return Coffee;
  return ShoppingBag;
}

function RecommendationsFeed({ items, loading }: { items: RecommendationItem[]; loading: boolean }) {
  const [open, setOpen] = useState<string | null>(null);

  const handleSwitch = (name: string) => {
    toast(`Interest logged: ${name}`, {
      description: "No switch endpoint yet — this is recorded for your next sync story.",
    });
    // eslint-disable-next-line no-console
    console.info("switch_interest", name);
  };

  return (
    <section>
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-14">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <SectionLabel number="§ B" label="Recommendations" />
            <h2 className="display-serif text-3xl sm:text-4xl text-charcoal mt-3">Live picks from your values + history.</h2>
          </div>
        </div>

        {loading && <p className="mt-6 text-sm text-charcoal/60">Loading recommendations…</p>}
        {!loading && items.length === 0 && (
          <PaperCard className="mt-8 p-8 text-charcoal/70">
            No recommendations yet — link merchants and set value focuses, or wait for approved vendor products in your categories.
          </PaperCard>
        )}

        <div className="mt-8 space-y-4">
          {items.map((r) => {
            const Icon = recIcon(r.product.category);
            const idKey = String(r.product.id);
            const isOpen = open === idKey;
            const price = r.product.price_hint != null ? String(r.product.price_hint) : "—";
            return (
              <PaperCard key={idKey} className="p-0">
                <div className="grid md:grid-cols-12 gap-0">
                  <div className="md:col-span-1 bg-cream-deep flex md:flex-col items-center justify-center p-4 md:p-6 border-b md:border-b-0 md:border-r border-charcoal/15">
                    <Icon className="h-7 w-7 text-charcoal/70" strokeWidth={1.6} />
                    <div className="text-[0.6rem] uppercase tracking-widest text-charcoal/55 ml-3 md:ml-0 md:mt-3">
                      {r.product.category ?? "Product"}
                    </div>
                  </div>
                  <div className="md:col-span-5 p-6 border-b md:border-b-0 md:border-r border-charcoal/15">
                    <div className="text-[0.65rem] uppercase tracking-widest text-charcoal/50">From your purchases</div>
                    <div className="display-serif text-xl text-charcoal mt-1 line-through decoration-terracotta decoration-2">
                      Similar to what you buy
                    </div>
                    <div className="text-xs text-charcoal/55 mt-2 num-display">score {r.score.toFixed(1)}</div>
                  </div>
                  <div className="md:col-span-4 p-6 border-b md:border-b-0 md:border-r border-charcoal/15">
                    <div className="text-[0.65rem] uppercase tracking-widest text-terracotta">Aligned pick</div>
                    <div className="display-serif text-xl text-charcoal mt-1">{r.product.name}</div>
                    <div className="num-display text-charcoal text-2xl mt-2">{price}</div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {r.product.key_features?.slice(0, 3).map((f) => (
                        <Stamp key={f} color="forest" className="!text-[0.6rem]">
                          {f}
                        </Stamp>
                      ))}
                    </div>
                  </div>
                  <div className="md:col-span-2 p-6 flex flex-col justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => handleSwitch(r.product.name)}
                      className="bg-terracotta text-cream px-4 py-2.5 text-xs font-semibold tracking-wide rounded-sm hover:bg-charcoal transition-colors inline-flex items-center justify-center gap-1.5"
                    >
                      Switch & Earn <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setOpen(isOpen ? null : idKey)}
                      className="text-xs text-charcoal/70 hover:text-terracotta inline-flex items-center justify-center gap-1 font-medium"
                    >
                      Why this is better
                      <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                    </button>
                  </div>
                </div>
                {isOpen && (
                  <div className="border-t border-dashed border-charcoal/25 bg-cream-deep p-6 animate-paper-in">
                    <div className="grid md:grid-cols-12 gap-6">
                      <div className="md:col-span-3">
                        <Eyebrow>Reasoning</Eyebrow>
                        <div className="display-serif text-charcoal text-lg mt-1">The case</div>
                      </div>
                      <div className="md:col-span-9 text-sm text-charcoal/80 leading-relaxed space-y-2">
                        {r.reasons.map((line) => (
                          <p key={line}>{line}</p>
                        ))}
                        {r.evidence_line_item_ids.length > 0 && (
                          <p className="text-xs text-charcoal/55 num-display">Evidence line items: {r.evidence_line_item_ids.join(", ")}</p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </PaperCard>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function RewardsAndValues({
  balance,
  vendorPoints,
  values,
  onToggle,
  patchBusy,
  showConnectCta,
}: {
  balance: number;
  vendorPoints: [number, number][];
  values: {
    sustainable: boolean;
    local: boolean;
    blackOwned: boolean;
    womenOwned: boolean;
    independent: boolean;
  };
  onToggle: (k: keyof typeof values) => void;
  patchBusy: boolean;
  showConnectCta: boolean;
}) {
  const rows = [
    ["sustainable", "Sustainability", Leaf],
    ["local", "Local", MapPin],
    ["blackOwned", "Black-owned", Users],
    ["womenOwned", "Women-owned", Sparkles],
    ["independent", "Ethically sourced", ShoppingBag],
  ] as const;

  return (
    <section className="bg-cream-deep border-t border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-14 grid lg:grid-cols-2 gap-8">
        <div>
          <SectionLabel number="§ D" label="Loyalty & Rewards" />
          <h2 className="display-serif text-3xl text-charcoal mt-3">Points ledger (live)</h2>
          {showConnectCta && (
            <Link
              to="/dashboard/connect"
              className="mt-3 inline-block text-sm font-semibold text-terracotta underline decoration-2 underline-offset-4"
            >
              Link a merchant to start earning link bonuses →
            </Link>
          )}
          <PaperCard className="mt-6 p-6">
            <div className="flex items-center justify-between">
              <div>
                <Eyebrow>WiseBuys points</Eyebrow>
                <div className="num-display text-charcoal text-5xl mt-1">{balance}</div>
              </div>
              <Trophy className="h-12 w-12 text-terracotta" strokeWidth={1.4} />
            </div>
            <div className="ink-divider my-5" />
            <div className="space-y-5">
              {vendorPoints.length === 0 && <p className="text-sm text-charcoal/60">Vendor-tagged events will stack here.</p>}
              {vendorPoints.map(([vid, pts]) => {
                const pct = Math.min(100, (pts / 500) * 100);
                return (
                  <div key={vid}>
                    <div className="flex justify-between text-sm">
                      <span className="font-semibold text-charcoal">Vendor #{vid}</span>
                      <span className="text-charcoal/60 num-display">{pts}/500</span>
                    </div>
                    <div className="mt-2 h-2 bg-charcoal/10 rounded-sm overflow-hidden">
                      <div className="h-full bg-terracotta" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </PaperCard>
        </div>

        <div>
          <SectionLabel number="§ E" label="Preferences & Values" />
          <h2 className="display-serif text-3xl text-charcoal mt-3">Spend like you mean it.</h2>
          <PaperCard className="mt-6 p-6">
            <Eyebrow>Value toggles</Eyebrow>
            <p className="text-xs text-charcoal/55 mt-1">{patchBusy ? "Saving…" : "Updates your customer profile."}</p>
            <div className="mt-4 space-y-3">
              {rows.map(([key, label, Icon]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => onToggle(key)}
                  className={`w-full flex items-center justify-between p-3 border rounded-sm transition-colors ${
                    values[key] ? "border-terracotta bg-terracotta/5" : "border-charcoal/15 hover:border-charcoal/30"
                  }`}
                >
                  <span className="flex items-center gap-3 text-sm font-medium text-charcoal">
                    <Icon className="h-4 w-4" strokeWidth={1.7} /> {label}
                  </span>
                  <span className={`h-5 w-9 rounded-full p-0.5 transition-colors ${values[key] ? "bg-terracotta" : "bg-charcoal/20"}`}>
                    <span className={`block h-4 w-4 bg-cream rounded-full transition-transform ${values[key] ? "translate-x-4" : ""}`} />
                  </span>
                </button>
              ))}
            </div>
          </PaperCard>
        </div>
      </div>
    </section>
  );
}
