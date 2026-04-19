import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, ExternalLink, Link2, RefreshCw, Webhook, X } from "lucide-react";
import { toast } from "sonner";
import { PaperCard, Eyebrow, SectionLabel, Stamp } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { openKnotTransactionLink } from "@/lib/knot";
import { cn } from "@/lib/utils";
import type {
  CreateSessionResponse,
  DevSimulateAck,
  KnotMerchantLite,
  KnotPurchasesMeta,
  LineItemPublic,
  MerchantAccountPublic,
  PurchasePublic,
  SyncResponse,
} from "@/lib/types";

const KNOT_ENV = (import.meta.env.VITE_KNOT_ENVIRONMENT ?? "development") as
  | "development"
  | "production"
  | "sandbox";

export const Route = createFileRoute("/dashboard/connect")({
  head: () => ({
    meta: [{ title: "Link purchases — WiseBuys" }],
  }),
  component: ConnectPage,
});

/** When Knot list API fails: doc examples (IDs from Knot docs; confirm in your dashboard if needed). */
const KNOT_DEV_FALLBACK_MERCHANTS: KnotMerchantLite[] = [
  { id: 45, name: "Walmart (Knot docs example)" },
  { id: 19, name: "DoorDash (Knot quickstart)" },
];

const PURCHASE_PAGE_SIZES = [25, 50, 100, 200] as const;
type PurchasePageSize = (typeof PURCHASE_PAGE_SIZES)[number];

function selectShellClassName(disabled?: boolean) {
  return cn(
    "mt-1.5 block w-full min-w-[10rem] rounded-sm border border-charcoal/15 bg-cream px-3 py-2 text-sm text-charcoal shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-terracotta/40 focus-visible:border-terracotta/50",
    disabled && "opacity-50 cursor-not-allowed",
  );
}

function formatOccurredAt(iso: string | null): string {
  if (!iso) return "Date unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(d);
}

