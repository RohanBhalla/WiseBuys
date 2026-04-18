import KnotapiJS from "knotapi-js";

export type KnotEnvironment = "development" | "production" | "sandbox";

export interface OpenKnotLinkOptions {
  sessionId: string;
  clientId: string;
  environment: KnotEnvironment;
  merchantIds: number[];
  onSuccess?: (merchantId: number) => void;
  onError?: (message: string) => void;
  onExit?: () => void;
}

/**
 * Opens Knot Web SDK (Transaction Link). Requires `knotapi-js` and dashboard domain allowlist.
 *
 * Knot’s Web docs: `onSuccess` is described for **card switched** flows; **Transaction Link**
 * signals a finished login via `onEvent` with `event === "AUTHENTICATED"`. We handle both and
 * de-dupe so `onSuccess` (here: merchant linked) runs once.
 */
export function openKnotTransactionLink(opts: OpenKnotLinkOptions): void {
  const clientId = (import.meta.env.VITE_KNOT_CLIENT_ID as string | undefined) || opts.clientId;
  const env =
    (import.meta.env.VITE_KNOT_ENVIRONMENT as KnotEnvironment | undefined) || opts.environment;

  let linkedFired = false;
  const fireLinked = (mid: number) => {
    if (linkedFired) return;
    linkedFired = true;
    opts.onSuccess?.(mid);
  };

  const fallbackMerchantId = opts.merchantIds[0] ?? 0;

  const knotapi = new KnotapiJS();
  knotapi.open({
    sessionId: opts.sessionId,
    clientId,
    environment: env,
    product: "transaction_link",
    merchantIds: opts.merchantIds,
    entryPoint: "onboarding",
    useCategories: true,
    useSearch: true,
    onSuccess: (knotSuccess) => {
      const parsed = Number(knotSuccess.merchant);
      const mid = Number.isFinite(parsed) ? parsed : fallbackMerchantId;
      fireLinked(mid);
    },
    onEvent: (knotEvent) => {
      const name = String(knotEvent.event ?? "").toUpperCase();
      if (name !== "AUTHENTICATED") return;
      const parsed = Number(knotEvent.merchantId ?? knotEvent.merchant);
      const mid = Number.isFinite(parsed) ? parsed : fallbackMerchantId;
      fireLinked(mid);
    },
    onError: (knotError) => {
      opts.onError?.(knotError.errorDescription || knotError.errorCode || "Knot error");
    },
    onExit: () => opts.onExit?.(),
  });
}
