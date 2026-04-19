import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  Coffee,
  Filter,
  Leaf,
  MapPin,
  RefreshCw,
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

/** Icons aligned with Preferences & Values toggles (slug → Lucide). */
function iconForValueSlug(slug: string): typeof Leaf | null {
  switch (slug) {
    case "sustainability":
      return Leaf;
    case "local":
      return MapPin;
    case "black_owned":
      return Users;
    case "women_owned":
      return Sparkles;
    case "ethically_sourced":
      return ShoppingBag;
    default:
      return null;
  }
}

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
  const hasPurchaseInsights = (spendingQ.data?.length ?? 0) > 0;
  const anyAccountNeverSynced = (accountsQ.data ?? []).some((a) => !a.last_synced_at);
  const accountsReady = !accountsQ.isLoading;
  const spendingReady = !spendingQ.isLoading;
  const showConnectFirst = accountsReady && merchantCount === 0;
  const showSyncPurchaseCta =
    accountsReady &&
    merchantCount > 0 &&
    (anyAccountNeverSynced || (spendingReady && !hasPurchaseInsights));

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
      <PurchaseDataCallout
        showConnectFirst={showConnectFirst}
        showSyncPurchaseCta={showSyncPurchaseCta}
        accountsLoading={accountsQ.isLoading}
      />
      <Stats merchantCount={merchantCount} balance={balance} totalSpent={totalSpent} recCount={recsQ.data?.length ?? 0} />
      <RecommendationsFeed items={recsQ.data ?? []} loading={recsQ.isLoading} profile={profileQ.data} />
      <RewardsAndValues
        balance={balance}
        vendorPoints={vendorPoints}
        values={values}
        onToggle={onToggle}
        patchBusy={patchProfileM.isPending}
        showConnectCta={showConnectFirst}
        showSyncCta={showSyncPurchaseCta}
      />
    </main>
  );
}

function PurchaseDataCallout({
  showConnectFirst,
  showSyncPurchaseCta,
  accountsLoading,
}: {
  showConnectFirst: boolean;
  showSyncPurchaseCta: boolean;
  accountsLoading: boolean;
}) {
  if (accountsLoading || (!showConnectFirst && !showSyncPurchaseCta)) return null;

  const connect = showConnectFirst;
  const title = connect ? "Link a merchant to import purchases" : "Sync your linked stores";
  const body = connect
    ? "WiseBuys reads SKU-level orders from Knot after you connect a store. Link first, then run a sync so spending, rewards, and recommendations can update."
    : "Your store is connected, but purchase history is not in WiseBuys yet (or a sync did not finish). Open Connect and tap Sync now on each account to pull orders and line items into the dashboard.";
  const Icon = connect ? ShoppingBag : RefreshCw;

  return (
    <section className="border-b border-charcoal/15 bg-cream-deep/60">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-7 md:py-8">
        <PaperCard className="p-6 md:p-8 border-terracotta/30 shadow-sm">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="flex gap-4 min-w-0">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-sm border border-terracotta/35 bg-terracotta/10 text-terracotta">
                <Icon className="h-6 w-6" strokeWidth={1.6} aria-hidden />
              </div>
              <div className="min-w-0">
                <Eyebrow>{connect ? "Next step" : "Action needed"}</Eyebrow>
                <h2 className="display-serif text-xl sm:text-2xl text-charcoal mt-1 leading-snug">{title}</h2>
                <p className="mt-2 text-sm text-charcoal/70 leading-relaxed max-w-2xl">{body}</p>
              </div>
            </div>
            <div className="flex shrink-0 md:pl-4">
              <Link
                to="/dashboard/connect"
                className="inline-flex w-full md:w-auto items-center justify-center gap-2 bg-terracotta text-cream px-5 py-3 text-sm font-semibold tracking-wide rounded-sm hover:bg-charcoal transition-colors text-center"
              >
                {connect ? "Connect a merchant" : "Go to Connect & sync"}
                <ArrowRight className="h-4 w-4 shrink-0" aria-hidden />
              </Link>
            </div>
          </div>
        </PaperCard>
      </div>
    </section>
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
            Spending, rewards, and recommendations update after Knot merchants are linked and synced.
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
    {
      num: String(merchantCount),
      label: "linked merchants",
      caption: merchantCount === 0 ? "Connect on the next screen to get started." : "Manage and sync on Connect.",
    },
    {
      num: `$${totalSpent.toFixed(0)}`,
      label: "tracked spend (insights)",
      caption: totalSpent === 0 ? "Run a sync after linking — totals fill in from Knot." : "From synced Knot purchases.",
    },
    { num: String(balance), label: "reward points", caption: `${recCount} live recommendations below.` },
  ];
  return (
    <section className="bg-cream-deep border-b border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <SectionLabel number="A" label="Summary" />
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

/** Per-product tags plus vendor-approved tags, deduped by id (for value chips + filters). */
function mergedValueTags(product: { tags?: TagPublic[]; vendor_tags?: TagPublic[] }): TagPublic[] {
  const m = new Map<number, TagPublic>();
  for (const t of product.tags ?? []) m.set(t.id, t);
  for (const t of product.vendor_tags ?? []) {
    if (!m.has(t.id)) m.set(t.id, t);
  }
  return [...m.values()].sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }));
}

