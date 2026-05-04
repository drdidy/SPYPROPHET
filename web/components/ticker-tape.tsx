"use client";

import { useReducedMotion } from "framer-motion";

const TICKERS = [
  { symbol: "SPY", price: "623.41", change: "+1.04%", up: true },
  { symbol: "VIX", price: "14.82", change: "-3.12%", up: false },
  { symbol: "QQQ", price: "568.20", change: "+0.83%", up: true },
  { symbol: "IWM", price: "245.10", change: "+1.62%", up: true },
  { symbol: "/ES", price: "6,310.50", change: "+0.78%", up: true },
  { symbol: "/NQ", price: "23,442.25", change: "+0.62%", up: true },
  { symbol: "TLT", price: "92.40", change: "-0.25%", up: false },
  { symbol: "DXY", price: "104.18", change: "-0.10%", up: false },
  { symbol: "GLD", price: "264.85", change: "+0.55%", up: true },
  { symbol: "BTC", price: "67,420", change: "+2.41%", up: true },
];

export function TickerTape() {
  const reduce = useReducedMotion();
  // Triple the array so the loop always shows a continuous strip.
  const items = [...TICKERS, ...TICKERS, ...TICKERS];

  return (
    <div
      className="relative overflow-hidden border-y border-border/60 bg-surface/40 backdrop-blur"
      role="marquee"
      aria-label="Market ticker"
    >
      {/* fade edges */}
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-bg via-bg/70 to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-bg via-bg/70 to-transparent" />

      <div
        className="flex whitespace-nowrap py-3"
        style={{
          animation: reduce ? "none" : "ticker-scroll 60s linear infinite",
        }}
      >
        {items.map((t, i) => (
          <span
            key={i}
            className="mx-6 inline-flex items-center gap-2 text-sm tabular"
          >
            <span className="font-bold text-text">{t.symbol}</span>
            <span className="font-mono text-text">{t.price}</span>
            <span
              className={
                "font-mono text-xs font-bold " +
                (t.up ? "text-green-bright" : "text-red-bright")
              }
            >
              {t.up ? "▲" : "▼"} {t.change}
            </span>
          </span>
        ))}
      </div>

      <style>{`
        @keyframes ticker-scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-33.333%); }
        }
      `}</style>
    </div>
  );
}
