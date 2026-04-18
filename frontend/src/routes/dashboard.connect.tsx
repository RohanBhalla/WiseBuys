import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { PaperCard, Eyebrow, SectionLabel, Stamp } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { openKnotTransactionLink } from "@/lib/knot";
import { cn } from "@/lib/utils";
import type {
  CreateSessionResponse,
  KnotMerchantLite,
  MerchantAccountPublic,
  PurchasePublic,
  SyncResponse,
} from "@/lib/types";

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

  const purchasesQ = useQuery({
    queryKey: ["knot", "purchases"],
    queryFn: () => apiFetch<PurchasePublic[]>("/api/knot/purchases?limit=20"),
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
      void qc.invalidateQueries({ queryKey: ["rewards", "me"] });
      void qc.invalidateQueries({ queryKey: ["insights", "spending"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Sync failed"),
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

      <PaperCard className="mt-8 p-8">
        <Eyebrow>Recent purchases</Eyebrow>
        <p className="mt-2 text-sm text-charcoal/60">Last 20 orders stored for recommendations and insights.</p>
        <div className="mt-4 space-y-1 max-h-96 overflow-y-auto text-sm">
          {(purchasesQ.data ?? []).map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between gap-3 border-b border-charcoal/10 py-2.5 last:border-0"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <MerchantAvatar
                  name={p.merchant_name}
                  logoUrl={logoByMerchantId.get(p.knot_merchant_id) ?? null}
                  size="sm"
                />
                <span className="text-charcoal/80 truncate">{p.merchant_name ?? `Merchant ${p.knot_merchant_id}`}</span>
              </div>
              <span className="num-display text-charcoal/70 shrink-0">{p.total != null ? String(p.total) : "—"}</span>
            </div>
          ))}
          {(purchasesQ.data ?? []).length === 0 && <p className="text-charcoal/60">No purchases stored yet.</p>}
        </div>
      </PaperCard>
    </main>
  );
}
