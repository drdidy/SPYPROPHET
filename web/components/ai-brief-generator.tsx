"use client";

import {
  AlertTriangle,
  Loader2,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import * as React from "react";

interface ExternalContextItem {
  label?: string;
  summary?: string;
  status?: string;
  detail?: string;
}

interface AiBriefDecision {
  stance: string;
  headline: string;
  primary_trade?: {
    label?: string;
    trigger_line?: string;
    trigger_price?: string | number;
    contract?: string;
    entry_timing?: string;
    entry_rule?: string;
    stop?: string | number;
    target?: string | number;
    confidence?: number;
  };
  why?: string[];
  avoid?: { reason?: string; mitigation?: string }[];
  risk_flags?: string[];
  novice_summary?: string;
  source_notes?: string[];
}

interface AiBriefResult {
  generated_at: string;
  provider: string;
  model?: string | null;
  confidence: number;
  decision: AiBriefDecision;
  warnings: string[];
  citations?: { source?: string; url?: string }[];
  source_statuses?: { name?: string; status?: string; detail?: string }[];
  external_context?: {
    dark_pool?: ExternalContextItem | null;
    dealer_gex?: ExternalContextItem | null;
    global_context?: { label?: string; symbol?: string; close?: number; change_pct?: number }[];
    sector_context?: { label?: string; symbol?: string; close?: number; change_pct?: number }[];
    sentiment?: { score?: number; tone?: string; explanation?: string };
  };
}

interface AiBriefGeneratorProps {
  apiBaseUrl: string;
}

export function AiBriefGenerator({ apiBaseUrl }: AiBriefGeneratorProps) {
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<AiBriefResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/brief/spy/generate`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as AiBriefResult;
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-violet/30 bg-violet/[0.04] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-violet">
            AI synthesis
          </div>
          <h2 className="mt-1 font-[family-name:var(--font-space-grotesk)] text-xl font-extrabold text-text">
            Generate Daily Brief
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Calls OpenAI with the day&apos;s structure, news, calendar,
            and external-context inputs. Returns a structured stance
            (TAKE / WAIT / NO_TRADE), the trigger trade, why-points,
            and risk flags. Cached 15 minutes server-side.
          </p>
        </div>
        <button
          type="button"
          onClick={generate}
          disabled={busy}
          className="inline-flex h-11 items-center gap-2 rounded-xl border border-violet/60 bg-violet/15 px-5 text-sm font-bold text-violet transition-colors hover:bg-violet/25 disabled:opacity-50"
        >
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              {result ? "Regenerate" : "Generate Daily Brief"}
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-red/40 bg-red/[0.05] p-3 text-xs text-red-bright">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" strokeWidth={2} />
          <div>
            <div className="font-bold">Brief generation failed</div>
            <div className="mt-1 font-mono text-[0.7rem] text-muted">{error}</div>
          </div>
        </div>
      )}

      {result && <RenderResult result={result} />}
    </div>
  );
}

function RenderResult({ result }: { result: AiBriefResult }) {
  const d = result.decision;
  const stanceTone =
    d.stance === "TAKE"
      ? "green"
      : d.stance === "NO_TRADE"
        ? "red"
        : "amber";

  return (
    <div className="mt-5 grid gap-5">
      <div className="rounded-xl border border-border/70 bg-surface/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">
              <span
                className={
                  stanceTone === "green"
                    ? "text-green-bright"
                    : stanceTone === "red"
                      ? "text-red-bright"
                      : "text-amber"
                }
              >
                Stance · {d.stance}
              </span>
              <span>· confidence {result.confidence}/100</span>
            </div>
            <div className="mt-2 font-[family-name:var(--font-space-grotesk)] text-lg font-extrabold leading-snug text-text">
              {d.headline}
            </div>
          </div>
          {result.model && (
            <span className="rounded-full border border-violet/40 bg-violet/10 px-2.5 py-1 text-[0.6rem] font-bold uppercase tracking-[0.14em] text-violet">
              {result.model}
            </span>
          )}
        </div>

        {d.primary_trade && (
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Mini label="Trigger" value={d.primary_trade.trigger_line ?? "—"} />
            <Mini label="Trigger price" value={String(d.primary_trade.trigger_price ?? "—")} />
            <Mini label="Stop" value={String(d.primary_trade.stop ?? "—")} />
            <Mini label="Target" value={String(d.primary_trade.target ?? "—")} />
          </div>
        )}

        {d.primary_trade?.entry_rule && (
          <p className="mt-3 text-sm leading-relaxed text-muted">
            <span className="font-bold text-text">Entry rule: </span>
            {d.primary_trade.entry_rule}
          </p>
        )}
      </div>

      {d.why && d.why.length > 0 && (
        <div className="rounded-xl border border-border/70 bg-surface/60 p-5">
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-blue-bright">
            Why it matters
          </div>
          <ul className="mt-3 grid grid-cols-1 gap-2 text-sm leading-relaxed text-text md:grid-cols-2">
            {d.why.map((w, i) => (
              <li
                key={i}
                className="flex items-start gap-2 rounded-lg border border-border/70 bg-surface-2/40 p-3"
              >
                <span className="mt-0.5 inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-bright" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {d.risk_flags && d.risk_flags.length > 0 && (
        <div className="rounded-xl border border-amber/30 bg-amber/[0.05] p-5">
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-amber">
            Risk flags
          </div>
          <ul className="mt-3 grid grid-cols-1 gap-2 text-sm leading-relaxed text-text">
            {d.risk_flags.map((r, i) => (
              <li key={i} className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber" strokeWidth={2} />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.external_context && <ExternalContext ctx={result.external_context} />}

      {d.novice_summary && (
        <div className="rounded-xl border border-border/70 bg-surface-2/40 p-4">
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">
            One-liner
          </div>
          <p className="mt-2 text-sm leading-relaxed text-text">{d.novice_summary}</p>
        </div>
      )}
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-surface-2/50 p-3">
      <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="mt-0.5 font-mono tabular text-text">{value}</div>
    </div>
  );
}

function ExternalContext({ ctx }: { ctx: AiBriefResult["external_context"] }) {
  if (!ctx) return null;
  const cards: { title: string; tone: "blue" | "violet" | "green" | "amber"; lines: { label: string; value: string }[] }[] = [];

  if (ctx.dark_pool) {
    cards.push({
      title: "Dark pool",
      tone: "violet",
      lines: collectKv(ctx.dark_pool, ["label", "summary", "status", "detail"]),
    });
  }
  if (ctx.dealer_gex) {
    cards.push({
      title: "Dealer GEX",
      tone: "amber",
      lines: collectKv(ctx.dealer_gex, ["label", "summary", "status", "detail"]),
    });
  }
  if (ctx.sentiment) {
    cards.push({
      title: "Sentiment",
      tone: "blue",
      lines: [
        { label: "Tone", value: String(ctx.sentiment.tone ?? "—") },
        { label: "Score", value: String(ctx.sentiment.score ?? "—") },
        { label: "Detail", value: String(ctx.sentiment.explanation ?? "—") },
      ],
    });
  }

  if (cards.length === 0 && (!ctx.global_context || ctx.global_context.length === 0)) {
    return null;
  }

  return (
    <div className="grid gap-3">
      <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">
        External context
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {cards.map((c) => (
          <div
            key={c.title}
            className={
              "rounded-xl border bg-surface/60 p-4 " +
              (c.tone === "violet"
                ? "border-violet/30"
                : c.tone === "amber"
                  ? "border-amber/30"
                  : c.tone === "green"
                    ? "border-green/30"
                    : "border-blue/30")
            }
          >
            <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">
              {c.title}
            </div>
            <div className="mt-2 grid gap-1.5 text-xs text-text">
              {c.lines.map((l, i) => (
                <div key={i} className="flex flex-wrap items-start gap-2">
                  <span className="font-bold text-muted">{l.label}:</span>
                  <span className="flex-1 break-words">{l.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {ctx.global_context && ctx.global_context.length > 0 && (
        <div className="rounded-xl border border-border/70 bg-surface/60 p-4">
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">
            Global tape
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            {ctx.global_context.slice(0, 8).map((m, i) => {
              const pct = m.change_pct;
              const isUp = (pct ?? 0) >= 0;
              const ChangeIcon = isUp ? TrendingUp : TrendingDown;
              return (
                <div key={i} className="rounded-lg border border-border/70 bg-surface-2/50 p-3">
                  <div className="text-[0.6rem] font-bold uppercase tracking-[0.12em] text-muted">
                    {m.label ?? m.symbol ?? "—"}
                  </div>
                  <div className="mt-0.5 font-mono tabular text-sm text-text">
                    {m.close !== undefined ? m.close.toFixed(2) : "—"}
                  </div>
                  {pct !== undefined && (
                    <div
                      className={
                        "mt-0.5 inline-flex items-center gap-1 text-[0.7rem] font-bold tabular " +
                        (isUp ? "text-green-bright" : "text-red-bright")
                      }
                    >
                      <ChangeIcon className="h-3 w-3" strokeWidth={2.5} />
                      {pct >= 0 ? "+" : ""}
                      {pct.toFixed(2)}%
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function collectKv(
  obj: ExternalContextItem | null | undefined,
  keys: string[],
): { label: string; value: string }[] {
  if (!obj || typeof obj !== "object") return [];
  const rows: { label: string; value: string }[] = [];
  for (const k of keys) {
    const v = (obj as Record<string, unknown>)[k];
    if (v !== undefined && v !== null && v !== "") {
      rows.push({ label: cap(k.replace(/_/g, " ")), value: String(v) });
    }
  }
  return rows;
}
function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
