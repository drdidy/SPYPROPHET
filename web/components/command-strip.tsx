"use client";

import { Card } from "@/components/ui/card";
import { ArrowDown, ArrowUp } from "lucide-react";

interface CommandStripProps {
  spyPrice?: number | null;
  spyChangePct?: number | null;
  vix?: number | null;
  decisionLabel?: string | null;
}

const fmtPrice = (v?: number | null) => {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const fmtPct = (v?: number | null) => {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "" : "";
  return `${sign}${v.toFixed(2)}%`;
};

export function CommandStrip({ spyPrice, spyChangePct, vix, decisionLabel }: CommandStripProps) {
  const change = spyChangePct ?? 0;
  const isUp = change > 0;
  const isDown = change < 0;
  const Trend = isUp ? ArrowUp : isDown ? ArrowDown : null;

  // VIX regime tone
  const vixTone =
    vix == null ? "text-muted" : vix >= 25 ? "text-red-bright" : vix >= 20 ? "text-amber" : "text-green-bright";

  return (
    <Card premium className="overflow-hidden">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border/60">
        {/* SPY price */}
        <div className="bg-surface/80 p-5">
          <div className="text-[0.62rem] uppercase tracking-[0.16em] text-muted font-bold">SPY · Last</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-[family-name:var(--font-display)] text-3xl font-extrabold tabular text-text">
              ${fmtPrice(spyPrice)}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-[0.78rem] font-bold tabular">
            {Trend && <Trend className={isUp ? "h-3.5 w-3.5 text-green-bright" : "h-3.5 w-3.5 text-red-bright"} strokeWidth={3} />}
            <span className={isUp ? "text-green-bright" : isDown ? "text-red-bright" : "text-muted"}>
              {fmtPct(spyChangePct)}
            </span>
            <span className="text-muted font-medium">today</span>
          </div>
        </div>

        {/* VIX */}
        <div className="bg-surface/80 p-5">
          <div className="text-[0.62rem] uppercase tracking-[0.16em] text-muted font-bold">VIX</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={`font-[family-name:var(--font-display)] text-3xl font-extrabold tabular ${vixTone}`}>
              {fmtPrice(vix)}
            </span>
          </div>
          <div className="mt-1 text-[0.78rem] text-muted font-medium">
            {vix == null ? "Pending" : vix >= 25 ? "Stress" : vix >= 20 ? "Elevated" : "Calm"} regime
          </div>
        </div>

        {/* Decision */}
        <div className="bg-surface/80 p-5 col-span-2 md:col-span-1">
          <div className="text-[0.62rem] uppercase tracking-[0.16em] text-muted font-bold">Decision</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-lg font-bold leading-tight text-text font-[family-name:var(--font-display)]">
              {decisionLabel || "Awaiting structure"}
            </span>
          </div>
          <div className="mt-1 text-[0.78rem] text-muted font-medium">Live read · update on each close</div>
        </div>

        {/* Live ribbon */}
        <div className="bg-surface/80 p-5 col-span-2 md:col-span-1 flex flex-col justify-center">
          <div className="flex items-center gap-2">
            <span className="live-pulse-dot" aria-hidden />
            <span className="text-[0.78rem] font-bold uppercase tracking-[0.12em] text-green-bright">Live data</span>
          </div>
          <div className="mt-1.5 text-[0.74rem] text-muted leading-snug">
            yfinance hourly candles · Tastytrade live options chain
          </div>
        </div>
      </div>
    </Card>
  );
}
