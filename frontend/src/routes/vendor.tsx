import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, Eye, Megaphone, MousePointer2, Repeat, Trophy, Users } from "lucide-react";
import { toast } from "sonner";
import heroVendor from "@/assets/hero-vendor.jpg";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import { PaperCard, Stamp, Eyebrow, SectionLabel } from "@/components/Primitives";
import { Toaster } from "@/components/ui/sonner";

export const Route = createFileRoute("/vendor")({
  head: () => ({
    meta: [
      { title: "Vendor Portal — Wiseguys for Brands" },
      { name: "description", content: "Win the customers about to switch. Behavioral insights, switching campaigns and product positioning for premium brands." },
      { property: "og:title", content: "Vendor Portal — Wiseguys for Brands" },
      { property: "og:description", content: "Customers you're about to win." },
    ],
  }),
  component: VendorDashboard,
});

function VendorDashboard() {
  return (
    <div className="min-h-screen flex flex-col">
      <SiteHeader />
      <Toaster position="top-right" />
      <main className="flex-1">
        <Header />
        <Overview />
        <Insights />
        <Campaigns />
        <Funnel />
      </main>
      <SiteFooter />
    </div>
  );
}

function Header() {
  return (
    <section className="border-b border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-10 md:py-14 grid md:grid-cols-12 gap-8 items-end">
        <div className="md:col-span-8">
          <Eyebrow>Brand Desk · Roastery No. 7</Eyebrow>
          <h1 className="display-serif text-4xl sm:text-6xl text-charcoal mt-3 leading-[0.98]">
            Customers you're <span className="italic text-terracotta">about to win</span>.
          </h1>
          <p className="mt-4 text-charcoal/70 max-w-xl">
            127 shoppers are one nudge away from switching to your single-origin. Here's the briefing.
          </p>
        </div>
        <div className="md:col-span-4">
          <PaperCard className="p-2">
            <img src={heroVendor} alt="Abstract growth illustration" width={1024} height={896} loading="lazy" className="w-full h-auto block" />
          </PaperCard>
        </div>
      </div>
    </section>
  );
}

function Overview() {
  const stats = [
    { num: "127", label: "Potential conversions this week", trend: "+18%", icon: Users },
    { num: "412", label: "Active switch opportunities", trend: "+9%", icon: Repeat },
    { num: "$8.4k", label: "Revenue influenced (30d)", trend: "+34%", icon: Trophy },
  ];
  return (
    <section className="bg-cream-deep border-b border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <SectionLabel number="§ A" label="Brand Overview" />
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {stats.map((s) => (
            <PaperCard key={s.label} className="p-7">
              <div className="flex items-start justify-between">
                <s.icon className="h-6 w-6 text-charcoal/55" strokeWidth={1.5} />
                <Stamp color="forest" className="!text-[0.6rem]">{s.trend}</Stamp>
              </div>
              <div className="num-display text-charcoal text-6xl mt-5">{s.num}</div>
              <div className="ink-divider my-4" />
              <div className="display-serif text-charcoal text-lg">{s.label}</div>
            </PaperCard>
          ))}
        </div>
      </div>
    </section>
  );
}

function Insights() {
  const segments = [
    {
      title: "People buying generic cold brew",
      size: "1,840",
      detail: "Mostly weekday lattes. High price-sensitivity. Open to local alternatives if quality is signaled.",
      tags: [{ label: "Coffee", c: "terracotta" as const }, { label: "Price-sensitive", c: "charcoal" as const }],
    },
    {
      title: "Sustainable shoppers in 5-mile radius",
      size: "742",
      detail: "Already toggle 'Local' and 'Sustainable.' Highest LTV bracket. Almost rude not to target.",
      tags: [{ label: "High LTV", c: "forest" as const }, { label: "Local", c: "azure" as const }],
    },
    {
      title: "Lapsed competitor customers",
      size: "318",
      detail: "Bought from BigChain Roasters in Q3, now drifting. A small discount tips them.",
      tags: [{ label: "Re-engage", c: "navy" as const }],
    },
  ];
  return (
    <section>
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-14">
        <SectionLabel number="§ B" label="Customer Insights" />
        <h2 className="display-serif text-3xl sm:text-4xl text-charcoal mt-3">
          Aggregated. Anonymized. <span className="italic text-terracotta">Actionable.</span>
        </h2>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {segments.map((s) => (
            <PaperCard key={s.title} className="p-6">
              <div className="flex flex-wrap gap-1.5">
                {s.tags.map((t) => (<Stamp key={t.label} color={t.c} className="!text-[0.6rem]">{t.label}</Stamp>))}
              </div>
              <h3 className="display-serif text-2xl text-charcoal mt-4 leading-tight">{s.title}</h3>
              <div className="num-display text-terracotta text-4xl mt-3">{s.size}</div>
              <div className="text-xs uppercase tracking-widest text-charcoal/50">shoppers</div>
              <p className="mt-4 text-sm text-charcoal/75 leading-relaxed">{s.detail}</p>
            </PaperCard>
          ))}
        </div>
      </div>
    </section>
  );
}

