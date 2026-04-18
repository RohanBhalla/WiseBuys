import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { PaperCard, Eyebrow, SectionLabel, Stamp } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { openKnotTransactionLink } from "@/lib/knot";
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
        <Link to="/dashboard" className="text-sm text-charcoal/60 hover:text-terracotta underline underline-offset-4">
          ← Back to dashboard
        </Link>
        <div className="mt-6">
          <SectionLabel number="§ TL" label="Transaction Link" />
        </div>
        <h1 className="display-serif text-4xl sm:text-5xl text-charcoal mt-3">Connect a merchant</h1>
        <p className="mt-3 text-charcoal/70 max-w-2xl">
          Choose a merchant, create a Knot session, then sign in via the Knot modal. After linking, we sync SKU-level
          purchases into WiseBuys. Webhook URL in the Knot dashboard should reach your FastAPI host (e.g. ngrok).
        </p>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <PaperCard className="p-8">
            <Eyebrow>Merchant</Eyebrow>
            {merchantsQ.isLoading && <p className="mt-2 text-sm text-charcoal/60">Loading merchants…</p>}
            {merchantsQ.isError && (
              <p className="mt-2 text-sm text-charcoal/70">
                Could not load merchants from Knot (check <code className="bg-cream-deep px-1">KNOT_CLIENT_ID</code> /{" "}
                <code className="bg-cream-deep px-1">KNOT_SECRET</code> and Transaction Link access). Showing common dev
                IDs. After keys work, reload — Amazon and Walmart appear from Knot (sorted to the top).
              </p>
            )}
            <div className="mt-4 space-y-2 max-h-64 overflow-y-auto">
              {!merchantsQ.isLoading &&
                sortedMerchants.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setMerchantId(m.id)}
                    className={`w-full text-left px-3 py-2 rounded-sm border text-sm ${
                      merchantId === m.id ? "border-terracotta bg-terracotta/10" : "border-charcoal/15 hover:border-charcoal/30"
                    }`}
                  >
                    <span className="font-semibold text-charcoal">{m.name ?? `Merchant ${m.id}`}</span>
                    <span className="num-display text-charcoal/50 ml-2">#{m.id}</span>
                  </button>
                ))}
              {!merchantsQ.isLoading && sortedMerchants.length === 0 && (
                <p className="text-sm text-charcoal/55">No merchants yet.</p>
              )}
            </div>
            <button
              type="button"
              disabled={openKnot.isPending || syncM.isPending}
              onClick={() => openKnot.mutate()}
              className="mt-6 w-full bg-terracotta text-cream py-3 text-sm font-semibold rounded-sm hover:bg-charcoal transition-colors disabled:opacity-50"
            >
              {openKnot.isPending ? "Creating session…" : "Open Knot & link"}
            </button>
            <p className="mt-3 text-xs text-charcoal/50">
              Set <code className="bg-cream-deep px-1">VITE_KNOT_CLIENT_ID</code> and{" "}
              <code className="bg-cream-deep px-1">VITE_KNOT_ENVIRONMENT</code> to match your Knot dashboard.
            </p>
          </PaperCard>

          <PaperCard className="p-8">
            <Eyebrow>Linked accounts</Eyebrow>
            <div className="mt-4 space-y-3">
              {(accountsQ.data ?? []).length === 0 && <p className="text-sm text-charcoal/60">None yet.</p>}
              {(accountsQ.data ?? []).map((a) => (
                <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 border border-charcoal/10 rounded-sm p-3">
                  <div>
                    <div className="font-semibold text-charcoal">{a.merchant_name ?? `Merchant ${a.knot_merchant_id}`}</div>
                    <div className="text-xs text-charcoal/55">
                      <Stamp color="charcoal" className="!text-[0.6rem]">
                        {a.connection_status}
                      </Stamp>
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
          <div className="mt-4 space-y-2 max-h-96 overflow-y-auto text-sm">
            {(purchasesQ.data ?? []).map((p) => (
              <div key={p.id} className="border-b border-charcoal/10 py-2 flex justify-between gap-4">
                <span className="text-charcoal/80">{p.merchant_name ?? `Merchant ${p.knot_merchant_id}`}</span>
                <span className="num-display text-charcoal/70 shrink-0">{p.total != null ? String(p.total) : "—"}</span>
              </div>
            ))}
            {(purchasesQ.data ?? []).length === 0 && <p className="text-charcoal/60">No purchases stored yet.</p>}
          </div>
        </PaperCard>
    </main>
  );
}
