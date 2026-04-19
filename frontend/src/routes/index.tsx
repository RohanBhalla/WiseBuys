import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Coffee, Leaf, MapPin, ShoppingBag, Sparkles, TrendingDown } from "lucide-react";
import heroLanding from "@/assets/hero-landing.jpg";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import { PaperCard, Stamp, Eyebrow, SectionLabel } from "@/components/Primitives";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Wiseguys — Shop smarter. Switch better. Earn while you're at it." },
      { name: "description", content: "Connect your purchases. We'll tell you what's better. A witty, premium platform for smarter shopping powered by transaction insights." },
      { property: "og:title", content: "Wiseguys — Shop smarter. Switch better." },
      { property: "og:description", content: "We read your receipts so your wallet doesn't have to." },
    ],
  }),
  component: LandingPage,
});

function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <HowItWorks />
        <InsightCards />
        <Values />
        <SocialProof />
        <CTA />
      </main>
      <SiteFooter />
    </div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 pt-12 pb-16 md:pt-20 md:pb-24 grid md:grid-cols-12 gap-10 items-center">
        <div className="md:col-span-7 animate-paper-in">
          <Eyebrow className="mb-5">Vol. 01 — A Periodical for Smarter Spending</Eyebrow>
          <h1 className="display-serif text-charcoal text-[2.6rem] leading-[1.02] sm:text-6xl md:text-7xl">
            Shop smarter.
            <br />
            <span className="text-terracotta italic">Switch</span> better.
            <br />
            Earn while<br className="hidden sm:block" /> you're at it.
          </h1>
          <p className="mt-6 max-w-md text-base sm:text-lg text-charcoal/75 leading-relaxed">
            Connect your purchases. We'll tell you what's better.<br />
            <span className="italic">(Yes, even the artisanal pickles.)</span>
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              to="/login"
              className="inline-flex items-center gap-2 bg-terracotta text-cream px-6 py-3.5 text-sm font-semibold tracking-wide rounded-sm hover:bg-charcoal transition-colors"
            >
              Sign in & get audited <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/vendor"
              className="text-sm font-semibold text-charcoal underline decoration-terracotta decoration-2 underline-offset-4 hover:text-terracotta transition-colors"
            >
              I'm a brand →
            </Link>
          </div>
          <div className="mt-10 flex flex-wrap gap-3">
            <Stamp color="terracotta">No spam, ever</Stamp>
            <Stamp color="azure">Bank-grade privacy</Stamp>
            <Stamp color="forest">Free forever</Stamp>
          </div>
        </div>
        <div className="md:col-span-5 relative">
          <div className="relative paper-card rounded-sm grain-strong p-3">
            <img
              src={heroLanding}
              alt="A shopping cart bursting with abstract geometric goods, surrounded by receipts and stars — a Wiseguys cart audit in progress."
              width={1024}
              height={1024}
              className="w-full h-auto block"
            />
          </div>
          <div className="hidden md:block absolute -bottom-6 -left-8 paper-card grain rounded-sm p-4 max-w-[14rem] rotate-[-3deg] bg-paper">
            <Eyebrow>Receipt #4421</Eyebrow>
            <div className="display-serif text-charcoal text-2xl mt-1">$847</div>
            <div className="text-xs text-charcoal mt-1">saved last quarter</div>
          </div>
          {/* No paper-card — its CSS forces a light paper bg and was overriding bg-azure, so cream-on-cream failed contrast */}
          <div className="hidden md:block absolute -top-4 -right-6 rounded-sm p-3 rotate-[4deg] bg-forest text-cream border border-charcoal/25 shadow-md">
            <div className="text-[0.6rem] tracking-[0.2em] uppercase font-semibold">Better swap found</div>
            <div className="display-serif text-xl mt-0.5">+38% value</div>
          </div>
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    { n: "01", title: "Connect", body: "Link your bank or upload receipts. Two clicks. No drama.", icon: ShoppingBag },
    { n: "02", title: "Analyze", body: "Our nosy algorithms read every line item. Politely.", icon: Sparkles },
    { n: "03", title: "Switch", body: "We surface better alternatives. You decide. Always.", icon: ArrowRight },
    { n: "04", title: "Earn", body: "Get rewarded for switches that benefit your values.", icon: TrendingDown },
  ];
  return (
    <section className="bg-cream-deep border-y border-charcoal/15 relative">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-16 md:py-24">
        <div className="max-w-2xl">
          <SectionLabel number="§ I" label="The Process" />
          <h2 className="display-serif text-4xl sm:text-5xl text-charcoal mt-4">
            Four steps. No PhD<br />in finance required.
          </h2>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s) => (
            <PaperCard key={s.n} className="p-6 hover-shuffle">
              <div className="flex items-start justify-between">
                <span className="num-display text-3xl text-terracotta">{s.n}</span>
                <s.icon className="h-6 w-6 text-charcoal/60" strokeWidth={1.6} />
              </div>
              <div className="mt-6 display-serif text-2xl text-charcoal">{s.title}</div>
              <p className="mt-2 text-sm text-charcoal/70 leading-relaxed">{s.body}</p>
            </PaperCard>
          ))}
        </div>
      </div>
    </section>
  );
}