function Campaigns() {
  const [campaign, setCampaign] = useState({
    type: "discount" as "discount" | "rewards",
    discount: 15,
    category: "Coffee",
    audience: "Sustainable & Local shoppers",
  });
  const reach = Math.round(742 + campaign.discount * 12);
  const conversions = Math.round(reach * 0.18);

  const launch = () => {
    toast("Campaign drafted", { description: `Targeting ~${reach} shoppers. Estimated ${conversions} switches.` });
  };

  return (
    <section className="bg-charcoal text-cream relative overflow-hidden">
      <div className="absolute inset-0 grain-strong opacity-50" />
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8 py-14">
        <Eyebrow className="!text-terracotta">§ C — Campaign Builder</Eyebrow>
        <h2 className="display-serif text-3xl sm:text-4xl mt-3">Build a switching incentive in three movements.</h2>

        <div className="mt-8 grid lg:grid-cols-3 gap-5">
          <div className="border border-cream/20 rounded-sm p-6">
            <Eyebrow className="!text-cream/60">01 · Incentive</Eyebrow>
            <div className="grid grid-cols-2 gap-2 mt-4">
              {(["discount", "rewards"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setCampaign({ ...campaign, type: t })}
                  className={`p-3 text-sm font-semibold rounded-sm border transition-colors ${
                    campaign.type === t ? "bg-terracotta border-terracotta text-cream" : "border-cream/25 text-cream/75 hover:border-cream"
                  }`}
                >
                  {t === "discount" ? "Discount" : "Bonus Points"}
                </button>
              ))}
            </div>
            <div className="mt-5">
              <div className="flex justify-between text-sm">
                <span className="text-cream/70">Amount</span>
                <span className="num-display text-cream">{campaign.discount}%</span>
              </div>
              <input
                type="range" min={5} max={40} value={campaign.discount}
                onChange={(e) => setCampaign({ ...campaign, discount: Number(e.target.value) })}
                className="w-full mt-2 accent-terracotta"
              />
            </div>
          </div>

          <div className="border border-cream/20 rounded-sm p-6">
            <Eyebrow className="!text-cream/60">02 · Target Audience</Eyebrow>
            <div className="mt-4 space-y-2">
              {["Sustainable & Local shoppers", "Lapsed competitor buyers", "Price-sensitive cold brew drinkers"].map((a) => (
                <button
                  key={a}
                  onClick={() => setCampaign({ ...campaign, audience: a })}
                  className={`w-full text-left p-3 text-sm rounded-sm border transition-colors ${
                    campaign.audience === a ? "bg-terracotta/15 border-terracotta text-cream" : "border-cream/20 text-cream/75 hover:border-cream/50"
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>

          <div className="border border-cream/20 rounded-sm p-6 flex flex-col">
            <Eyebrow className="!text-cream/60">03 · Estimated Impact</Eyebrow>
            <div className="mt-4 grid grid-cols-2 gap-3 flex-1">
              <div>
                <div className="text-xs uppercase tracking-widest text-cream/55">Reach</div>
                <div className="num-display text-3xl text-cream mt-1">{reach.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-widest text-cream/55">Switches</div>
                <div className="num-display text-3xl text-terracotta mt-1">{conversions.toLocaleString()}</div>
              </div>
            </div>
            <button onClick={launch} className="mt-4 bg-terracotta text-cream px-4 py-3 text-sm font-semibold rounded-sm hover:bg-cream hover:text-charcoal transition-colors inline-flex items-center justify-center gap-2">
              <Megaphone className="h-4 w-4" /> Launch campaign
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Funnel() {
  const stages = [
    { label: "Seen", value: 12480, icon: Eye, pct: 100 },
    { label: "Considered", value: 4120, icon: MousePointer2, pct: 33 },
    { label: "Switched", value: 1280, icon: Repeat, pct: 10 },
    { label: "Loyal", value: 612, icon: Trophy, pct: 5 },
  ];
  const positioning = [
    { label: "Price competitiveness", value: 72, c: "bg-terracotta" },
    { label: "Value alignment", value: 88, c: "bg-forest" },
    { label: "Sustainability perception", value: 81, c: "bg-azure" },
    { label: "Quality signal", value: 94, c: "bg-navy" },
  ];

  return (
    <section className="bg-cream-deep border-t border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-14 grid lg:grid-cols-2 gap-8">
        <div>
          <SectionLabel number="§ E" label="Performance Funnel" />
          <h2 className="display-serif text-3xl text-charcoal mt-3">Seen → Switched → Loyal.</h2>
          <PaperCard className="mt-6 p-6">
            <div className="space-y-4">
              {stages.map((s) => (
                <div key={s.label}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-charcoal font-semibold">
                      <s.icon className="h-4 w-4" strokeWidth={1.6} /> {s.label}
                    </span>
                    <span className="num-display text-charcoal">{s.value.toLocaleString()}</span>
                  </div>
                  <div className="mt-2 h-3 bg-charcoal/10 rounded-sm overflow-hidden">
                    <div className="h-full bg-terracotta relative grain" style={{ width: `${s.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="ink-divider my-5" />
            <div className="flex items-center justify-between">
              <Eyebrow>ROI on campaigns</Eyebrow>
              <span className="num-display text-forest text-2xl">4.8×</span>
            </div>
          </PaperCard>
        </div>

        <div>
          <SectionLabel number="§ D" label="Product Positioning" />
          <h2 className="display-serif text-3xl text-charcoal mt-3">How your product reads on shelf.</h2>
          <PaperCard className="mt-6 p-6">
            <div className="space-y-5">
              {positioning.map((p) => (
                <div key={p.label}>
                  <div className="flex justify-between text-sm">
                    <span className="text-charcoal font-semibold">{p.label}</span>
                    <span className="num-display text-charcoal">{p.value}</span>
                  </div>
                  <div className="mt-2 h-2.5 bg-charcoal/10 rounded-sm overflow-hidden">
                    <div className={`h-full ${p.c}`} style={{ width: `${p.value}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="ink-divider my-5" />
            <div className="flex items-center justify-between text-sm">
              <span className="text-charcoal/70">Composite ranking</span>
              <span className="display-serif text-charcoal text-2xl">Top 4% <ArrowRight className="inline h-4 w-4 text-terracotta" /></span>
            </div>
          </PaperCard>
        </div>
      </div>
    </section>
  );
}
