import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { PaperCard, Eyebrow, SectionLabel } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { VendorProductPublic, VendorProfilePublic } from "@/lib/types";

export const Route = createFileRoute("/vendor/catalog/$productId")({
  head: () => ({
    meta: [{ title: "Edit product — WiseBuys" }],
  }),
  component: EditProductPage,
});

function EditProductPage() {
  const { productId } = Route.useParams();
  const auth = useRequireRole("vendor");
  const navigate = useNavigate();
  const qc = useQueryClient();
  const id = Number(productId);

  const productQ = useQuery({
    queryKey: ["catalog", "product", id],
    queryFn: () => apiFetch<VendorProductPublic>(`/api/catalog/products/${id}`),
    enabled: auth.ready && !!auth.token && Number.isFinite(id),
  });

  const profileQ = useQuery({
    queryKey: ["vendor", "me"],
    queryFn: () => apiFetch<VendorProfilePublic>("/api/vendors/me"),
    enabled: auth.ready && !!auth.token,
    retry: false,
  });
  const allowedTags = profileQ.data?.allowed_tags ?? [];

  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [category, setCategory] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [priceHint, setPriceHint] = useState("");
  const [differentiator, setDifferentiator] = useState("");
  const [keyFeatures, setKeyFeatures] = useState("");
  const [isPublished, setIsPublished] = useState(false);
  const [tagIds, setTagIds] = useState<number[]>([]);

  useEffect(() => {
    const p = productQ.data;
    if (!p) return;
    setName(p.name);
    setSku(p.sku ?? "");
    setCategory(p.category ?? "");
    setCurrency(p.currency);
    setPriceHint(p.price_hint != null ? String(p.price_hint) : "");
    setDifferentiator(p.differentiator ?? "");
    setKeyFeatures((p.key_features ?? []).join("\n"));
    setIsPublished(p.is_published);
    setTagIds((p.tags ?? []).map((t) => t.id));
  }, [productQ.data]);

  const toggleTag = (tid: number) =>
    setTagIds((prev) => (prev.includes(tid) ? prev.filter((x) => x !== tid) : [...prev, tid]));

  const saveM = useMutation({
    mutationFn: () =>
      apiFetch<VendorProductPublic>(`/api/catalog/products/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name,
          sku: sku.trim() || null,
          category: category.trim() || null,
          currency,
          price_hint: priceHint.trim() ? Number(priceHint) : null,
          differentiator: differentiator.trim() || null,
          key_features: keyFeatures
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
          is_published: isPublished,
          tag_ids: tagIds,
        }),
      }),
    onSuccess: () => {
      toast.success("Saved");
      void qc.invalidateQueries({ queryKey: ["catalog", "products"] });
      void qc.invalidateQueries({ queryKey: ["catalog", "product", id] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Save failed"),
  });

  const delM = useMutation({
    mutationFn: () => apiFetch<void>(`/api/catalog/products/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Deleted");
      void navigate({ to: "/vendor/catalog" });
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

  return (
    <main className="flex-1 mx-auto max-w-2xl w-full px-5 sm:px-8 py-12">
        <Link to="/vendor/catalog" className="text-sm text-charcoal/60 hover:text-terracotta underline underline-offset-4">
          ← Catalog
        </Link>
        <SectionLabel number="§ C" label="Edit product" />
        <h1 className="display-serif text-4xl text-charcoal mt-4">Edit product</h1>
        {productQ.isLoading && <p className="mt-4 text-sm text-charcoal/60">Loading…</p>}
        {productQ.isError && (
          <PaperCard className="mt-6 p-6 text-terracotta text-sm">Could not load product.</PaperCard>
        )}
        {productQ.data && (
          <PaperCard className="mt-8 p-8 space-y-4">
            <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm" required />
            </label>
            <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
              SKU
              <input value={sku} onChange={(e) => setSku(e.target.value)} className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm" />
            </label>
            <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
              Category
              <input value={category} onChange={(e) => setCategory(e.target.value)} className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm" />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
                Currency
                <input value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase().slice(0, 3))} className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm" />
              </label>
              <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
                Price hint
                <input value={priceHint} onChange={(e) => setPriceHint(e.target.value)} type="number" step="0.01" className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm" />
              </label>
            </div>
            <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
              Differentiator
              <textarea value={differentiator} onChange={(e) => setDifferentiator(e.target.value)} rows={3} className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm" />
            </label>
            <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
              Key features (one per line)
              <textarea value={keyFeatures} onChange={(e) => setKeyFeatures(e.target.value)} rows={4} className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm" />
            </label>
            <div>
              <Eyebrow>Value tags</Eyebrow>
              <p className="mt-1 text-xs text-charcoal/60">
                Pick the values this specific product is verified for. Only your approved allow-list shows.
              </p>
              {allowedTags.length === 0 ? (
                <p className="mt-3 text-xs text-charcoal/55 italic">
                  No allowed tags yet. Ask an admin to expand your application's allow-list.
                </p>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  {allowedTags.map((t) => {
                    const active = tagIds.includes(t.id);
                    return (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => toggleTag(t.id)}
                        className={`text-[0.65rem] uppercase tracking-widest font-semibold px-3 py-1.5 rounded-sm border transition-colors ${
                          active
                            ? "bg-terracotta text-cream border-terracotta"
                            : "bg-cream-deep text-charcoal border-charcoal/20 hover:border-terracotta hover:text-terracotta"
                        }`}
                      >
                        {t.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <label className="flex items-center gap-2 text-sm text-charcoal cursor-pointer">
              <input type="checkbox" checked={isPublished} onChange={(e) => setIsPublished(e.target.checked)} className="accent-terracotta" />
              Published
            </label>
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="button"
                disabled={saveM.isPending}
                onClick={() => saveM.mutate()}
                className="bg-terracotta text-cream px-6 py-2.5 text-sm font-semibold rounded-sm hover:bg-charcoal disabled:opacity-50"
              >
                {saveM.isPending ? "Saving…" : "Save changes"}
              </button>
              <button
                type="button"
                disabled={delM.isPending}
                onClick={() => {
                  if (confirm("Delete this product?")) delM.mutate();
                }}
                className="text-sm text-charcoal/60 hover:text-terracotta underline"
              >
                Delete
              </button>
            </div>
          </PaperCard>
        )}
    </main>
  );
}
