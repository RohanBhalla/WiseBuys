import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  Eye,
  MousePointerClick,
  Tag as TagIcon,
  Trophy,
  Users,
} from "lucide-react";
import heroVendor from "@/assets/hero-vendor.jpg";
import { PaperCard, Stamp, Eyebrow, SectionLabel } from "@/components/Primitives";
import { apiFetch } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type {
  CompetitorRow,
  PricingInsightRow,
  RecentClickRow,
  TopProductRow,
  VendorAnalyticsResponse,
  VendorApplicationPublic,
  VendorProfilePublic,
} from "@/lib/types";

export const Route = createFileRoute("/vendor/")({
  head: () => ({
    meta: [{ title: "Vendor Portal — WiseBuys" }],
  }),
  component: VendorHome,
});

function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (!Number.isFinite(value)) return "—";
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return iso;
  const diff = (Date.now() - then) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

function VendorHome() {
  const auth = useRequireRole("vendor");

  const appsQ = useQuery({
    queryKey: ["vendor", "applications"],
    queryFn: () => apiFetch<VendorApplicationPublic[]>("/api/vendors/applications/me"),
    enabled: auth.ready && !!auth.token,
  });

  const profileQ = useQuery({
    queryKey: ["vendor", "me"],
    queryFn: () => apiFetch<VendorProfilePublic>("/api/vendors/me"),
    enabled: auth.ready && !!auth.token,
    retry: false,
  });

  const analyticsQ = useQuery({
    queryKey: ["vendor", "analytics"],
    queryFn: () => apiFetch<VendorAnalyticsResponse>("/api/vendors/me/analytics"),
    enabled: auth.ready && !!auth.token && !!profileQ.data,
    refetchInterval: 60_000,
    retry: false,
  });

  if (!auth.ready || !auth.token) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <span className="text-charcoal/60 text-sm">Loading…</span>
      </main>
    );
  }

  const apps = appsQ.data ?? [];
  const latest = apps[0];
  const approved = apps.some((a) => a.status === "approved");
  const hasProfile = !!profileQ.data;
  const analytics = analyticsQ.data;

  return (
    <main className="flex-1 flex flex-col">
      <section className="border-b border-charcoal/15">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 py-10 md:py-14 grid md:grid-cols-12 gap-8 items-end">
          <div className="md:col-span-8">
            <Eyebrow>Brand desk · WiseBuys</Eyebrow>
            <h1 className="display-serif text-4xl sm:text-6xl text-charcoal mt-3 leading-[0.98]">
              {hasProfile ? (
                <>
                  Welcome, <span className="italic text-terracotta">{profileQ.data!.company_legal_name}</span>.
                </>
              ) : (
                <>Your application, <span className="italic text-terracotta">under review</span>.</>
              )}
            </h1>
            <p className="mt-4 text-charcoal/70 max-w-xl">
              {hasProfile
                ? "Track who's seeing your products, who you're competing against, and where your prices land in the market."
                : "Submit once, admins verify claims, then your catalog and analytics unlock."}
            </p>
          </div>
          <div className="md:col-span-4">
            <PaperCard className="p-2">
              <img src={heroVendor} alt="" width={1024} height={896} loading="lazy" className="w-full h-auto block" />
            </PaperCard>
          </div>
        </div>
      </section>

      <section className="bg-cream-deep border-b border-charcoal/15">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
          <SectionLabel number="A" label="Status" />
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            <PaperCard className="p-7">
              <Stamp color={approved ? "forest" : "terracotta"} className="!text-[0.65rem]">
                {latest?.status ?? "none"}
              </Stamp>
              <div className="num-display text-charcoal text-4xl mt-4">{apps.length}</div>
              <div className="ink-divider my-4" />
              <div className="display-serif text-charcoal text-lg">Applications on file</div>
            </PaperCard>
            <PaperCard className="p-7">
              <div className="num-display text-charcoal text-4xl">
                {hasProfile ? profileQ.data!.allowed_tags.length : "—"}
              </div>
              <div className="ink-divider my-4" />
              <div className="display-serif text-charcoal text-lg">Allowed value tags</div>
            </PaperCard>
            <PaperCard className="p-7">
              <Link
                to="/vendor/catalog"
                className="inline-flex items-center gap-2 bg-charcoal text-cream px-4 py-2 text-sm font-semibold rounded-sm hover:bg-terracotta transition-colors"
              >
                Catalog <ArrowRight className="h-4 w-4" />
              </Link>
              <div className="ink-divider my-4" />
              <div className="text-sm text-charcoal/65">
                {hasProfile
                  ? `${analytics?.summary.published_products ?? "—"} published of ${analytics?.summary.total_products ?? "—"} total`
                  : "Unlocks after approval."}
              </div>
            </PaperCard>
          </div>
          {!approved && (
            <div className="mt-6">
              <Link to="/vendor/apply" className="text-sm font-semibold text-terracotta underline underline-offset-4">
                {apps.length ? "Start / another application →" : "Start application →"}
              </Link>
            </div>
          )}
        </div>
      </section>

      {hasProfile && (
        <>
          <ReachSection analytics={analytics} loading={analyticsQ.isLoading} />
          <CompetitorsSection competitors={analytics?.competitors ?? []} loading={analyticsQ.isLoading} />
          <PricingSection rows={analytics?.pricing_insights ?? []} loading={analyticsQ.isLoading} />
          <TopProductsSection
            products={analytics?.top_products ?? []}
            recentClicks={analytics?.recent_clicks ?? []}
            loading={analyticsQ.isLoading}
          />
          <section className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
            <SectionLabel number="F" label="Allowed tags" />
            <div className="mt-4 flex flex-wrap gap-2">
              {profileQ.data!.allowed_tags.map((t) => (
                <Stamp key={t.id} color="azure" className="!text-[0.65rem]">
                  {t.label}
                </Stamp>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function ReachSection({
  analytics,
  loading,
}: {
  analytics: VendorAnalyticsResponse | undefined;
  loading: boolean;
}) {
  const s = analytics?.summary;
  const tiles: { label: string; value: string; caption: string; Icon: typeof Eye }[] = [
    {
      label: "Customers recommended",
      value: s ? String(s.recommended_customers) : "—",
      caption: s
        ? `Based on a sample of ${s.reach_sample_size} of ${s.total_active_customers} active customers.`
        : "Reach updates whenever shoppers refresh their dashboard.",
      Icon: Users,
    },
    {
      label: "Recommendation appearances",
      value: s ? String(s.recommendation_appearances) : "—",
      caption: "Total slots your products filled across the sampled customers.",
      Icon: Eye,
    },
    {
      label: "Total clicks",
      value: s ? String(s.total_clicks) : "—",
      caption: s ? `${s.clicks_last_30d} in the last 30d · ${s.clicks_last_7d} in the last 7d` : "All time, across the dashboard CTAs.",
      Icon: MousePointerClick,
    },
    {
      label: "Unique clickers",
      value: s ? String(s.distinct_click_users) : "—",
      caption: "Distinct shoppers who tapped 'Switch & Earn' on any of your items.",
      Icon: Trophy,
    },
  ];

  return (
    <section className="border-t border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <SectionLabel number="B" label="Reach & Engagement" />
        <h2 className="display-serif text-3xl text-charcoal mt-3">Who's seeing — and tapping — your products.</h2>
        {loading && <p className="mt-4 text-sm text-charcoal/60">Crunching reach numbers…</p>}
        <div className="mt-6 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {tiles.map((t) => (
            <PaperCard key={t.label} className="p-6">
              <div className="flex items-start justify-between">
                <Eyebrow>{t.label}</Eyebrow>
                <t.Icon className="h-5 w-5 text-charcoal/55" strokeWidth={1.6} />
              </div>
              <div className="num-display text-charcoal text-5xl mt-3">{t.value}</div>
              <div className="ink-divider my-4" />
              <div className="text-sm text-charcoal/65 leading-relaxed">{t.caption}</div>
            </PaperCard>
          ))}
        </div>
      </div>
    </section>
  );
}

function CompetitorsSection({
  competitors,
  loading,
}: {
  competitors: CompetitorRow[];
  loading: boolean;
}) {
  return (
    <section className="bg-cream-deep border-y border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <SectionLabel number="C" label="Competitors" />
        <h2 className="display-serif text-3xl text-charcoal mt-3">Brands fishing in the same pond.</h2>
        {loading && <p className="mt-4 text-sm text-charcoal/60">Loading competitor map…</p>}
        {!loading && competitors.length === 0 && (
          <PaperCard className="mt-6 p-8 text-charcoal/70">
            No overlapping competitors detected yet. Once vendors with shared categories or value tags publish, they'll show up here.
          </PaperCard>
        )}
        {competitors.length > 0 && (
          <div className="mt-6 grid gap-5 md:grid-cols-2">
            {competitors.map((c) => {
              const positionTone =
                c.price_position === "you priced higher"
                  ? "text-terracotta"
                  : c.price_position === "you priced lower"
                  ? "text-forest"
                  : "text-charcoal/65";
              return (
                <PaperCard key={c.vendor_user_id} className="p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="display-serif text-charcoal text-xl leading-tight">
                        {c.company_legal_name}
                      </div>
                      <div className="text-[0.65rem] uppercase tracking-widest text-charcoal/55 mt-1 num-display">
                        overlap score {c.overlap_score.toFixed(1)}
                      </div>
                    </div>
                    <Stamp color="azure" className="!text-[0.6rem]">
                      {c.overlap_product_count} overlap
                    </Stamp>
                  </div>
                  <div className="ink-divider my-4" />
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <Eyebrow>Their avg price</Eyebrow>
                      <div className="num-display text-charcoal text-2xl mt-1">{formatPrice(c.their_avg_price)}</div>
                    </div>
                    <div>
                      <Eyebrow>Your avg price</Eyebrow>
                      <div className="num-display text-charcoal text-2xl mt-1">{formatPrice(c.your_avg_price)}</div>
                    </div>
                  </div>
                  <div className={`mt-3 text-[0.7rem] uppercase tracking-wider font-semibold ${positionTone}`}>
                    {c.price_position}
                  </div>
                  {c.shared_categories.length > 0 && (
                    <div className="mt-4">
                      <Eyebrow>Shared categories</Eyebrow>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {c.shared_categories.map((cat) => (
                          <Stamp key={cat} color="charcoal" className="!text-[0.6rem]">
                            {cat}
                          </Stamp>
                        ))}
                      </div>
                    </div>
                  )}
                  {c.shared_tag_labels.length > 0 && (
                    <div className="mt-3">
                      <Eyebrow>Shared values</Eyebrow>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {c.shared_tag_labels.map((tag) => (
                          <Stamp key={tag} color="forest" className="!text-[0.6rem]">
                            {tag}
                          </Stamp>
                        ))}
                      </div>
                    </div>
                  )}
                  {c.co_recommendation_count > 0 && (
                    <div className="mt-4 text-xs text-charcoal/65">
                      Co-recommended alongside your products{" "}
                      <span className="font-semibold text-charcoal">{c.co_recommendation_count}</span>{" "}
                      time{c.co_recommendation_count === 1 ? "" : "s"} in the sampled feeds.
                    </div>
                  )}
                </PaperCard>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

function PricingSection({ rows, loading }: { rows: PricingInsightRow[]; loading: boolean }) {
  return (
    <section className="border-t border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <SectionLabel number="D" label="Pricing Intelligence" />
        <h2 className="display-serif text-3xl text-charcoal mt-3">Where your prices sit in the market.</h2>
        {loading && <p className="mt-4 text-sm text-charcoal/60">Pulling competitor prices…</p>}
        {!loading && rows.length === 0 && (
          <PaperCard className="mt-6 p-8 text-charcoal/70">
            Add categorized products to your catalog and we'll benchmark them against the rest of the WiseBuys marketplace here.
          </PaperCard>
        )}
        {rows.length > 0 && (
          <div className="mt-6 grid gap-5 md:grid-cols-2">
            {rows.map((row) => (
              <PaperCard key={row.category} className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <Eyebrow>Category</Eyebrow>
                    <div className="display-serif text-2xl text-charcoal mt-1">{row.category}</div>
                  </div>
                  <Stamp
                    color={
                      row.position === "premium" || row.position === "luxury"
                        ? "terracotta"
                        : row.position === "value"
                        ? "forest"
                        : "azure"
                    }
                    className="!text-[0.6rem]"
                  >
                    {row.position}
                  </Stamp>
                </div>
                <div className="ink-divider my-4" />
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <Eyebrow>You</Eyebrow>
                    <div className="num-display text-charcoal text-2xl mt-1">{formatPrice(row.your_avg_price)}</div>
                    <div className="text-xs text-charcoal/55 mt-1">
                      {formatPrice(row.your_min_price)} – {formatPrice(row.your_max_price)}
                    </div>
                  </div>
                  <div>
                    <Eyebrow>Market</Eyebrow>
                    <div className="num-display text-charcoal text-2xl mt-1">{formatPrice(row.market_median_price)}</div>
                    <div className="text-xs text-charcoal/55 mt-1">
                      {formatPrice(row.market_min_price)} – {formatPrice(row.market_max_price)}
                    </div>
                  </div>
                  <div>
                    <Eyebrow>Percentile</Eyebrow>
                    <div className="num-display text-charcoal text-2xl mt-1">{row.percentile.toFixed(0)}</div>
                    <div className="text-xs text-charcoal/55 mt-1">vs {row.market_sample_size} listings</div>
                  </div>
                </div>
                <div className="mt-4 h-2 bg-charcoal/10 rounded-sm overflow-hidden relative">
                  <div className="absolute top-0 bottom-0 w-px bg-charcoal/30" style={{ left: "50%" }} />
                  <div
                    className="h-full bg-terracotta"
                    style={{ width: `${Math.max(2, Math.min(100, row.percentile))}%` }}
                  />
                </div>
                <p className="mt-4 text-sm text-charcoal/80 leading-relaxed">{row.recommendation}</p>
              </PaperCard>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function TopProductsSection({
  products,
  recentClicks,
  loading,
}: {
  products: TopProductRow[];
  recentClicks: RecentClickRow[];
  loading: boolean;
}) {
  return (
    <section className="bg-cream-deep border-y border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <SectionLabel number="E" label="Product Performance" />
        <h2 className="display-serif text-3xl text-charcoal mt-3">What's actually landing in feeds.</h2>
        <div className="mt-6 grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <PaperCard className="p-0 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-cream/60 border-b border-charcoal/15">
                  <tr className="text-[0.6rem] uppercase tracking-widest text-charcoal/55">
                    <th className="text-left px-4 py-3 font-semibold">Product</th>
                    <th className="text-left px-3 py-3 font-semibold">Category</th>
                    <th className="text-right px-3 py-3 font-semibold">Price</th>
                    <th className="text-right px-3 py-3 font-semibold">Reach</th>
                    <th className="text-right px-4 py-3 font-semibold">Clicks</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-sm text-charcoal/60">
                        Loading…
                      </td>
                    </tr>
                  )}
                  {!loading && products.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-sm text-charcoal/60">
                        Publish products to start collecting performance data.
                      </td>
                    </tr>
                  )}
                  {products.map((p) => (
                    <tr key={p.product_id} className="border-b border-charcoal/10 last:border-b-0">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-charcoal">{p.name}</div>
                        {!p.is_published && (
                          <div className="text-[0.6rem] uppercase tracking-widest text-charcoal/45 mt-1">
                            unpublished
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3 text-charcoal/70">{p.category ?? "—"}</td>
                      <td className="px-3 py-3 text-right num-display text-charcoal">{formatPrice(p.price_hint)}</td>
                      <td className="px-3 py-3 text-right num-display text-charcoal">{p.recommendation_appearances}</td>
                      <td className="px-4 py-3 text-right num-display text-charcoal font-semibold">{p.click_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </PaperCard>
          </div>
          <div>
            <PaperCard className="p-6">
              <div className="flex items-center justify-between">
                <Eyebrow>Recent clicks</Eyebrow>
                <BarChart3 className="h-4 w-4 text-charcoal/45" strokeWidth={1.6} />
              </div>
              <div className="ink-divider my-4" />
              {recentClicks.length === 0 && (
                <p className="text-sm text-charcoal/65">
                  No clicks yet. Once a customer taps "Switch & Earn" on one of your products it'll appear here in real time.
                </p>
              )}
              {recentClicks.length > 0 && (
                <ul className="space-y-3">
                  {recentClicks.map((c) => (
                    <li key={c.id} className="flex items-start justify-between gap-3 text-sm">
                      <div>
                        <div className="font-semibold text-charcoal leading-tight">
                          {c.product_name ?? `Product #${c.product_id}`}
                        </div>
                        <div className="text-[0.65rem] uppercase tracking-widest text-charcoal/55 mt-1 inline-flex items-center gap-1">
                          <TagIcon className="h-3 w-3" /> {c.source}
                        </div>
                      </div>
                      <div className="text-xs text-charcoal/55 num-display whitespace-nowrap">
                        {formatRelativeTime(c.created_at)}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </PaperCard>
          </div>
        </div>
      </div>
    </section>
  );
}
