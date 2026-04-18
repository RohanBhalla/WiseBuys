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
 */
export function openKnotTransactionLink(opts: OpenKnotLinkOptions): void {
  const clientId = (import.meta.env.VITE_KNOT_CLIENT_ID as string | undefined) || opts.clientId;
  const env =
    (import.meta.env.VITE_KNOT_ENVIRONMENT as KnotEnvironment | undefined) || opts.environment;
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
      const mid = Number.isFinite(parsed) ? parsed : opts.merchantIds[0]!;
      opts.onSuccess?.(mid);
    },
    onError: (knotError) => {
      opts.onError?.(knotError.errorDescription || knotError.errorCode || "Knot error");
    },
    onExit: () => opts.onExit?.(),
  });
}
