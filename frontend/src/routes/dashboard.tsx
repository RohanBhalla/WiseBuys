import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, ChevronDown, Coffee, Leaf, MapPin, ShoppingBag, Sparkles, Trophy, Users } from "lucide-react";
import { toast } from "sonner";
import heroCustomer from "@/assets/hero-customer.jpg";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import { PaperCard, Stamp, Eyebrow, SectionLabel } from "@/components/Primitives";
import { Toaster } from "@/components/ui/sonner";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Customer Portal — Wiseguys" },
      { name: "description", content: "Your cart audit, recommendations, rewards and shopping values — all in one paper-bound dashboard." },
      { property: "og:title", content: "Customer Portal — Wiseguys" },
      { property: "og:description", content: "We need to talk about your coffee choices." },
    ],
  }),
  component: CustomerDashboard,
});

function CustomerDashboard() {
  return (
    <div className="min-h-screen flex flex-col">
      <SiteHeader />
      <Toaster position="top-right" />
      <main className="flex-1">
        <Greeting />
        <Stats />
        <Recommendations />
        <RewardsAndValues />
      </main>
      <SiteFooter />
    </div>
  );
}

function Greeting() {
  return (
    <section className="border-b border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-10 md:py-14 grid md:grid-cols-12 gap-8 items-end">
        <div className="md:col-span-8">
          <Eyebrow>Tuesday Edition · Audit No. 0042</Eyebrow>
          <h1 className="display-serif text-4xl sm:text-6xl text-charcoal mt-3 leading-[0.98]">
            Good morning, <span className="italic text-terracotta">Margot</span>.
          </h1>
          <p className="mt-4 text-charcoal/70 max-w-xl">
            We've been through your receipts. There's good news, mild news, and one situation involving oat milk we'd like to discuss.
          </p>
        </div>
        <div className="md:col-span-4">
          <PaperCard className="p-2">
            <img src={heroCustomer} alt="Abstract analysis illustration" width={1024} height={896} loading="lazy" className="w-full h-auto block" />
          </PaperCard>
        </div>
      </div>
    </section>
  );
}

function Stats() {
  const stats = [
    { num: "62%", label: "of purchases can be improved", caption: "Don't take it personally." },
    { num: "$847", label: "potential annual savings", caption: "Or 169 better lattes." },
    { num: "1,240", label: "Wiseguy points earned", caption: "Redeemable for smugness." },
  ];
  return (
    <section className="bg-cream-deep border-b border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <SectionLabel number="§ A" label="Cart Audit Summary" />
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {stats.map((s) => (
            <PaperCard key={s.label} className="p-7">
              <div className="num-display text-charcoal text-6xl">{s.num}</div>
              <div className="ink-divider my-4" />
              <div className="display-serif text-charcoal text-lg">{s.label}</div>
              <div className="text-sm text-charcoal/60 italic mt-1">{s.caption}</div>
            </PaperCard>
          ))}
        </div>
        <div className="mt-6 grid gap-5 md:grid-cols-2">
          <PaperCard className="p-6 bg-charcoal text-cream">
            <Stamp color="terracotta" className="!text-cream !border-cream">Talking-To #1</Stamp>
            <h3 className="display-serif text-2xl mt-4">We need to talk about your coffee choices.</h3>
            <p className="text-sm text-cream/75 mt-2">Seven oat milk lattes a week is a lifestyle, not a budget. We found three local roasters within a two-mile radius.</p>
          </PaperCard>
          <PaperCard className="p-6">
            <Stamp color="forest">Win of the Week</Stamp>
            <h3 className="display-serif text-2xl mt-4 text-charcoal">Your pasta game is impeccable.</h3>
            <p className="text-sm text-charcoal/70 mt-2">Imported, independent, mostly organic. We have nothing to add. Carry on.</p>
          </PaperCard>
        </div>
      </div>
    </section>
  );
}

type Rec = {
  id: string;
  category: string;
  current: string;
  currentPrice: string;
  better: string;
  betterPrice: string;
  reasoning: string;
  tags: { label: string; color: "terracotta" | "azure" | "forest" | "navy" | "charcoal" }[];
  icon: typeof Coffee;
};

