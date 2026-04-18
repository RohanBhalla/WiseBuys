import { Link, useLocation } from "@tanstack/react-router";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import logo from "@/assets/wiseguys-logo.png";

const links = [
  { to: "/", label: "Home" },
  { to: "/dashboard", label: "Customer" },
  { to: "/vendor", label: "Vendor" },
] as const;

export function SiteHeader() {
  const location = useLocation();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-charcoal/15 bg-cream/85 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8">
        <Link to="/" className="flex items-center gap-2.5 group" onClick={() => setOpen(false)}>
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-cream-deep overflow-hidden ring-1 ring-charcoal/15">
            <img src={logo} alt="Wiseguys owl logo" className="h-full w-full object-cover" />
          </span>
          <span className="display-serif text-2xl text-charcoal tracking-tight">Wiseguys</span>
          <span className="hidden sm:inline-block text-[0.6rem] font-semibold tracking-[0.18em] uppercase text-terracotta border border-terracotta/50 rounded-sm px-1.5 py-0.5 ml-1">
            Est. 2025
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {links.map((l) => {
            const active = location.pathname === l.to;
            return (
              <Link
                key={l.to}
                to={l.to}
                className={`text-sm font-medium tracking-wide transition-colors ${
                  active ? "text-terracotta" : "text-charcoal/75 hover:text-charcoal"
                }`}
              >
                {l.label}
                {active && <span className="block h-[2px] w-full bg-terracotta mt-1" />}
              </Link>
            );
          })}
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 bg-charcoal text-cream px-4 py-2 text-sm font-semibold rounded-sm hover:bg-terracotta transition-colors"
          >
            Audit my cart
          </Link>
        </nav>

        <button
          className="md:hidden text-charcoal"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-charcoal/15 bg-cream px-5 py-4 space-y-3">
          {links.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              onClick={() => setOpen(false)}
              className="block text-base font-medium text-charcoal/85"
            >
              {l.label}
            </Link>
          ))}
          <Link
            to="/dashboard"
            onClick={() => setOpen(false)}
            className="inline-flex items-center bg-charcoal text-cream px-4 py-2 text-sm font-semibold rounded-sm"
          >
            Audit my cart
          </Link>
        </div>
      )}
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-charcoal/15 bg-cream-deep mt-20">
      <div className="mx-auto max-w-7xl px-5 py-12 sm:px-8 grid gap-8 md:grid-cols-4">
        <div className="md:col-span-2">
          <div className="display-serif text-2xl text-charcoal">Wiseguys</div>
          <p className="mt-3 text-sm text-charcoal/70 max-w-sm leading-relaxed">
            Smarter shopping, powered by your receipts. We read between the lines so your wallet doesn't have to.
          </p>
        </div>
        <div>
          <div className="eyebrow mb-3">Platform</div>
          <ul className="space-y-2 text-sm text-charcoal/75">
            <li><Link to="/dashboard">For Shoppers</Link></li>
            <li><Link to="/vendor">For Brands</Link></li>
            <li><Link to="/">How it works</Link></li>
          </ul>
        </div>
        <div>
          <div className="eyebrow mb-3">Company</div>
          <ul className="space-y-2 text-sm text-charcoal/75">
            <li>About</li>
            <li>Careers</li>
            <li>Press kit</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-charcoal/15">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 py-5 flex flex-col sm:flex-row gap-2 justify-between text-xs text-charcoal/55">
          <span>© 2025 Wiseguys Co. — Printed on the internet.</span>
          <span className="tracking-[0.2em] uppercase">A periodical for the discerning shopper</span>
        </div>
      </div>
    </footer>
  );
}