function InsightCards() {
  const insights = [
    {
      tag: "Coffee Intervention",
      tagColor: "terracotta" as const,
      headline: "We need to talk about your coffee choices.",
      from: "Brand X Cold Brew",
      fromPrice: "$5.99",
      to: "Local Roastery No. 7",
      toPrice: "$4.20",
      saving: "Save $42/mo",
      tags: ["Local", "Independent"],
      icon: Coffee,
    },
    {
      tag: "Pantry Upgrade",
      tagColor: "azure" as const,
      headline: "Your pasta sauce has a secret older brother.",
      from: "Generic Marinara",
      fromPrice: "$3.29",
      to: "Nonna's Imported",
      toPrice: "$3.89",
      saving: "+22% quality",
      tags: ["Imported", "No Sugar"],
      icon: ShoppingBag,
    },
    {
      tag: "Greener Swap",
      tagColor: "forest" as const,
      headline: "Same soap. Half the planet's tears.",
      from: "Big Cleanco",
      fromPrice: "$8.99",
      to: "Refill Co.",
      toPrice: "$6.50",
      saving: "Save $30 + 12 bottles",
      tags: ["Sustainable", "Refillable"],
      icon: Leaf,
    },
  ];
  return (
    <section className="relative">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-16 md:py-24">
        <div className="max-w-2xl">
          <SectionLabel number="§ II" label="Sample Insights" />
          <h2 className="display-serif text-4xl sm:text-5xl text-charcoal mt-4">
            Receipts, but with <span className="italic text-terracotta">opinions</span>.
          </h2>
          <p className="mt-4 text-charcoal/70 max-w-md">
            A taste of what lands in your feed. Each card is one small swap away from a smugger you.
          </p>
        </div>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {insights.map((i) => (
            <PaperCard key={i.headline} className="p-6 hover-shuffle">
              <div className="flex items-center justify-between">
                <Stamp color={i.tagColor}>{i.tag}</Stamp>
                <i.icon className="h-5 w-5 text-charcoal/50" strokeWidth={1.6} />
              </div>
              <h3 className="display-serif text-2xl text-charcoal mt-5 leading-tight">{i.headline}</h3>
              <div className="ink-divider mt-5" />
              <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                <div>
                  <div className="text-[0.65rem] uppercase tracking-widest text-charcoal/50">Currently</div>
                  <div className="text-charcoal/80 mt-1 line-through decoration-terracotta">{i.from}</div>
                  <div className="num-display text-charcoal/60 text-base">{i.fromPrice}</div>
                </div>
                <div>
                  <div className="text-[0.65rem] uppercase tracking-widest text-terracotta">Better</div>
                  <div className="text-charcoal font-semibold mt-1">{i.to}</div>
                  <div className="num-display text-charcoal text-base">{i.toPrice}</div>
                </div>
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                {i.tags.map((t) => (
                  <Stamp key={t} color="charcoal" className="!text-[0.6rem] !py-1">{t}</Stamp>
                ))}
              </div>
              <div className="mt-5 flex items-center justify-between">
                <span className="text-sm font-semibold text-forest">{i.saving}</span>
                <span className="text-charcoal/40">→</span>
              </div>
            </PaperCard>
          ))}
        </div>
      </div>
    </section>
  );
}

function Values() {
  const values = [
    { label: "Sustainable", icon: Leaf, color: "text-forest" },
    { label: "Locally Sourced", icon: MapPin, color: "text-terracotta" },
    { label: "Independent", icon: ShoppingBag, color: "text-azure" },
    { label: "Women-Owned", icon: Sparkles, color: "text-navy" },
  ];
  return (
    <section className="bg-charcoal text-cream relative overflow-hidden">
      <div className="absolute inset-0 grain-strong opacity-50" />
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8 py-16 md:py-24 grid md:grid-cols-12 gap-10">
        <div className="md:col-span-5">
          <Eyebrow className="!text-terracotta">§ III — Values, not vibes</Eyebrow>
          <h2 className="display-serif text-4xl sm:text-5xl mt-4">
            Spend like<br />you mean it.
          </h2>
          <p className="mt-5 text-cream/75 max-w-md leading-relaxed">
            Choose what matters to you. We'll quietly factor it into every recommendation. No lectures. No guilt-trips.
          </p>
        </div>
        <div className="md:col-span-7 grid grid-cols-2 gap-4">
          {values.map((v) => (
            <div key={v.label} className="border border-cream/20 p-6 rounded-sm hover:bg-cream/5 transition-colors">
              <v.icon className={`h-7 w-7 ${v.color}`} strokeWidth={1.6} />
              <div className="display-serif text-xl mt-4">{v.label}</div>
              <div className="text-xs text-cream/55 mt-1 tracking-wider uppercase">Toggle in your portal</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function SocialProof() {
  const brands = ["RUSTIC & CO", "OAK + AMBER", "MERIDIAN", "GOOD COMPANY", "FIELDNOTE", "PARLOUR"];
  return (
    <section className="bg-cream-deep border-y border-charcoal/15">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 py-12">
        <div className="text-center eyebrow mb-6">As featured in the carts of</div>
        <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
          {brands.map((b) => (
            <span key={b} className="display-serif text-charcoal/65 text-lg sm:text-xl tracking-wider">{b}</span>
          ))}
        </div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="relative">
      <div className="mx-auto max-w-5xl px-5 sm:px-8 py-20 md:py-28 text-center">
        <Eyebrow>Final notice</Eyebrow>
        <h2 className="display-serif text-charcoal text-5xl sm:text-7xl mt-5 leading-[0.95]">
          Your receipts<br />
          deserve <span className="italic text-terracotta">better</span>.
        </h2>
        <p className="mt-6 text-charcoal/75 max-w-lg mx-auto">
          Three minutes to connect. A lifetime of slightly smug satisfaction.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-4">
          <Link to="/login" className="inline-flex items-center gap-2 bg-terracotta text-cream px-7 py-4 text-sm font-semibold tracking-wide rounded-sm hover:bg-charcoal transition-colors">
            Sign in & get audited <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}
