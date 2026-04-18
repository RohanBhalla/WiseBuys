import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { PaperCard, Eyebrow, SectionLabel } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { VendorProductPublic } from "@/lib/types";

export const Route = createFileRoute("/vendor/catalog/new")({
  head: () => ({
    meta: [{ title: "New product — WiseBuys" }],
  }),
  component: NewProductPage,
});

function NewProductPage() {
  const auth = useRequireRole("vendor");
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [category, setCategory] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [priceHint, setPriceHint] = useState("");
  const [differentiator, setDifferentiator] = useState("");
  const [keyFeatures, setKeyFeatures] = useState("");
  const [isPublished, setIsPublished] = useState(false);

  const saveM = useMutation({
    mutationFn: () =>
      apiFetch<VendorProductPublic>("/api/catalog/products", {
        method: "POST",
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
        }),
      }),
    onSuccess: (p) => {
      toast.success("Product created");
      void navigate({ to: "/vendor/catalog/$productId", params: { productId: String(p.id) } });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Save failed"),
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
        <SectionLabel number="§ C" label="New product" />
        <h1 className="display-serif text-4xl text-charcoal mt-4">Add a product</h1>
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
          <label className="flex items-center gap-2 text-sm text-charcoal cursor-pointer">
            <input type="checkbox" checked={isPublished} onChange={(e) => setIsPublished(e.target.checked)} className="accent-terracotta" />
            Published
          </label>
          <button
            type="button"
            disabled={saveM.isPending || !name.trim()}
            onClick={() => saveM.mutate()}
            className="w-full bg-terracotta text-cream py-3 text-sm font-semibold rounded-sm hover:bg-charcoal disabled:opacity-50"
          >
            {saveM.isPending ? "Saving…" : "Create product"}
          </button>
        </PaperCard>
    </main>
  );
}
