import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PaperCard, Eyebrow, SectionLabel, Stamp } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { VendorProductPublic, VendorProfilePublic } from "@/lib/types";

export const Route = createFileRoute("/vendor/catalog")({
  head: () => ({
    meta: [{ title: "Catalog — WiseBuys" }],
  }),
  component: VendorCatalogPage,
});

function VendorCatalogPage() {
  const auth = useRequireRole("vendor");
  const qc = useQueryClient();

  const profileQ = useQuery({
    queryKey: ["vendor", "me"],
    queryFn: () => apiFetch<VendorProfilePublic>("/api/vendors/me"),
    enabled: auth.ready && !!auth.token,
    retry: false,
  });

  const productsQ = useQuery({
    queryKey: ["catalog", "products"],
    queryFn: () => apiFetch<VendorProductPublic[]>("/api/catalog/products"),
    enabled: auth.ready && !!auth.token && !!profileQ.data,
  });

  const delM = useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/api/catalog/products/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Product removed");
      void qc.invalidateQueries({ queryKey: ["catalog", "products"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Delete failed"),
  });

  if (!auth.ready || !auth.token) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <span className="text-charcoal/60 text-sm">Loading…</span>
      </main>
    );
  }

  if (profileQ.isError || !profileQ.data) {
    return (
      <main className="flex-1 mx-auto max-w-2xl px-6 py-16">
        <PaperCard className="p-8 text-center">
          <Eyebrow>Not quite yet</Eyebrow>
          <h1 className="display-serif text-3xl text-charcoal mt-2">Catalog unlocks after approval</h1>
          <p className="mt-3 text-sm text-charcoal/70">Finish your application or wait for admin review.</p>
          <Link
            to="/vendor/apply"
            className="mt-6 inline-block bg-terracotta text-cream px-6 py-3 text-sm font-semibold rounded-sm"
          >
            Apply
          </Link>
        </PaperCard>
      </main>
    );
  }

  return (
    <main className="flex-1 mx-auto max-w-7xl w-full px-5 sm:px-8 py-12">
        <Link to="/vendor" className="text-sm text-charcoal/60 hover:text-terracotta underline underline-offset-4">
          ← Vendor desk
        </Link>
        <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <SectionLabel number="§ C" label="Catalog" />
            <h1 className="display-serif text-4xl text-charcoal mt-2">Your products</h1>
          </div>
          <Link
            to="/vendor/catalog/new"
            className="bg-charcoal text-cream px-5 py-2.5 text-sm font-semibold rounded-sm hover:bg-terracotta transition-colors"
          >
            Add product
          </Link>
        </div>

        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {(productsQ.data ?? []).map((p) => (
            <PaperCard key={p.id} className="p-6">
              <div className="flex justify-between gap-2">
                <h2 className="display-serif text-xl text-charcoal leading-tight">{p.name}</h2>
                {p.is_published && (
                  <Stamp color="forest" className="!text-[0.6rem] shrink-0">
                    Live
                  </Stamp>
                )}
              </div>
              <p className="text-sm text-charcoal/65 mt-2 line-clamp-3">{p.differentiator ?? "—"}</p>
              <div className="mt-4 num-display text-charcoal">
                {p.price_hint != null ? `${p.currency} ${p.price_hint}` : "—"}
              </div>
              <div className="mt-4 flex gap-2">
                <Link to="/vendor/catalog/$productId" params={{ productId: String(p.id) }} className="text-xs font-semibold text-terracotta underline">
                  Edit
                </Link>
                <button
                  type="button"
                  className="text-xs font-semibold text-charcoal/55 hover:text-terracotta"
                  onClick={() => {
                    if (confirm("Delete this product?")) delM.mutate(p.id);
                  }}
                >
                  Delete
                </button>
              </div>
            </PaperCard>
          ))}
        </div>
        {(productsQ.data ?? []).length === 0 && !productsQ.isLoading && (
          <PaperCard className="mt-8 p-10 text-center text-charcoal/70">No products yet. Add your first.</PaperCard>
        )}
    </main>
  );
}
