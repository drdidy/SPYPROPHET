"use client";

import * as React from "react";

export type TickerItem = {
  symbol: string;
  price: number | null;
  changePct: number | null;
};

function fmtPrice(v: number | null): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v >= 1000) return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (v >= 100) return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(v: number | null): string {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

export function TickerMarquee({ items }: { items: TickerItem[] }) {
  // Triple the array so the loop always shows a continuous strip.
  const tripled = React.useMemo(() => [...items, ...items, ...items], [items]);

  return (
    <div
      className="relative overflow-hidden border-y border-border/60 bg-surface/40 backdrop-blur"
      role="marquee"
      aria-label="Live market ticker"
    >
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-bg via-bg/70 to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-bg via-bg/70 to-transparent" />

      <div className="ticker-track flex whitespace-nowrap py-3">
        {tripled.map((t, i) => {
          const up = (t.changePct ?? 0) > 0;
          const down = (t.changePct ?? 0) < 0;
          return (
            <span key={i} className="mx-6 inline-flex items-center gap-2 text-sm tabular">
              <span className="font-bold text-text">{t.symbol}</span>
              <span className="font-mono text-text">{fmtPrice(t.price)}</span>
              <span
                className={
                  "font-mono text-xs font-bold " +
                  (up ? "text-green-bright" : down ? "text-red-bright" : "text-muted")
                }
              >
                {up ? "▲" : down ? "▼" : "·"} {fmtPct(t.changePct)}
              </span>
            </span>
          );
        })}
      </div>

      <style>{`
        .ticker-track { animation: ticker-scroll 60s linear infinite; }
        @keyframes ticker-scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-33.333%); }
        }
        @media (prefers-reduced-motion: reduce) {
          .ticker-track { animation: none; }
        }
      `}</style>
    </div>
  );
}
