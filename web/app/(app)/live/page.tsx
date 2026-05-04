import { CommandStrip } from "@/components/command-strip";
import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { DirectionGlyph } from "@/components/ui/direction-glyph";
import { Pill } from "@/components/ui/pill";
import {
  Activity,
  ArrowRight,
  Compass,
  Layers,
  ShieldCheck,
  Target,
  Timer,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";

// Demo data — replaced with real API once FastAPI is wired up.
const DEMO = {
  spyPrice: 623.41,
  spyChangePct: 1.04,
  vix: 14.82,
  decisionLabel: "Watch upper structure trigger",
  bias: { label: "Bullish", direction: "call" as const, score: 78 },
  signal: { label: "Pending confirmation", direction: "call" as const, line: "Upper Ascending" },
  trigger: { name: "Upper Ascending", value: 624.85, distance: 1.44 },
  target: { name: "Lower Descending", value: 627.1, rr: 1.55 },
  stop: 622.78,
  watchCall: 625,
  watchPut: 622,
  guardrails: [
    { label: "Chase distance", state: "Within tolerance", tone: "green" as const },
    { label: "Retest fade", state: "Fresh approach", tone: "green" as const },
    { label: "Daily loss cap", state: "Untouched", tone: "green" as const },
  ],
  intel: [
    { label: "VIX regime", value: "Calm", body: "Premium can be thin", tone: "blue" as const },
    { label: "SPY pressure", value: "Bid", body: "+3 bar momentum", tone: "green" as const },
    { label: "Trigger gap", value: "$1.44", body: "Inside reach window", tone: "amber" as const },
    { label: "Pivot window", value: "08:30–15:00 CT", body: "Prior RTH anchors", tone: "blue" as const },
  ],
};

export default function LivePage() {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      {/* Page heading */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <CardKicker className="mb-1.5 flex items-center gap-2">
            <Activity className="h-3 w-3" strokeWidth={3} /> Live Console
          </CardKicker>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
            Today’s structure read.
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">
            Pre-checked, pre-projected, and gated by wait discipline. Trigger fires only on hourly close confirmation.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="live" pulse>Streaming</Pill>
          <Pill tone="blue">Tastytrade · Connected</Pill>
        </div>
      </div>

      {/* Command strip */}
      <CommandStrip
        spyPrice={DEMO.spyPrice}
        spyChangePct={DEMO.spyChangePct}
        vix={DEMO.vix}
        decisionLabel={DEMO.decisionLabel}
      />

      {/* Headline decision row */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Card premium className="overflow-hidden">
          <CardHeader>
            <div>
              <CardKicker>Decision</CardKicker>
              <CardTitle className="mt-1.5 text-2xl md:text-3xl text-bullish-gradient">
                Hold for trigger close above {DEMO.trigger.value.toFixed(2)}
              </CardTitle>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
                Price is above the upper structure. A touch from above followed by an
                hourly close back above {DEMO.trigger.name.toLowerCase()} confirms calls.
                Until then, no trade.
              </p>
            </div>
            <DirectionGlyph direction={DEMO.bias.direction} label={`Bias · ${DEMO.bias.label}`} size="lg" />
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {[
                { label: "Bias", value: DEMO.bias.label, glyph: <DirectionGlyph direction={DEMO.bias.direction} size="sm" label={DEMO.bias.label} /> },
                { label: "Grade", value: "A", tone: "green" },
                { label: "Action", value: "Watch", tone: "amber" },
                { label: "Signal", value: DEMO.signal.label, tone: "blue" },
              ].map((cell) => (
                <div key={cell.label} className="rounded-xl border border-border/70 bg-surface-2/50 p-3.5">
                  <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">{cell.label}</div>
                  <div className="mt-1.5 flex items-center gap-2">
                    {cell.glyph ?? (
                      <span className="font-[family-name:var(--font-display)] text-base font-bold leading-tight text-text tabular">
                        {cell.value}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Wait discipline gates */}
            <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
              {DEMO.guardrails.map((g) => (
                <div
                  key={g.label}
                  className="rounded-xl border border-green/20 bg-green/[0.04] p-3.5"
                >
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-green-bright" strokeWidth={2.5} />
                    <span className="text-[0.7rem] font-bold uppercase tracking-[0.12em] text-muted">
                      {g.label}
                    </span>
                  </div>
                  <div className="mt-1 text-sm font-bold text-green-bright">{g.state}</div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        {/* Trigger panel */}
        <Card glow="amber" className="overflow-hidden">
          <CardHeader>
            <div>
              <CardKicker className="text-amber">Trigger Line</CardKicker>
              <CardTitle className="mt-1.5">{DEMO.trigger.name}</CardTitle>
            </div>
            <Target className="h-6 w-6 text-amber" strokeWidth={2.5} />
          </CardHeader>
          <CardBody>
            <div className="font-[family-name:var(--font-display)] text-4xl font-extrabold tabular text-text">
              ${DEMO.trigger.value.toFixed(2)}
            </div>
            <div className="mt-1.5 text-sm text-muted">
              {DEMO.trigger.distance > 0 ? "+" : ""}
              {DEMO.trigger.distance.toFixed(2)} from spot
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-border/70 bg-surface-2/50 p-3">
                <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">Stop</div>
                <div className="mt-0.5 font-[family-name:var(--font-display)] text-lg font-bold tabular text-red-bright">
                  ${DEMO.stop.toFixed(2)}
                </div>
              </div>
              <div className="rounded-lg border border-border/70 bg-surface-2/50 p-3">
                <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">R:R</div>
                <div className="mt-0.5 font-[family-name:var(--font-display)] text-lg font-bold tabular text-text">
                  1 : {DEMO.target.rr.toFixed(2)}
                </div>
              </div>
            </div>
            <div className="mt-3 rounded-lg border border-blue/30 bg-blue/[0.06] p-3">
              <div className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-blue-bright">
                <ArrowRight className="h-3 w-3" strokeWidth={3} /> Target
              </div>
              <div className="mt-0.5 flex items-baseline gap-2 text-sm">
                <span className="font-[family-name:var(--font-display)] text-xl font-bold tabular text-text">
                  ${DEMO.target.value.toFixed(2)}
                </span>
                <span className="text-muted">{DEMO.target.name}</span>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Intel grid */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {DEMO.intel.map((tile) => (
          <Card
            key={tile.label}
            hoverable
            className="p-4"
            glow={tile.tone === "green" ? "green" : tile.tone === "amber" ? "amber" : "blue"}
          >
            <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">{tile.label}</div>
            <div
              className={
                "mt-1.5 font-[family-name:var(--font-display)] text-xl font-extrabold tabular " +
                (tile.tone === "green"
                  ? "text-green-bright"
                  : tile.tone === "amber"
                    ? "text-amber"
                    : "text-blue-bright")
              }
            >
              {tile.value}
            </div>
            <div className="mt-1 text-xs text-muted">{tile.body}</div>
          </Card>
        ))}
      </div>

      {/* Watchlist contracts */}
      <Card hoverable className="overflow-hidden">
        <CardHeader>
          <div>
            <CardKicker className="flex items-center gap-2">
              <Layers className="h-3 w-3" strokeWidth={3} /> Same-day Watchlist
            </CardKicker>
            <CardTitle className="mt-1.5">OTM contracts armed</CardTitle>
          </div>
          <Pill tone="violet">Tastytrade live</Pill>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-green/30 bg-green/[0.05] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-green-bright" strokeWidth={2.5} />
                  <span className="text-[0.7rem] font-bold uppercase tracking-[0.12em] text-green-bright">
                    Call
                  </span>
                </div>
                <Pill tone="green" size="xs">▲ +0.18</Pill>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="font-[family-name:var(--font-display)] text-3xl font-extrabold tabular text-text">
                  ${DEMO.watchCall}
                </span>
                <span className="text-sm text-muted">strike · 0DTE</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-lg border border-border/70 bg-surface-2/50 p-2">
                  <div className="text-[0.6rem] uppercase tracking-[0.12em] font-bold text-muted">Mark</div>
                  <div className="mt-0.5 font-mono tabular text-text">$1.42</div>
                </div>
                <div className="rounded-lg border border-border/70 bg-surface-2/50 p-2">
                  <div className="text-[0.6rem] uppercase tracking-[0.12em] font-bold text-muted">Δ</div>
                  <div className="mt-0.5 font-mono tabular text-text">0.42</div>
                </div>
                <div className="rounded-lg border border-border/70 bg-surface-2/50 p-2">
                  <div className="text-[0.6rem] uppercase tracking-[0.12em] font-bold text-muted">Spread</div>
                  <div className="mt-0.5 font-mono tabular text-text">$0.04</div>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-red/30 bg-red/[0.05] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TrendingDown className="h-4 w-4 text-red-bright" strokeWidth={2.5} />
                  <span className="text-[0.7rem] font-bold uppercase tracking-[0.12em] text-red-bright">
                    Put
                  </span>
                </div>
                <Pill tone="red" size="xs">▼ -0.06</Pill>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="font-[family-name:var(--font-display)] text-3xl font-extrabold tabular text-text">
                  ${DEMO.watchPut}
                </span>
                <span className="text-sm text-muted">strike · 0DTE</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-lg border border-border/70 bg-surface-2/50 p-2">
                  <div className="text-[0.6rem] uppercase tracking-[0.12em] font-bold text-muted">Mark</div>
                  <div className="mt-0.5 font-mono tabular text-text">$1.16</div>
                </div>
                <div className="rounded-lg border border-border/70 bg-surface-2/50 p-2">
                  <div className="text-[0.6rem] uppercase tracking-[0.12em] font-bold text-muted">Δ</div>
                  <div className="mt-0.5 font-mono tabular text-text">-0.38</div>
                </div>
                <div className="rounded-lg border border-border/70 bg-surface-2/50 p-2">
                  <div className="text-[0.6rem] uppercase tracking-[0.12em] font-bold text-muted">Spread</div>
                  <div className="mt-0.5 font-mono tabular text-text">$0.05</div>
                </div>
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Footer note */}
      <div className="mt-2 rounded-xl border border-amber/30 bg-amber/[0.05] p-4 text-xs text-amber">
        <div className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.16em]">
          <Timer className="h-3.5 w-3.5" strokeWidth={3} /> Demo data
        </div>
        <p className="mt-1.5 leading-relaxed text-muted">
          This page renders example values until the FastAPI backend is wired up.
          The structure logic, signal engine, and journal will stream from your
          existing Python code via JSON endpoints — same edge, faster pages.
        </p>
      </div>
    </div>
  );
}