function formatMoney(amount: string | number | null, currency: string | null): string {
  if (amount == null || amount === "") return "—";
  const n = typeof amount === "number" ? amount : Number.parseFloat(String(amount));
  if (!Number.isFinite(n)) return String(amount);
  const code = (currency && currency.length === 3 ? currency : "USD").toUpperCase();
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: code,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${code} ${n.toFixed(2)}`;
  }
}

function formatLineMoney(li: LineItemPublic, orderCurrency: string | null): string | null {
  if (li.total != null && li.total !== "") return formatMoney(li.total, orderCurrency);
  if (li.unit_price != null && li.quantity != null) {
    const u = typeof li.unit_price === "number" ? li.unit_price : Number.parseFloat(String(li.unit_price));
    const q = li.quantity;
    if (Number.isFinite(u) && typeof q === "number" && q > 0) {
      return formatMoney(u * q, orderCurrency);
    }
  }
  return null;
}

function shortTxnId(id: string): string {
  if (id.length <= 18) return id;
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

function PurchaseDetailRow({
  purchase: p,
  logoUrl,
}: {
  purchase: PurchasePublic;
  logoUrl: string | null | undefined;
}) {
  const merchant = p.merchant_name ?? `Merchant ${p.knot_merchant_id}`;
  const lines = p.line_items ?? [];
  const preview = lines.slice(0, 5);
  const rest = Math.max(0, lines.length - preview.length);

  return (
    <article className="border-b border-charcoal/10 py-4 last:border-0">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          <MerchantAvatar name={p.merchant_name} logoUrl={logoUrl} size="sm" className="mt-0.5" />
          <div className="min-w-0 flex-1 space-y-2">
            <div>
              <div className="font-semibold text-charcoal leading-tight">{merchant}</div>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-charcoal/60">
                <time dateTime={p.occurred_at ?? undefined}>{formatOccurredAt(p.occurred_at)}</time>
                {p.order_status ? (
                  <>
                    <span className="text-charcoal/30" aria-hidden>
                      ·
                    </span>
                    <Stamp color="forest" className="!text-[0.6rem]">
                      {p.order_status}
                    </Stamp>
                  </>
                ) : null}
                <span className="text-charcoal/30" aria-hidden>
                  ·
                </span>
                <span className="num-display font-mono text-[0.7rem] text-charcoal/50" title={p.knot_transaction_id}>
                  {shortTxnId(p.knot_transaction_id)}
                </span>
                {p.url ? (
                  <>
                    <span className="text-charcoal/30" aria-hidden>
                      ·
                    </span>
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-semibold text-terracotta hover:text-charcoal underline underline-offset-2"
                    >
                      Order
                      <ExternalLink className="h-3 w-3 shrink-0 opacity-80" aria-hidden />
                    </a>
                  </>
                ) : null}
              </div>
            </div>
            {preview.length > 0 ? (
              <ul className="space-y-1 border-l-2 border-terracotta/25 pl-3 text-xs text-charcoal/80">
                {preview.map((li) => {
                  const sub = formatLineMoney(li, p.currency);
                  return (
                    <li key={li.id} className="flex gap-3 justify-between">
                      <span className="min-w-0 truncate" title={li.description ?? undefined}>
                        {li.name}
                        {li.quantity != null && li.quantity > 1 ? (
                          <span className="num-display text-charcoal/45"> ×{li.quantity}</span>
                        ) : null}
                      </span>
                      {sub ? <span className="shrink-0 num-display text-charcoal/70">{sub}</span> : null}
                    </li>
                  );
                })}
                {rest > 0 ? (
                  <li className="text-charcoal/50 italic">+{rest} more line item{rest === 1 ? "" : "s"}</li>
                ) : null}
              </ul>
            ) : (
              <p className="text-xs text-charcoal/50 italic">No line items stored for this order.</p>
            )}
          </div>
        </div>
        <div className="shrink-0 text-left sm:text-right sm:pl-4">
          <div className="num-display text-lg font-semibold tabular-nums text-charcoal">{formatMoney(p.total, p.currency)}</div>
          {p.currency ? (
            <div className="mt-0.5 text-[0.65rem] font-medium uppercase tracking-wide text-charcoal/45">{p.currency}</div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function sortMerchantsForConnect(list: KnotMerchantLite[]): KnotMerchantLite[] {
  const rank = (name: string) => {
    const n = name.toLowerCase();
    if (n.includes("amazon")) return 0;
    if (n.includes("walmart")) return 1;
    if (n.includes("doordash")) return 2;
    return 50;
  };
  return [...list].sort((a, b) => {
    const ra = rank(a.name ?? "");
    const rb = rank(b.name ?? "");
    if (ra !== rb) return ra - rb;
    return (a.name ?? "").localeCompare(b.name ?? "");
  });
}

function MerchantAvatar({
  name,
  logoUrl,
  size = "md",
  className,
}: {
  name: string | null | undefined;
  logoUrl?: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const [broken, setBroken] = useState(false);
  const label = (name ?? "").trim() || "Merchant";
  const initial = label.charAt(0).toUpperCase();
  const showImg = Boolean(logoUrl) && !broken;
  const box =
    size === "lg" ? "h-14 w-14 min-h-14 min-w-14" : size === "sm" ? "h-9 w-9 min-h-9 min-w-9" : "h-11 w-11 min-h-11 min-w-11";

  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-md border border-charcoal/10 bg-cream-deep",
        box,
        className,
      )}
    >
      {showImg ? (
        <img
          src={logoUrl!}
          alt=""
          className="h-full w-full object-contain p-1.5"
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setBroken(true)}
        />
      ) : (
        <span className={cn("font-semibold text-charcoal/45", size === "lg" ? "text-lg" : "text-sm")}>{initial}</span>
      )}
    </div>
  );
}

function ConnectPage() {
  const auth = useRequireRole("customer");
  const qc = useQueryClient();
  const [merchantId, setMerchantId] = useState(19);
  const [purchasePageSize, setPurchasePageSize] = useState<PurchasePageSize>(50);
  const [purchaseOffset, setPurchaseOffset] = useState(0);
  const [purchaseMerchantFilter, setPurchaseMerchantFilter] = useState<number | null>(null);
  const [showRecommendationsCta, setShowRecommendationsCta] = useState(false);
  /** Bumps on each successful sync so the CTA remounts and the entrance animation runs again. */
  const [recommendationsCtaEnterKey, setRecommendationsCtaEnterKey] = useState(0);

  const merchantsQ = useQuery({
    queryKey: ["knot", "merchants"],
    queryFn: () => apiFetch<KnotMerchantLite[]>("/api/knot/merchants"),
    enabled: auth.ready && !!auth.token,
    retry: false,
  });

  const sortedMerchants = useMemo(() => {
    if (merchantsQ.data?.length) return sortMerchantsForConnect(merchantsQ.data);
    if (merchantsQ.isError) return KNOT_DEV_FALLBACK_MERCHANTS;
    return [];
  }, [merchantsQ.data, merchantsQ.isError]);

  const logoByMerchantId = useMemo(() => {
    const m = new Map<number, string | null>();
    for (const row of merchantsQ.data ?? []) {
      if (row.logo) m.set(row.id, row.logo);
    }
    return m;
  }, [merchantsQ.data]);

  const selectedMerchant = useMemo(
    () => sortedMerchants.find((x) => x.id === merchantId) ?? null,
    [sortedMerchants, merchantId],
  );

  const accountsQ = useQuery({
    queryKey: ["knot", "accounts"],
    queryFn: () => apiFetch<MerchantAccountPublic[]>("/api/knot/merchant-accounts"),
    enabled: auth.ready && !!auth.token,
  });

  const purchasesListUrl = useMemo(() => {
    const p = new URLSearchParams();
    p.set("limit", String(purchasePageSize));
    p.set("offset", String(purchaseOffset));
    if (purchaseMerchantFilter != null) p.set("merchant_id", String(purchaseMerchantFilter));
    return `/api/knot/purchases?${p.toString()}`;
  }, [purchasePageSize, purchaseOffset, purchaseMerchantFilter]);

  const purchasesMetaUrl = useMemo(() => {
    if (purchaseMerchantFilter != null) {
      return `/api/knot/purchases/meta?merchant_id=${purchaseMerchantFilter}`;
    }
    return "/api/knot/purchases/meta";
  }, [purchaseMerchantFilter]);

  useEffect(() => {
    setPurchaseOffset(0);
  }, [purchasePageSize, purchaseMerchantFilter]);

  const purchasesMetaQ = useQuery({
    queryKey: ["knot", "purchases-meta", purchaseMerchantFilter ?? "all"],
    queryFn: () => apiFetch<KnotPurchasesMeta>(purchasesMetaUrl),
    enabled: auth.ready && !!auth.token,
  });

  const purchasesQ = useQuery({
    queryKey: ["knot", "purchases", purchasePageSize, purchaseOffset, purchaseMerchantFilter ?? "all"],
    queryFn: () => apiFetch<PurchasePublic[]>(purchasesListUrl),
    enabled: auth.ready && !!auth.token,
  });

  const syncM = useMutation({
    mutationFn: (mid: number) =>
      apiFetch<SyncResponse>("/api/knot/sync", {
        method: "POST",
        body: JSON.stringify({ merchant_id: mid }),
      }),
    onSuccess: (data) => {
      toast.success(`Synced: ${data.transactions_persisted} transactions saved.`);
      void qc.invalidateQueries({ queryKey: ["knot", "accounts"] });
      void qc.invalidateQueries({ queryKey: ["knot", "purchases"] });
      void qc.invalidateQueries({ queryKey: ["knot", "purchases-meta"] });
      void qc.invalidateQueries({ queryKey: ["rewards", "me"] });
      void qc.invalidateQueries({ queryKey: ["insights", "spending"] });
      void qc.invalidateQueries({ queryKey: ["recommendations", "me"] });
      setRecommendationsCtaEnterKey((k) => k + 1);
      setShowRecommendationsCta(true);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Sync failed"),
  });

  const simulateLinkM = useMutation({
    mutationFn: (mid: number) =>
      apiFetch<DevSimulateAck>("/api/knot/dev/simulate-link", {
        method: "POST",
        body: JSON.stringify({
          merchant_id: mid,
          new_transactions: true,
          updated_transactions: true,
        }),
      }),
    onSuccess: (ack) => {
      toast.success(
        `Knot dev link requested for merchant ${ack.merchant_id}. Webhook should fire shortly.`,
      );
      // Webhooks land asynchronously; pulse the cached views so the
      // resulting account/purchases appear without a manual reload.
      setTimeout(() => {
        void qc.invalidateQueries({ queryKey: ["knot", "accounts"] });
        void qc.invalidateQueries({ queryKey: ["knot", "purchases"] });
        void qc.invalidateQueries({ queryKey: ["knot", "purchases-meta"] });
        void qc.invalidateQueries({ queryKey: ["recommendations", "me"] });
      }, 4000);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Dev link failed"),
  });

  const simulateDisconnectM = useMutation({
    mutationFn: (mid: number) =>
      apiFetch<DevSimulateAck>("/api/knot/dev/simulate-disconnect", {
        method: "POST",
        body: JSON.stringify({ merchant_id: mid }),
      }),
    onSuccess: (ack) => {
      toast.success(
        `Knot dev disconnect requested for merchant ${ack.merchant_id}. ACCOUNT_LOGIN_REQUIRED webhook coming.`,
      );
      setTimeout(() => {
        void qc.invalidateQueries({ queryKey: ["knot", "accounts"] });
      }, 4000);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Dev disconnect failed"),
  });

  const openKnot = useMutation({
    mutationFn: async () => {
      const session = await apiFetch<CreateSessionResponse>("/api/knot/sessions", {
        method: "POST",
        body: JSON.stringify({ merchant_id: merchantId, metadata: { source: "wisebuys_web" } }),
      });
      return session;
    },
    onSuccess: (session) => {
      try {
        openKnotTransactionLink({
          sessionId: session.session_id,
          clientId: session.client_id,
          environment: session.environment as "development" | "production" | "sandbox",
          merchantIds: [merchantId],
          onSuccess: (mid) => {
            toast.success("Merchant linked. Syncing…");
            syncM.mutate(mid);
          },
          onError: (msg) => toast.error(msg),
        });
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Could not open Knot");
      }
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not create Knot session"),
  });

  const purchaseTotal = purchasesMetaQ.data?.total ?? 0;
  const purchaseRows = purchasesQ.data ?? [];
  const rangeStart = purchaseTotal === 0 ? 0 : purchaseOffset + 1;
  const rangeEnd = purchaseTotal === 0 ? 0 : purchaseOffset + purchaseRows.length;
  const canPrev = purchaseOffset > 0;
  const canNext = purchaseOffset + purchasePageSize < purchaseTotal;

  if (!auth.ready || !auth.token) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <span className="text-charcoal/60 text-sm">Loading…</span>
      </main>
    );
  }

  return (
    <main className="flex-1 mx-auto max-w-7xl w-full px-5 sm:px-8 py-12">
      <Link
        to="/dashboard"
        className="text-sm text-charcoal/60 hover:text-terracotta underline underline-offset-4"
      >
        ← Back to dashboard
      </Link>
      <div className="mt-6">
        <SectionLabel number="§ TL" label="Transaction Link" />
      </div>
      <h1 className="display-serif text-4xl sm:text-5xl text-charcoal mt-3">Connect a merchant</h1>
      <p className="mt-3 text-charcoal/70 max-w-2xl">
        Pick where you shop, open Knot’s secure window to sign in, then we pull item-level purchases into WiseBuys.
        Configure webhooks in the Knot dashboard if you want automatic sync when new orders appear.
      </p>

      <ol className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-6 text-sm text-charcoal/75">
        <li className="flex items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-terracotta text-xs font-bold text-cream">
            1
          </span>
          <span className="leading-snug">Select a merchant (logo from Knot)</span>
        </li>
        <li className="hidden sm:block text-charcoal/25" aria-hidden>
          →
        </li>
        <li className="flex items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-charcoal text-xs font-bold text-cream">
            2
          </span>
          <span className="leading-snug flex items-center gap-1.5">
            <Link2 className="h-4 w-4 shrink-0 text-terracotta" aria-hidden />
            Open Knot & sign in
          </span>
        </li>
        <li className="hidden sm:block text-charcoal/25" aria-hidden>
          →
        </li>
        <li className="flex items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-charcoal/20 bg-cream text-xs font-bold text-charcoal">
            3
          </span>
          <span className="leading-snug flex items-center gap-1.5">
            <RefreshCw className="h-4 w-4 shrink-0 text-charcoal/50" aria-hidden />
            We sync purchases (or tap Sync now)
          </span>
        </li>
      </ol>

      <div className="mt-10 grid gap-6 lg:grid-cols-2">
        <PaperCard className="p-8">
          <Eyebrow>Choose merchant</Eyebrow>
          {merchantsQ.isLoading && <p className="mt-2 text-sm text-charcoal/60">Loading merchants…</p>}
          {merchantsQ.isError && (
            <p className="mt-2 text-sm text-charcoal/70">
              Could not load merchants from Knot (check <code className="bg-cream-deep px-1">KNOT_CLIENT_ID</code> /{" "}
              <code className="bg-cream-deep px-1">KNOT_SECRET</code> and Transaction Link access). Showing common dev
              IDs below without logos — reload after fixing keys to see real logos from Knot.
            </p>
          )}

          {!merchantsQ.isLoading && sortedMerchants.length > 0 && (
            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 max-h-[min(28rem,55vh)] overflow-y-auto pr-1">
              {sortedMerchants.map((m) => {
                const selected = merchantId === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setMerchantId(m.id)}
                    className={cn(
                      "flex items-start gap-3 rounded-md border p-3 text-left transition-colors",
                      selected
                        ? "border-terracotta bg-terracotta/10 ring-1 ring-terracotta/40"
                        : "border-charcoal/12 hover:border-charcoal/25 hover:bg-cream-deep/60",
                    )}
                  >
                    <MerchantAvatar name={m.name} logoUrl={m.logo} size="md" />
                    <div className="min-w-0 flex-1 pt-0.5">
                      <div className="font-semibold text-charcoal leading-tight">{m.name ?? `Merchant ${m.id}`}</div>
                      {m.category ? (
                        <div className="mt-1 text-xs text-charcoal/55 line-clamp-2">{m.category}</div>
                      ) : (
                        <div className="mt-1 num-display text-xs text-charcoal/40">ID {m.id}</div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {!merchantsQ.isLoading && sortedMerchants.length === 0 && (
            <p className="mt-4 text-sm text-charcoal/55">No merchants yet.</p>
          )}

          {selectedMerchant && (
            <div className="mt-6 flex items-center gap-3 rounded-md border border-charcoal/10 bg-cream-deep/40 p-4">
              <MerchantAvatar name={selectedMerchant.name} logoUrl={selectedMerchant.logo} size="lg" />
              <div className="min-w-0">
                <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-charcoal/45">Ready to link</div>
                <div className="font-semibold text-charcoal truncate">{selectedMerchant.name}</div>
                {selectedMerchant.category && (
                  <div className="text-xs text-charcoal/55 truncate">{selectedMerchant.category}</div>
                )}
              </div>
            </div>
          )}

          <button
            type="button"
            disabled={openKnot.isPending || syncM.isPending}
            onClick={() => openKnot.mutate()}
            className="mt-6 w-full bg-terracotta text-cream py-3 text-sm font-semibold rounded-sm hover:bg-charcoal transition-colors disabled:opacity-50"
          >
            {openKnot.isPending ? "Creating session…" : "Open Knot & link"}
          </button>
          <p className="mt-3 text-xs text-charcoal/50">
            Match <code className="bg-cream-deep px-1">VITE_KNOT_CLIENT_ID</code> and{" "}
            <code className="bg-cream-deep px-1">VITE_KNOT_ENVIRONMENT</code> to the session Knot returns.
          </p>
        </PaperCard>

        <PaperCard className="p-8">
          <Eyebrow>Linked accounts</Eyebrow>
          <p className="mt-2 text-sm text-charcoal/60">
            After linking, the merchant appears here. Use <strong className="font-semibold text-charcoal/80">Sync now</strong>{" "}
            to refresh purchases anytime.
          </p>
          <div className="mt-4 space-y-3">
            {(accountsQ.data ?? []).length === 0 && <p className="text-sm text-charcoal/60">None yet.</p>}
            {(accountsQ.data ?? []).map((a) => (
              <div
                key={a.id}
                className="flex flex-wrap items-center justify-between gap-3 border border-charcoal/10 rounded-md p-3"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <MerchantAvatar
                    name={a.merchant_name}
                    logoUrl={logoByMerchantId.get(a.knot_merchant_id) ?? null}
                    size="md"
                  />
                  <div className="min-w-0">
                    <div className="font-semibold text-charcoal truncate">
                      {a.merchant_name ?? `Merchant ${a.knot_merchant_id}`}
                    </div>
                    <div className="text-xs text-charcoal/55">
                      <Stamp color="charcoal" className="!text-[0.6rem]">
                        {a.connection_status}
                      </Stamp>
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => syncM.mutate(a.knot_merchant_id)}
                  disabled={syncM.isPending}
                  className="text-xs font-semibold bg-charcoal text-cream px-3 py-2 rounded-sm hover:bg-terracotta disabled:opacity-50"
                >
                  Sync now
                </button>
              </div>
            ))}
          </div>
        </PaperCard>
      </div>

      {showRecommendationsCta && (
        <PaperCard
          key={recommendationsCtaEnterKey}
          className="mt-8 p-6 md:p-8 border-terracotta/30 bg-gradient-to-br from-terracotta/[0.07] to-cream animate-paper-in"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <Eyebrow>Next step</Eyebrow>
              <p className="display-serif text-xl text-charcoal mt-2 leading-snug">
                View recommendations on your dashboard
              </p>
              <p className="mt-2 text-sm text-charcoal/70 max-w-2xl">
                Your purchase history just refreshed — open the dashboard to see value-aligned picks and explanations
                tied to what you buy.
              </p>
            </div>
            <div className="flex shrink-0 flex-col gap-2 sm:items-end">
              <Link
                to="/dashboard"
                hash="dashboard-recommendations"
                className="inline-flex w-full sm:w-auto items-center justify-center gap-2 bg-terracotta text-cream px-5 py-3 text-sm font-semibold rounded-sm hover:bg-charcoal transition-colors"
              >
                Go to recommendations
                <ArrowRight className="h-4 w-4 shrink-0" aria-hidden />
              </Link>
              <button
                type="button"
                onClick={() => setShowRecommendationsCta(false)}
                className="inline-flex items-center justify-center gap-1.5 text-xs font-medium text-charcoal/55 hover:text-charcoal"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
                Dismiss
              </button>
            </div>
          </div>
        </PaperCard>
      )}

      {KNOT_ENV === "development" && (
        <PaperCard className="mt-8 p-6 md:p-8 border-charcoal/15 bg-cream-deep/40">
          <div className="flex items-start gap-3">
            <Webhook className="mt-1 h-5 w-5 shrink-0 text-charcoal/60" aria-hidden />
            <div className="min-w-0 flex-1">
              <Eyebrow>Dev environment · webhook simulation</Eyebrow>
              <p className="mt-2 text-sm text-charcoal/70 max-w-3xl">
                Trigger Knot's{" "}
                <code className="bg-cream px-1">/development/accounts/link</code> and{" "}
                <code className="bg-cream px-1">/development/accounts/disconnect</code> for the
                selected merchant. Knot will POST to your configured webhook URL — your backend
                handles <strong className="font-semibold text-charcoal/85">AUTHENTICATED</strong>,{" "}
                <strong className="font-semibold text-charcoal/85">NEW_TRANSACTIONS_AVAILABLE</strong>,{" "}
                <strong className="font-semibold text-charcoal/85">UPDATED_TRANSACTIONS_AVAILABLE</strong>,
                and{" "}
                <strong className="font-semibold text-charcoal/85">ACCOUNT_LOGIN_REQUIRED</strong>.
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => simulateLinkM.mutate(merchantId)}
                  disabled={simulateLinkM.isPending}
                  className="inline-flex items-center gap-2 rounded-sm bg-charcoal px-4 py-2 text-xs font-semibold text-cream hover:bg-terracotta disabled:opacity-50"
                >
                  {simulateLinkM.isPending ? "Requesting…" : "Simulate link + new txns"}
                </button>
                <button
                  type="button"
                  onClick={() => simulateDisconnectM.mutate(merchantId)}
                  disabled={simulateDisconnectM.isPending}
                  className="inline-flex items-center gap-2 rounded-sm border border-charcoal/20 bg-cream px-4 py-2 text-xs font-semibold text-charcoal hover:border-charcoal/40 disabled:opacity-50"
                >
                  {simulateDisconnectM.isPending ? "Requesting…" : "Simulate disconnect"}
                </button>
                <span className="text-xs text-charcoal/55">
                  Targets merchant <span className="num-display font-semibold">{merchantId}</span>
                  {selectedMerchant?.name ? ` (${selectedMerchant.name})` : ""}.
                </span>
              </div>
            </div>
          </div>
        </PaperCard>
      )}

      <PaperCard className="mt-8 p-8">
        <Eyebrow>Stored purchases</Eyebrow>
        <p className="mt-2 text-sm text-charcoal/60">
          Browse what WiseBuys has saved from Knot (up to 200 per page). Use filters and pagination for larger histories.
        </p>

        <div className="mt-5 flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end lg:justify-between">
          <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
            <label className="text-[0.65rem] font-semibold uppercase tracking-widest text-charcoal/45">
              Rows per page
              <select
                className={selectShellClassName()}
                value={purchasePageSize}
                onChange={(e) => setPurchasePageSize(Number(e.target.value) as PurchasePageSize)}
              >
                {PURCHASE_PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[0.65rem] font-semibold uppercase tracking-widest text-charcoal/45">
              Merchant
              <select
                className={selectShellClassName(!(accountsQ.data ?? []).length)}
                value={purchaseMerchantFilter ?? ""}
                disabled={!(accountsQ.data ?? []).length}
                onChange={(e) => {
                  const v = e.target.value;
                  setPurchaseMerchantFilter(v === "" ? null : Number(v));
                }}
              >
                <option value="">All linked</option>
                {(accountsQ.data ?? []).map((a) => (
                  <option key={a.id} value={a.knot_merchant_id}>
                    {a.merchant_name ?? `Merchant ${a.knot_merchant_id}`}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="text-xs text-charcoal/55 lg:text-right">
            {purchasesMetaQ.isLoading && "Counting rows…"}
            {!purchasesMetaQ.isLoading &&
              (purchaseTotal === 0
                ? "No rows match this filter."
                : `Showing ${rangeStart}–${rangeEnd} of ${purchaseTotal}`)}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!canPrev || purchasesQ.isLoading}
              onClick={() => setPurchaseOffset((o) => Math.max(0, o - purchasePageSize))}
              className="rounded-sm border border-charcoal/15 bg-cream px-3 py-2 text-xs font-semibold text-charcoal hover:border-charcoal/30 disabled:opacity-40"
            >
              Previous page
            </button>
            <button
              type="button"
              disabled={!canNext || purchasesQ.isLoading}
              onClick={() => setPurchaseOffset((o) => o + purchasePageSize)}
              className="rounded-sm border border-charcoal/15 bg-cream px-3 py-2 text-xs font-semibold text-charcoal hover:border-charcoal/30 disabled:opacity-40"
            >
              Next page
            </button>
          </div>
        </div>

        <div className="mt-4 max-h-[min(32rem,70vh)] overflow-y-auto text-sm">
          {purchaseRows.map((p) => (
            <PurchaseDetailRow key={p.id} purchase={p} logoUrl={logoByMerchantId.get(p.knot_merchant_id) ?? null} />
          ))}
          {!purchasesQ.isLoading && purchaseRows.length === 0 && (
            <p className="text-charcoal/60">No purchases stored yet for this view — try another merchant or run Sync now.</p>
          )}
          {purchasesQ.isLoading && <p className="text-charcoal/55">Loading purchases…</p>}
        </div>
      </PaperCard>
    </main>
  );
}
