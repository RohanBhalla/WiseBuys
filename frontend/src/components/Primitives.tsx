import { type ReactNode } from "react";

type StampColor = "terracotta" | "azure" | "forest" | "navy" | "charcoal";

const colorMap: Record<StampColor, string> = {
  terracotta: "text-terracotta",
  azure: "text-azure",
  forest: "text-forest",
  navy: "text-navy",
  charcoal: "text-charcoal",
};

export function Stamp({
  children,
  color = "terracotta",
  className = "",
}: {
  children: ReactNode;
  color?: StampColor;
  className?: string;
}) {
  return <span className={`stamp ${colorMap[color]} ${className}`}>{children}</span>;
}

export function PaperCard({
  children,
  className = "",
  grain = true,
}: {
  children: ReactNode;
  className?: string;
  grain?: boolean;
}) {
  return (
    <div className={`paper-card rounded-sm overflow-hidden ${grain ? "grain" : ""} ${className}`}>
      <div className="relative">{children}</div>
    </div>
  );
}

export function Eyebrow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`eyebrow ${className}`}>{children}</div>;
}

export function SectionLabel({ number, label }: { number: string; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="num-display text-terracotta text-2xl">{number}</span>
      <span className="ink-divider-dashed flex-1" />
      <span className="eyebrow">{label}</span>
    </div>
  );
}