const recs: Rec[] = [
  {
    id: "r1",
    category: "Coffee",
    current: "MegaBean Cold Brew 32oz",
    currentPrice: "$5.99",
    better: "Roastery No. 7 — Single Origin",
    betterPrice: "$4.20",
    reasoning: "Local roastery, 4-mile shipping radius. Same caffeine profile, 30% less acidic. Currently scoring 4.8/5 on independent reviews. Your previous purchases suggest you favor medium roasts — this is one.",
    tags: [{ label: "Local", color: "terracotta" }, { label: "Independent", color: "azure" }],
    icon: Coffee,
  },
  {
    id: "r2",
    category: "Household",
    current: "PlanetSlayer All-Purpose Cleaner",
    currentPrice: "$8.99",
    better: "Refill Co. Concentrate",
    betterPrice: "$6.50",
    reasoning: "Refillable aluminum bottle, plant-based formula. You've toggled 'Sustainable' as a high-priority value. This swap aligns with that. Also: it actually works.",
    tags: [{ label: "Sustainable", color: "forest" }, { label: "Refillable", color: "forest" }],
    icon: Leaf,
  },
  {
    id: "r3",
    category: "Pantry",
    current: "Generic Granola 18oz",
    currentPrice: "$4.49",
    better: "Fieldnote Heritage Oats",
    betterPrice: "$5.25",
    reasoning: "Slightly more expensive, but Black-owned, regenerative farming, and contains 40% less sugar. Your values toggle 'Ownership' weighs this favorably.",
    tags: [{ label: "Black-Owned", color: "navy" }, { label: "Regenerative", color: "forest" }],
    icon: ShoppingBag,
  },
];

