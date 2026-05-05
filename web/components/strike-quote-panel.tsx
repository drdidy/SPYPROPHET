"use client";

import type { ChainStrike, OptionQuote, QuotePairResponse } from "@/lib/api";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import * as React from "react";

interface StrikeQuotePanelProps {
  strikes: ChainStrike[];
  expiration: string;
  spotPrice: number | null;
  apiBaseUrl: string;
}

const REFRESH_MS = 15000;

export function StrikeQuotePanel({
  strikes,
  expiration,
  spotPrice,
  apiBaseUrl,
}: StrikeQuotePanelProps) {
  // Default to the strike closest to spot.
  const defaultIndex = React.useMemo(() => {
    if (!spotPrice || strikes.length === 0) return 0;
    let best = 0;
    let bestDist = Infinity;
    for (let i = 0; i < strikes.length; i += 1) {
      const d = Math.abs(strikes[i].strike - spotPrice);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    }
    return best;
  }, [strikes, spotPrice]);

  const [index, setIndex] = React.useState(defaultIndex);
  const [quote, setQuote] = React.useState<QuotePairResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = React.useState(true);
  const [lastFetchedAt, setLastFetchedAt] = React.useState<number | null>(null);

  const active = strikes[index];

  const fetchQuote = React.useCallback(async () => {
    if (!active) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        expiration,
        call_strike: String(active.strike),
        put_strike: String(active.strike),
      });
      const res = await fetch(`${apiBaseUrl}/api/quotes/spy?${params}`);
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as QuotePairResponse;
      setQuote(data);
      setLastFetchedAt(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [active, expiration, apiBaseUrl]);

  React.useEffect(() => {
    fetchQuote();
  }, [fetchQuote]);

  React.useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetchQuote, REFRESH_MS);
    return () => clearInterval(id);
  }, [autoRefresh, fetchQuote]);

  if (!active) {
    return (
      <div className="rounded-xl border border-border/70 bg-surface-2/40 p-4 text-sm text-muted">
        No strikes available.
      </div>
    );
  }

  const distance = spotPrice !== null ? active.strike - spotPrice : null;

  return (
    <div className="rounded-2xl border border-border/70 bg-surface-2/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
            disabled={index === 0}
            aria-label="Previous strike"
            className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-text transition-colors hover:bg-surface-2 disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <div className="rounded-lg border border-border/70 bg-surface px-4 py-2">
            <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">
              Active strike
            </div>
            <div className="font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold tabular text-text">
              ${active.strike.toFixed(0)}
            </div>
            {distance !== null && (
              <div
                className={
                  "mt-0.5 text-[0.7rem] font-bold tabular " +
                  (distance > 0 ? "text-green-bright" : distance < 0 ? "text-red-bright" : "text-muted")
                }
              >
                {distance > 0 ? "+" : ""}
                {distance.toFixed(2)} from spot
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => setIndex((i) => Math.min(strikes.length - 1, i + 1))}
            disabled={index === strikes.length - 1}
            aria-label="Next strike"
            className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-text transition-colors hover:bg-surface-2 disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <label className="inline-flex items-center gap-2 text-xs text-muted">
            <input
              type="checkbox"
              className="h-3.5 w-3.5"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh 15s
          </label>
          <button
            type="button"
            onClick={fetchQuote}
            disabled={loading}
            aria-label="Refresh quote now"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-blue/60 bg-blue/15 px-3 text-xs font-bold text-blue-bright transition-colors hover:bg-blue/25 disabled:opacity-50"
          >
            <RefreshCw className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-red/30 bg-red/[0.05] p-3 text-xs text-red-bright">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" strokeWidth={2} />
          <div>
            <div className="font-bold">Quote fetch failed</div>
            <div className="mt-0.5 font-mono text-[0.7rem] text-muted">{error}</div>
          </div>
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <QuoteCard
          tone="green"
          icon={<ArrowUp className="h-4 w-4" strokeWidth={2.5} />}
          label="Call"
          quote={quote?.call ?? null}
          loading={loading && !quote}
        />
        <QuoteCard
          tone="red"
          icon={<ArrowDown className="h-4 w-4" strokeWidth={2.5} />}
          label="Put"
          quote={quote?.put ?? null}
          loading={loading && !quote}
        />
      </div>

      {(quote?.warning || lastFetchedAt) && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[0.7rem] text-muted">
          {quote?.warning ? (
            <span className="text-amber">{quote.warning}</span>
          ) : (
            <span />
          )}
          {lastFetchedAt && (
            <span className="font-mono tabular">
              Last fetched {new Date(lastFetchedAt).toLocaleTimeString()}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function QuoteCard({
  tone,
  icon,
  label,
  quote,
  loading,
}: {
  tone: "green" | "red";
  icon: React.ReactNode;
  label: string;
  quote: OptionQuote | null;
  loading: boolean;
}) {
  const accent =
    tone === "green"
      ? "border-green/30 bg-green/[0.05] text-green-bright"
      : "border-red/30 bg-red/[0.05] text-red-bright";

  return (
    <div className={`rounded-xl border ${accent} p-4`}>
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-[0.7rem] font-bold uppercase tracking-[0.12em]">
          {label}
        </span>
        {quote?.provider && (
          <span className="ml-auto text-[0.6rem] font-mono text-muted">
            {quote.provider}
          </span>
        )}
      </div>

      {loading ? (
        <div className="mt-3 text-sm text-muted">Loading…</div>
      ) : !quote ? (
        <div className="mt-3 text-sm text-muted">No quote available.</div>
      ) : (
        <>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-[family-name:var(--font-display)] text-2xl font-extrabold tabular text-text">
              {fmtMoney(quote.mark)}
            </span>
            <span className="text-xs text-muted">mark</span>
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
            <Mini label="Bid" value={fmtMoney(quote.bid)} />
            <Mini label="Ask" value={fmtMoney(quote.ask)} />
            <Mini label="Spread" value={fmtMoney(quote.spread)} />
          </div>

          <div className="mt-2 grid grid-cols-4 gap-2 text-center text-xs">
            <Mini label="Δ" value={fmtNum(quote.delta, 2)} />
            <Mini label="Γ" value={fmtNum(quote.gamma, 3)} />
            <Mini label="Θ" value={fmtNum(quote.theta, 2)} />
            <Mini label="IV" value={fmtPct(quote.iv)} />
          </div>

          {quote.warning && (
            <div className="mt-2 text-[0.7rem] text-amber">{quote.warning}</div>
          )}
        </>
      )}
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-surface-2/50 p-2">
      <div className="text-[0.58rem] uppercase tracking-[0.12em] font-bold text-muted">
        {label}
      </div>
      <div className="mt-0.5 font-mono tabular text-text">{value}</div>
    </div>
  );
}

function fmtMoney(v: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `$${v.toFixed(2)}`;
}
function fmtNum(v: number | null, dp = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(dp);
}
function fmtPct(v: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(0)}%`;
}