function parsePriceHint(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "string" ? Number(value) : value;
  return Number.isFinite(n) ? n : null;
}

type PriceBucket = "all" | "under25" | "25-50" | "50-100" | "over100";

function priceInBucket(price: number | null, bucket: PriceBucket): boolean {
  if (bucket === "all") return true;
  if (price == null) return false;
  switch (bucket) {
    case "under25":
      return price < 25;
    case "25-50":
      return price >= 25 && price < 50;
    case "50-100":
      return price >= 50 && price < 100;
    case "over100":
      return price >= 100;
    default:
      return true;
  }
}

function formatPrice(value: string | number | null | undefined, currency?: string | null): string | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return null;
  const code = (currency ?? "USD").toUpperCase();
  if (code === "USD") {
    return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${code}`;
}

function priceDelta(
  altRaw: string | number | null | undefined,
  compareRaw: string | number | null | undefined,
): { kind: "cheaper" | "premium" | "even"; pct: number } | null {
  if (altRaw == null || compareRaw == null) return null;
  const alt = typeof altRaw === "string" ? Number(altRaw) : altRaw;
  const cmp = typeof compareRaw === "string" ? Number(compareRaw) : compareRaw;
  if (!Number.isFinite(alt) || !Number.isFinite(cmp) || cmp <= 0) return null;
  const diff = alt - cmp;
  const pct = (diff / cmp) * 100;
  if (diff <= -0.5) return { kind: "cheaper", pct: Math.abs(pct) };
  if (diff >= 0.5 && pct >= 8) return { kind: "premium", pct };
  return { kind: "even", pct: Math.abs(pct) };
}

function RecommendationsFeed({
  items,
  loading,
  profile,
}: {
  items: RecommendationItem[];
  loading: boolean;
  profile: CustomerProfilePublic | undefined;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [priceBucket, setPriceBucket] = useState<PriceBucket>("all");
  /** Filter by platform value-tag slugs (same tags as Preferences & Values). */
  const [selectedTagSlugs, setSelectedTagSlugs] = useState<string[]>([]);

  const userTagIds = useMemo(() => {
    const s = new Set<number>();
    if (profile?.primary_focus) s.add(profile.primary_focus.id);
    for (const t of profile?.secondary_focuses ?? []) s.add(t.id);
    return s;
  }, [profile]);

  const categoryOptions = useMemo(() => {
    const seen = new Set<string>();
    const labels: string[] = [];
    for (const r of items) {
      const c = r.product.category?.trim();
      if (!c) continue;
      const key = c.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      labels.push(c);
    }
    return labels.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  }, [items]);

  const valueTagOptions = useMemo(() => {
    const byId = new Map<number, TagPublic>();
    for (const r of items) {
      for (const t of mergedValueTags(r.product)) {
        if (!byId.has(t.id)) byId.set(t.id, t);
      }
    }
    return [...byId.values()].sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }));
  }, [items]);

  const filteredItems = useMemo(() => {
    const catNorm = categoryFilter === "all" ? null : categoryFilter.trim().toLowerCase();
    const slugSet = new Set(selectedTagSlugs);
    return items.filter((r) => {
      if (catNorm) {
        const pc = (r.product.category ?? "").trim().toLowerCase();
        if (pc !== catNorm) return false;
      }
      if (!priceInBucket(parsePriceHint(r.product.price_hint), priceBucket)) return false;
      if (slugSet.size > 0) {
        const productSlugs = new Set(mergedValueTags(r.product).map((t) => t.slug));
        let has = false;
        for (const slug of slugSet) {
          if (productSlugs.has(slug)) {
            has = true;
            break;
          }
        }
        if (!has) return false;
      }
      return true;
    });
  }, [items, categoryFilter, priceBucket, selectedTagSlugs]);

  const filtersActive =
    categoryFilter !== "all" || priceBucket !== "all" || selectedTagSlugs.length > 0;

  useEffect(() => {
    if (open && !filteredItems.some((r) => String(r.product.id) === open)) {
      setOpen(null);
    }
  }, [filteredItems, open]);

  const handleSwitch = async (name: string, productId: number) => {
    toast(`Interest logged: ${name}`, {
      description: "We let the brand know — they see this in their dashboard insights.",
    });
    try {
      await apiFetch("/api/recommendations/clicks", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, source: "dashboard" }),
      });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("click record failed", err);
    }
  };

  const toggleTagSlug = (slug: string) => {
    setSelectedTagSlugs((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
    );
  };

  const clearFilters = () => {
    setCategoryFilter("all");
    setPriceBucket("all");
    setSelectedTagSlugs([]);
  };

  return (
    <section id="dashboard-recommendations" className="scroll-mt-28">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-14">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <SectionLabel number="B" label="Recommendations" />
            <h2 className="display-serif text-3xl sm:text-4xl text-charcoal mt-3">Live picks from your values + history.</h2>
            <p className="mt-2 text-sm text-charcoal/65 max-w-2xl">
              Each pick lists <strong className="font-semibold text-charcoal/85">value tags</strong> from the product and the
              brand’s approved tags (same categories as <span className="whitespace-nowrap">Preferences &amp; Values</span>
              ). Tags in <span className="text-terracotta font-medium">terracotta</span> match a focus on your profile.
            </p>
          </div>
        </div>

        {loading && <p className="mt-6 text-sm text-charcoal/60">Loading recommendations…</p>}
        {!loading && items.length === 0 && (
          <PaperCard className="mt-8 p-8 text-charcoal/70">
            No recommendations yet — after you{" "}
            <Link to="/dashboard/connect" className="font-semibold text-terracotta underline underline-offset-4">
              link and sync merchants
            </Link>
            , set your value focuses, and give approved vendor products time to match your purchase history.
          </PaperCard>
        )}

        {!loading && items.length > 0 && (
          <PaperCard className="mt-8 p-5 sm:p-6 border border-charcoal/10">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <Filter className="h-4 w-4 text-charcoal/50" aria-hidden />
              <span className="text-[0.65rem] uppercase tracking-widest text-charcoal/55">Filter picks</span>
              {filtersActive && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="ml-auto text-xs font-medium text-terracotta hover:text-charcoal underline underline-offset-2"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="flex flex-col lg:flex-row lg:flex-wrap gap-5 lg:gap-x-8 lg:gap-y-4">
              <label className="flex flex-col gap-1.5 min-w-[10rem]">
                <span className="text-[0.65rem] uppercase tracking-widest text-charcoal/50">Type</span>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="bg-cream border border-charcoal/20 rounded-sm px-3 py-2 text-sm text-charcoal focus:outline-none focus:ring-2 focus:ring-terracotta/40"
                >
                  <option value="all">All categories</option>
                  {categoryOptions.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1.5 min-w-[10rem]">
                <span className="text-[0.65rem] uppercase tracking-widest text-charcoal/50">Price</span>
                <select
                  value={priceBucket}
                  onChange={(e) => setPriceBucket(e.target.value as PriceBucket)}
                  className="bg-cream border border-charcoal/20 rounded-sm px-3 py-2 text-sm text-charcoal focus:outline-none focus:ring-2 focus:ring-terracotta/40"
                >
                  <option value="all">Any price</option>
                  <option value="under25">Under $25</option>
                  <option value="25-50">$25 – $50</option>
                  <option value="50-100">$50 – $100</option>
                  <option value="over100">$100+</option>
                </select>
              </label>
              {valueTagOptions.length > 0 && (
                <div className="flex flex-col gap-2 flex-1 min-w-[min(100%,18rem)]">
                  <span className="text-[0.65rem] uppercase tracking-widest text-charcoal/50">Value tags</span>
                  <div className="flex flex-wrap gap-2">
                    {valueTagOptions.map((tag) => {
                      const on = selectedTagSlugs.includes(tag.slug);
                      return (
                        <button
                          key={tag.id}
                          type="button"
                          onClick={() => toggleTagSlug(tag.slug)}
                          className={`text-[0.65rem] uppercase tracking-wider px-2.5 py-1 rounded-sm border transition-colors ${
                            on
                              ? "border-forest bg-forest/10 text-forest font-semibold"
                              : "border-charcoal/20 text-charcoal/70 hover:border-terracotta/50 hover:text-charcoal"
                          }`}
                        >
                          {tag.label}
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-[0.65rem] text-charcoal/45">Show picks that carry any selected value tag.</p>
                </div>
              )}
            </div>
            {filtersActive && (
              <p className="mt-4 text-xs text-charcoal/55 num-display">
                Showing {filteredItems.length} of {items.length}
              </p>
            )}
          </PaperCard>
        )}

        {!loading && items.length > 0 && filteredItems.length === 0 && (
          <PaperCard className="mt-6 p-8 text-charcoal/70">
            No recommendations match these filters.{" "}
            <button type="button" onClick={clearFilters} className="font-semibold text-terracotta underline underline-offset-4">
              Clear filters
            </button>{" "}
            to see everything again.
          </PaperCard>
        )}

        <div className="mt-8 space-y-4">
          {filteredItems.map((r) => {
            const Icon = recIcon(r.product.category);
            const idKey = String(r.product.id);
            const isOpen = open === idKey;
            const altPrice = formatPrice(r.product.price_hint, r.product.currency);
            const comparable = r.comparable;
            const compPriceRaw =
              comparable?.unit_price ?? comparable?.total ?? null;
            const compPrice = comparable
              ? formatPrice(compPriceRaw, comparable.currency ?? r.product.currency)
              : null;
            const delta = comparable
              ? priceDelta(r.product.price_hint, compPriceRaw)
              : null;
            const deltaTone =
              delta?.kind === "cheaper"
                ? "text-forest"
                : delta?.kind === "premium"
                ? "text-terracotta"
                : "text-charcoal/60";
            const deltaLabel =
              delta?.kind === "cheaper"
                ? `${delta.pct.toFixed(0)}% cheaper`
                : delta?.kind === "premium"
                ? `${delta.pct.toFixed(0)}% premium`
                : delta
                ? "About the same price"
                : null;
            const valueTags = mergedValueTags(r.product);
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
                    <div className="text-[0.65rem] uppercase tracking-widest text-charcoal/50">
                      {comparable ? "You bought" : "From your purchases"}
                    </div>
                    {comparable ? (
                      <>
                        <div className="display-serif text-xl text-charcoal mt-1 leading-snug line-through decoration-terracotta decoration-2 decoration-[1.5px]">
                          {comparable.name}
                        </div>
                        <div className="flex items-baseline gap-3 mt-2 flex-wrap">
                          <div className="num-display text-charcoal/80 text-2xl">{compPrice ?? "—"}</div>
                          {comparable.merchant_name && (
                            <div className="text-[0.7rem] uppercase tracking-widest text-charcoal/55">
                              {comparable.merchant_name}
                            </div>
                          )}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="display-serif text-xl text-charcoal mt-1 line-through decoration-terracotta decoration-2">
                          Similar to what you buy
                        </div>
                        <div className="text-xs text-charcoal/55 mt-2 num-display">score {r.score.toFixed(1)}</div>
                      </>
                    )}
                  </div>
                  <div className="md:col-span-4 p-6 border-b md:border-b-0 md:border-r border-charcoal/15">
                    <div className="text-[0.65rem] uppercase tracking-widest text-terracotta">Aligned pick</div>
                    <div className="display-serif text-xl text-charcoal mt-1 leading-snug">{r.product.name}</div>
                    <div className="num-display text-charcoal text-2xl mt-2">{altPrice ?? "—"}</div>
                    {deltaLabel && (
                      <div className={`text-[0.7rem] mt-2 font-semibold tracking-wide ${deltaTone}`}>
                        {deltaLabel}
                      </div>
                    )}
                    {valueTags.length > 0 && (
                      <div className="mt-3">
                        <div className="text-[0.6rem] uppercase tracking-widest text-charcoal/45 mb-1.5">Value tags</div>
                        <div className="flex flex-wrap gap-1.5">
                          {valueTags.map((t) => {
                            const matchesUser = userTagIds.has(t.id);
                            const Icon = iconForValueSlug(t.slug);
                            return (
                              <Stamp
                                key={t.id}
                                color={matchesUser ? "terracotta" : "forest"}
                                className="!text-[0.6rem] inline-flex items-center gap-1"
                              >
                                {Icon ? <Icon className="h-3 w-3 shrink-0 opacity-90" aria-hidden /> : null}
                                {t.label}
                              </Stamp>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    {(r.product.key_features?.length ?? 0) > 0 && (
                      <div className="mt-3">
                        <div className="text-[0.6rem] uppercase tracking-widest text-charcoal/45 mb-1.5">Highlights</div>
                        <div className="flex flex-wrap gap-1.5">
                          {r.product.key_features?.slice(0, 4).map((f) => (
                            <Stamp key={f} color="charcoal" className="!text-[0.6rem]">
                              {f}
                            </Stamp>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="md:col-span-2 p-6 flex flex-col justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => handleSwitch(r.product.name, r.product.id)}
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
                        <div className="text-[0.65rem] uppercase tracking-widest text-charcoal/50 mt-3 num-display">
                          match score {r.score.toFixed(1)}
                        </div>
                      </div>
                      <div className="md:col-span-9 text-sm text-charcoal/80 leading-relaxed space-y-3">
                        {r.insight && (
                          <p className="text-charcoal text-base leading-relaxed">{r.insight}</p>
                        )}
                        {r.reasons.length > 0 && (
                          <ul className="space-y-1.5 pt-1">
                            {r.reasons.map((line) => (
                              <li
                                key={line}
                                className="text-charcoal/75 text-xs uppercase tracking-wider before:content-['•'] before:text-terracotta before:mr-2"
                              >
                                {line}
                              </li>
                            ))}
                          </ul>
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
  showSyncCta,
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
  showSyncCta: boolean;
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
          <SectionLabel number="C" label="Loyalty & Rewards" />
          <h2 className="display-serif text-3xl text-charcoal mt-3">Points ledger (live)</h2>
          {showConnectCta && (
            <Link
              to="/dashboard/connect"
              className="mt-4 inline-flex items-center gap-2 bg-terracotta text-cream px-4 py-2.5 text-sm font-semibold rounded-sm hover:bg-charcoal transition-colors"
            >
              Connect a merchant <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          )}
          {showSyncCta && !showConnectCta && (
            <Link
              to="/dashboard/connect"
              className="mt-4 inline-flex items-center gap-2 border border-terracotta/40 bg-terracotta/10 text-charcoal px-4 py-2.5 text-sm font-semibold rounded-sm hover:bg-terracotta/15 transition-colors"
            >
              <RefreshCw className="h-4 w-4 text-terracotta" aria-hidden />
              Sync purchases on Connect
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
          <SectionLabel number="D" label="Preferences & Values" />
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
