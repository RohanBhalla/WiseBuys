import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { PaperCard, Eyebrow, SectionLabel } from "@/components/Primitives";
import { apiFetch, ApiError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { TagPublic, VendorApplicationPublic } from "@/lib/types";

export const Route = createFileRoute("/vendor/apply")({
  head: () => ({
    meta: [{ title: "Vendor application — WiseBuys" }],
  }),
  component: VendorApplyPage,
});

function VendorApplyPage() {
  const auth = useRequireAuth();
  const navigate = useNavigate();
  const [companyLegalName, setCompanyLegalName] = useState("");
  const [companyWebsite, setCompanyWebsite] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [country, setCountry] = useState("");
  const [narrative, setNarrative] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [tagIds, setTagIds] = useState<Set<number>>(new Set());

  const tagsQ = useQuery({
    queryKey: ["tags"],
    queryFn: () => apiFetch<TagPublic[]>("/api/tags"),
    enabled: auth.ready && !!auth.token,
  });

  useEffect(() => {
    if (auth.me?.email && !contactEmail) setContactEmail(auth.me.email);
  }, [auth.me?.email, contactEmail]);

  const submitM = useMutation({
    mutationFn: async () => {
      const evidence_urls = evidenceUrl.trim()
        ? [evidenceUrl.trim()]
        : [];
      return apiFetch<VendorApplicationPublic>("/api/vendors/applications", {
        method: "POST",
        body: JSON.stringify({
          company_legal_name: companyLegalName,
          company_website: companyWebsite.trim() || null,
          contact_email: contactEmail,
          country: country.trim().toUpperCase().slice(0, 2) || null,
          narrative: narrative.trim() || null,
          requested_tag_ids: [...tagIds],
          evidence_urls,
        }),
      });
    },
    onSuccess: () => {
      toast.success("Application submitted. We’ll be insufferably thorough.");
      void navigate({ to: "/vendor" });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Submit failed"),
  });

  if (!auth.ready || !auth.token) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <span className="text-charcoal/60 text-sm">Loading…</span>
      </main>
    );
  }

  if (auth.role !== "vendor" && auth.role !== "customer") {
    return (
      <main className="flex-1 flex items-center justify-center px-6">
        <PaperCard className="p-8 max-w-md text-center">
          <p className="text-charcoal">Vendor or shopper accounts only.</p>
          <Link to="/login" className="mt-4 inline-block text-terracotta font-semibold underline">
            Sign in
          </Link>
        </PaperCard>
      </main>
    );
  }

  return (
    <main className="flex-1 mx-auto max-w-3xl w-full px-5 sm:px-8 py-14">
        <Link to="/vendor" className="text-sm text-charcoal/60 hover:text-terracotta underline underline-offset-4">
          ← Vendor home
        </Link>
        <SectionLabel number="§ V" label="Join the marketplace" />
        <h1 className="display-serif text-4xl text-charcoal mt-4">Vendor application</h1>
        <p className="mt-3 text-charcoal/70">
          Select value tags you can substantiate. Admins review every application before catalog access.
        </p>

        <PaperCard className="mt-8 p-8 space-y-4">
          <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
            Legal company name
            <input
              value={companyLegalName}
              onChange={(e) => setCompanyLegalName(e.target.value)}
              className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
              required
            />
          </label>
          <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
            Website (optional)
            <input
              value={companyWebsite}
              onChange={(e) => setCompanyWebsite(e.target.value)}
              placeholder="https://"
              className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
            />
          </label>
          <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
            Contact email
            <input
              type="email"
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
              required
            />
          </label>
          <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
            Country (ISO-2, optional)
            <input
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              maxLength={2}
              placeholder="US"
              className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal uppercase"
            />
          </label>
          <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
            Narrative
            <textarea
              value={narrative}
              onChange={(e) => setNarrative(e.target.value)}
              rows={4}
              className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
            />
          </label>
          <label className="block text-xs font-semibold tracking-widest text-charcoal/55 uppercase">
            Evidence URL (optional)
            <input
              value={evidenceUrl}
              onChange={(e) => setEvidenceUrl(e.target.value)}
              placeholder="https://…"
              className="mt-1.5 w-full border border-charcoal/15 rounded-sm bg-cream-deep px-3 py-2.5 text-sm text-charcoal"
            />
          </label>

          <div>
            <Eyebrow>Requested tags</Eyebrow>
            <div className="mt-3 flex flex-wrap gap-2">
              {(tagsQ.data ?? []).map((t) => {
                const on = tagIds.has(t.id);
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => {
                      const n = new Set(tagIds);
                      if (on) n.delete(t.id);
                      else n.add(t.id);
                      setTagIds(n);
                    }}
                    className={`rounded-sm border px-3 py-2 text-xs font-semibold ${
                      on ? "border-terracotta bg-terracotta/10 text-charcoal" : "border-charcoal/15 text-charcoal/75"
                    }`}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          <button
            type="button"
            disabled={submitM.isPending || !companyLegalName || !contactEmail || tagIds.size === 0}
            onClick={() => submitM.mutate()}
            className="w-full bg-terracotta text-cream py-3 text-sm font-semibold rounded-sm hover:bg-charcoal transition-colors disabled:opacity-50"
          >
            {submitM.isPending ? "Submitting…" : "Submit application"}
          </button>
        </PaperCard>
    </main>
  );
}