function Recommendations() {
  const [open, setOpen] = useState<string | null>("r1");

  const handleSwitch = (rec: Rec) => {
    toast(`Switched to ${rec.better}`, {
      description: "+12 Wiseguy points earned. Smugness +1.",
    });
  };

  return (
    <section>
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-14">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <SectionLabel number="§ B" label="Recommendations Feed" />
            <h2 className="display-serif text-3xl sm:text-4xl text-charcoal mt-3">A few suggestions, gently offered.</h2>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Stamp color="charcoal">All</Stamp>
            <Stamp color="terracotta">Coffee</Stamp>
            <Stamp color="forest">Sustainable</Stamp>
            <Stamp color="azure">Local</Stamp>
          </div>
        </div>

        <div className="mt-8 space-y-4">
          {recs.map((r) => {
            const isOpen = open === r.id;
            return (
              <PaperCard key={r.id} className="p-0">
                <div className="grid md:grid-cols-12 gap-0">
                  <div className="md:col-span-1 bg-cream-deep flex md:flex-col items-center justify-center p-4 md:p-6 border-b md:border-b-0 md:border-r border-charcoal/15">
                    <r.icon className="h-7 w-7 text-charcoal/70" strokeWidth={1.6} />
                    <div className="text-[0.6rem] uppercase tracking-widest text-charcoal/55 ml-3 md:ml-0 md:mt-3">{r.category}</div>
                  </div>
                  <div className="md:col-span-5 p-6 border-b md:border-b-0 md:border-r border-charcoal/15">
                    <div className="text-[0.65rem] uppercase tracking-widest text-charcoal/50">Currently</div>
                    <div className="display-serif text-xl text-charcoal mt-1 line-through decoration-terracotta decoration-2">{r.current}</div>
                    <div className="num-display text-charcoal/60 text-2xl mt-2">{r.currentPrice}</div>
                  </div>
                  <div className="md:col-span-4 p-6 border-b md:border-b-0 md:border-r border-charcoal/15">
                    <div className="text-[0.65rem] uppercase tracking-widest text-terracotta">Better</div>
                    <div className="display-serif text-xl text-charcoal mt-1">{r.better}</div>
                    <div className="num-display text-charcoal text-2xl mt-2">{r.betterPrice}</div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {r.tags.map((t) => (<Stamp key={t.label} color={t.color} className="!text-[0.6rem]">{t.label}</Stamp>))}
                    </div>
                  </div>
                  <div className="md:col-span-2 p-6 flex flex-col justify-between gap-3">
                    <button
                      onClick={() => handleSwitch(r)}
                      className="bg-terracotta text-cream px-4 py-2.5 text-xs font-semibold tracking-wide rounded-sm hover:bg-charcoal transition-colors inline-flex items-center justify-center gap-1.5"
                    >
                      Switch & Earn <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setOpen(isOpen ? null : r.id)}
                      className="text-xs text-charcoal/70 hover:text-terracotta inline-flex items-center justify-center gap-1 font-medium"
                    >
                      Why this is better
                      <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                    </button>
                  </div>
                </div>
                {isOpen && (
                  <div className="border-t border-dashed border-charcoal/25 bg-cream-deep p-6 animate-paper-in">
                    <div className="grid md:grid-cols-12 gap-6">
                      <div className="md:col-span-3">
                        <Eyebrow>AI Reasoning</Eyebrow>
                        <div className="display-serif text-charcoal text-lg mt-1">The case for switching</div>
                      </div>
                      <p className="md:col-span-9 text-sm text-charcoal/80 leading-relaxed">{r.reasoning}</p>
                    </div>
                  </div>
                )}
              </PaperCard>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function RewardsAndValues() {
  const [values, setValues] = useState({
    sustainable: true,
    local: true,
    blackOwned: true,
    womenOwned: false,
    independent: true,
  });
  const [priceVsValues, setPriceVsValues] = useState(60);

  const milestones = [
    { name: "Roastery No. 7", points: 320, max: 500 },
    { name: "Refill Co.", points: 180, max: 250 },
    { name: "Fieldnote", points: 95, max: 200 },
  ];

  return (
    <section className="bg-cream-deep border-t border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-14 grid lg:grid-cols-2 gap-8">
        <div>
          <SectionLabel number="§ D" label="Loyalty & Rewards" />
          <h2 className="display-serif text-3xl text-charcoal mt-3">Brands you've earned standing with.</h2>
          <PaperCard className="mt-6 p-6">
            <div className="flex items-center justify-between">
              <div>
                <Eyebrow>Wiseguy Points</Eyebrow>
                <div className="num-display text-charcoal text-5xl mt-1">1,240</div>
              </div>
              <Trophy className="h-12 w-12 text-terracotta" strokeWidth={1.4} />
            </div>
            <div className="ink-divider my-5" />
            <div className="space-y-5">
              {milestones.map((m) => {
                const pct = (m.points / m.max) * 100;
                return (
                  <div key={m.name}>
                    <div className="flex justify-between text-sm">
                      <span className="font-semibold text-charcoal">{m.name}</span>
                      <span className="text-charcoal/60 num-display">{m.points}/{m.max}</span>
                    </div>
                    <div className="mt-2 h-2 bg-charcoal/10 rounded-sm overflow-hidden">
                      <div className="h-full bg-terracotta" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </PaperCard>
        </div>

        <div>
          <SectionLabel number="§ E" label="Preferences & Values" />
          <h2 className="display-serif text-3xl text-charcoal mt-3">Spend like you mean it.</h2>
          <PaperCard className="mt-6 p-6">
            <Eyebrow>Value Filters</Eyebrow>
            <div className="mt-4 space-y-3">
              {([
                ["sustainable", "Sustainable", Leaf],
                ["local", "Locally Sourced", MapPin],
                ["blackOwned", "Black-Owned", Users],
                ["womenOwned", "Women-Owned", Sparkles],
                ["independent", "Independent", ShoppingBag],
              ] as const).map(([key, label, Icon]) => (
                <button
                  key={key}
                  onClick={() => setValues({ ...values, [key]: !values[key] })}
                  className={`w-full flex items-center justify-between p-3 border rounded-sm transition-colors ${
                    values[key] ? "border-terracotta bg-terracotta/5" : "border-charcoal/15 hover:border-charcoal/30"
                  }`}
                >
                  <span className="flex items-center gap-3 text-sm font-medium text-charcoal">
                    <Icon className="h-4 w-4" strokeWidth={1.7} /> {label}
                  </span>
                  <span className={`h-5 w-9 rounded-full p-0.5 transition-colors ${values[key] ? "bg-terracotta" : "bg-charcoal/20"}`}>
                    <span className={`block h-4 w-4 bg-cream rounded-full transition-transform ${values[key] ? "translate-x-4" : ""}`} />
                  </span>
                </button>
              ))}
            </div>
            <div className="ink-divider my-6" />
            <Eyebrow>Price ↔ Values balance</Eyebrow>
            <input
              type="range"
              min={0}
              max={100}
              value={priceVsValues}
              onChange={(e) => setPriceVsValues(Number(e.target.value))}
              className="w-full mt-3 accent-terracotta"
            />
            <div className="flex justify-between text-xs text-charcoal/60 mt-1 font-semibold tracking-wide">
              <span>Cheapest</span>
              <span className="num-display text-charcoal">{priceVsValues}%</span>
              <span>Values-first</span>
            </div>
          </PaperCard>
        </div>
      </div>
    </section>
  );
}
