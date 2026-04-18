import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import heroVendor from "@/assets/hero-vendor.jpg";
import { PaperCard, Stamp, Eyebrow, SectionLabel } from "@/components/Primitives";
import { apiFetch } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { VendorApplicationPublic, VendorProfilePublic } from "@/lib/types";

export const Route = createFileRoute("/vendor/")({
  head: () => ({
    meta: [{ title: "Vendor Portal — WiseBuys" }],
  }),
  component: VendorHome,
});

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
                ? "Manage your catalog and allowed value tags below. Campaign analytics ship next."
                : "Submit once, admins verify claims, then your catalog unlocks."}
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
          <SectionLabel number="§ A" label="Status" />
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
              <div className="num-display text-charcoal text-4xl">{hasProfile ? profileQ.data!.allowed_tags.length : "—"}</div>
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
              <div className="text-sm text-charcoal/65">{hasProfile ? "Add products shoppers can see." : "Unlocks after approval."}</div>
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
        <section className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
          <SectionLabel number="§ B" label="Allowed tags" />
          <div className="mt-4 flex flex-wrap gap-2">
            {profileQ.data!.allowed_tags.map((t) => (
              <Stamp key={t.id} color="azure" className="!text-[0.65rem]">
                {t.label}
              </Stamp>
            ))}
          </div>
        </section>
      )}

      <section className="bg-cream-deep border-t border-charcoal/15">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 py-14">
          <SectionLabel number="§ C" label="Roadmap" />
          <h2 className="display-serif text-3xl text-charcoal mt-3">Campaigns & funnel</h2>
          <PaperCard className="mt-6 p-8 max-w-2xl">
            <Eyebrow>Coming soon</Eyebrow>
            <p className="mt-2 text-sm text-charcoal/75 leading-relaxed">
              Aggregated acquisition funnels and incentive campaigns will plug into the same paper-card layout — for now,
              use the live catalog and Swagger for admin approvals.
            </p>
          </PaperCard>
        </div>
      </section>
    </main>
  );
}
