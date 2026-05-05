import { AnimatedNumber } from "@/components/animated-number";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/reveal";
import { SpotlightCard } from "@/components/spotlight-card";
import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { DirectionGlyph } from "@/components/ui/direction-glyph";
import { Pill } from "@/components/ui/pill";
import { getLiveSnapshot, type LiveSnapshot } from "@/lib/api";
import {
  Activity,
  ArrowRight,
  Layers,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

// Default values for sections the API doesn't yet populate. Phase 2 will
// stream real bias/trigger/target/guardrail/intel data from the briefing
// helpers in app.py; until then the layout stays intact with sane numbers
// derived from the live spot price.
const DEFAULT_VIEW = {
  decisionLabel: "Live read · update on each close",
  bias: { label: "Calibrating", direction: "call" as const },
  signal: { label: "Awaiting structure read" },
  trigger: { name: "Upper structure", offsetFromSpot: 1.44 },
  target: { name: "Lower structure", offsetFromSpot: 3.69, rr: 1.55 },
  stopOffsetFromSpot: -0.63,
  guardrails: [
    { label: "Wait gate", state: "Live read", tone: "green" as const },
    { label: "Chase distance", state: "Within tolerance", tone: "green" as const },
    { label: "Daily loss cap", state: "Untouched", tone: "green" as const },
  ],
};

export const revalidate = 30;

export default async function LivePage() {
  const snapshot = await getLiveSnapshot();
  const view = composeView(snapshot);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      {/* Page heading */}
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <CardKicker className="mb-1.5 flex items-center gap-2">
              <Activity className="h-3 w-3" strokeWidth={3} /> Live Console
            </CardKicker>
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
              Today&apos;s structure read.
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">
              Pre-checked, pre-projected, and gated by wait discipline. Trigger fires only on hourly close confirmation.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {view.connected ? (
              <>
                <Pill tone="live" pulse>Streaming</Pill>
                <Pill tone="blue">Live · Connected</Pill>
              </>
            ) : (
              <Pill tone="amber" pulse>Reconnecting</Pill>
            )}
          </div>
        </div>
      </Reveal>

      {/* Command strip */}
      <Reveal delay={0.1}>
        <SpotlightCard premium tilt={false} className="overflow-hidden">
          <div className="grid grid-cols-2 gap-px bg-border/60 md:grid-cols-4">
            <div className="bg-surface/80 p-5">
              <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">SPY · Last</div>
              <div className="mt-1 font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tabular text-text">
                {view.spotPrice !== null ? (
                  <>
                    $<AnimatedNumber value={view.spotPrice} decimals={2} startDelay={300} />
                  </>
                ) : (
                  <span className="text-muted">—</span>
                )}
              </div>
              <div className={"mt-1 inline-flex items-center gap-1.5 text-[0.78rem] font-bold tabular " + view.changeToneClass}>
                {view.changePct !== null ? (
                  <>
                    {view.changePct >= 0 ? "▲ +" : "▼ "}
                    <AnimatedNumber value={Math.abs(view.changePct)} decimals={2} startDelay={400} />%
                    <span className="font-medium text-muted">today</span>
                  </>
                ) : (
                  <span className="font-medium text-muted">change unavailable</span>
                )}
              </div>
            </div>
            <div className="bg-surface/80 p-5">
              <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">VIX</div>
              <div className={"mt-1 font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tabular " + view.vixToneClass}>
                {view.vixValue !== null ? (
                  <AnimatedNumber value={view.vixValue} decimals={2} startDelay={400} />
                ) : (
                  <span className="text-muted">—</span>
                )}
              </div>
              <div className="mt-1 text-[0.78rem] font-medium text-muted">
                {view.vixRegime ?? "Regime unavailable"}
              </div>
            </div>
            <div className="bg-surface/80 p-5 col-span-2 md:col-span-1">
              <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">Decision</div>
              <div className="mt-1 font-[family-name:var(--font-space-grotesk)] text-lg font-bold leading-tight text-text">
                {view.decisionLabel}
              </div>
              <div className="mt-1 text-[0.78rem] font-medium text-muted">Live read · update on each close</div>
            </div>
            <div className="bg-surface/80 p-5 col-span-2 md:col-span-1 flex flex-col justify-center">
              <div className="flex items-center gap-2">
                <span className="live-pulse-dot" aria-hidden />
                <span className="text-[0.78rem] font-bold uppercase tracking-[0.12em] text-green-bright">
                  {view.connected ? "Live data" : "Cold cache"}
                </span>
              </div>
              <div className="mt-1.5 text-[0.74rem] text-muted leading-snug">
                Hourly candles · Live options chain
              </div>
            </div>
          </div>
        </SpotlightCard>
      </Reveal>

      {/* Headline decision row */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Reveal delay={0.18}>
          <SpotlightCard premium className="overflow-hidden">
            <CardHeader>
              <div>
                <CardKicker>Decision</CardKicker>
                <CardTitle className="mt-1.5 text-2xl md:text-3xl text-bullish-gradient">
                  {view.headline}
                </CardTitle>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
                  Trigger fires on hourly close confirmation. Until then, no trade.
                </p>
              </div>
              <DirectionGlyph direction={view.bias.direction} label={`Bias · ${view.bias.label}`} size="lg" />
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  {
                    label: "Bias",
                    value: view.bias.label,
                    glyph: <DirectionGlyph direction={view.bias.direction} size="sm" label={view.bias.label} />,
                  },
                  { label: "Grade", value: view.grade ?? "—" },
                  { label: "Action", value: humanizeAction(view.action) ?? (view.connected ? "Watch" : "Wait") },
                  { label: "Signal", value: view.signal.label },
                ].map((cell) => (
                  <div key={cell.label} className="overflow-hidden rounded-xl border border-border/70 bg-surface-2/50 p-3.5">
                    <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">{cell.label}</div>
                    <div className="mt-1.5 flex items-center gap-2">
                      {cell.glyph ?? (
                        <span className="line-clamp-2 break-words font-[family-name:var(--font-display)] text-sm font-bold leading-snug text-text tabular md:text-base">
                          {cell.value}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <StaggerGroup className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3" delayChildren={0.1}>
                {view.guardrails.map((g) => (
                  <StaggerItem key={g.label}>
                    <div className="rounded-xl border border-green/20 bg-green/[0.04] p-3.5">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 text-green-bright" strokeWidth={2.5} />
                        <span className="text-[0.7rem] font-bold uppercase tracking-[0.12em] text-muted">
                          {g.label}
                        </span>
                      </div>
                      <div className="mt-1 text-sm font-bold text-green-bright">{g.state}</div>
                    </div>
                  </StaggerItem>
                ))}
              </StaggerGroup>
            </CardBody>
          </SpotlightCard>
        </Reveal>

        {/* Trigger panel */}
        <Reveal delay={0.26}>
          <SpotlightCard className="overflow-hidden shadow-[0_0_0_1px_rgba(245,196,81,0.32),0_18px_60px_-10px_rgba(245,196,81,0.32)]">
            <CardHeader>
              <div>
                <CardKicker className="text-amber">Trigger Line</CardKicker>
                <CardTitle className="mt-1.5">{view.trigger.name}</CardTitle>
              </div>
              <Target className="h-6 w-6 text-amber" strokeWidth={2.5} />
            </CardHeader>
            <CardBody>
              <div className="font-[family-name:var(--font-space-grotesk)] text-4xl font-extrabold tabular text-text">
                {view.trigger.value !== null ? (
                  <>
                    $<AnimatedNumber value={view.trigger.value} decimals={2} startDelay={500} />
                  </>
                ) : (
                  <span className="text-muted">—</span>
                )}
              </div>
              <div className="mt-1.5 text-sm text-muted">
                {view.trigger.distance !== null
                  ? `${view.trigger.distance >= 0 ? "+" : ""}${view.trigger.distance.toFixed(2)} from spot`
                  : "Distance unavailable"}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-border/70 bg-surface-2/50 p-3">
                  <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">Stop</div>
                  <div className="mt-0.5 font-[family-name:var(--font-space-grotesk)] text-lg font-bold tabular text-red-bright">
                    {view.stop !== null ? (
                      <>
                        $<AnimatedNumber value={view.stop} decimals={2} startDelay={600} />
                      </>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-border/70 bg-surface-2/50 p-3">
                  <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">R:R</div>
                  <div className="mt-0.5 font-[family-name:var(--font-space-grotesk)] text-lg font-bold tabular text-text">
                    {view.target.rr !== null ? (
                      <>1 : <AnimatedNumber value={view.target.rr} decimals={2} startDelay={650} /></>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-3 rounded-lg border border-blue/30 bg-blue/[0.06] p-3">
                <div className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-blue-bright">
                  <ArrowRight className="h-3 w-3" strokeWidth={3} /> Target
                </div>
                <div className="mt-0.5 flex items-baseline gap-2 text-sm">
                  <span className="font-[family-name:var(--font-space-grotesk)] text-xl font-bold tabular text-text">
                    {view.target.value !== null ? (
                      <>
                        $<AnimatedNumber value={view.target.value} decimals={2} startDelay={700} />
                      </>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </span>
                  <span className="text-muted">{view.target.name}</span>
                </div>
              </div>
            </CardBody>
          </SpotlightCard>
        </Reveal>
      </div>

      {/* Intel grid — UnusualWhales flow context */}
      {view.intel && view.intel.length > 0 && (
        <Reveal delay={0.22}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4">
            {view.intel.map((tile) => (
              <Card
                key={tile.label}
                hoverable
                className="p-4"
                glow={tile.tone === "green" ? "green" : tile.tone === "amber" ? "amber" : "blue"}
              >
                <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">
                  {tile.label}
                </div>
                <div
                  className={
                    "mt-1.5 font-[family-name:var(--font-display)] text-base font-extrabold tabular " +
                    (tile.tone === "green"
                      ? "text-green-bright"
                      : tile.tone === "amber"
                        ? "text-amber"
                        : "text-blue-bright")
                  }
                >
                  {tile.value}
                </div>
                <div className="mt-1 line-clamp-3 text-xs leading-snug text-muted">
                  {tile.body}
                </div>
              </Card>
            ))}
          </div>
        </Reveal>
      )}

      {/* Watchlist contracts */}
      <Card hoverable className="overflow-hidden">
        <CardHeader>
          <div>
            <CardKicker className="flex items-center gap-2">
              <Layers className="h-3 w-3" strokeWidth={3} /> Same-day Watchlist
            </CardKicker>
            <CardTitle className="mt-1.5">OTM contracts armed</CardTitle>
          </div>
          <Pill tone="violet">Live quotes</Pill>
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
                <Pill tone="green" size="xs">0DTE</Pill>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="font-[family-name:var(--font-display)] text-3xl font-extrabold tabular text-text">
                  {view.watchCall !== null ? `$${view.watchCall}` : "—"}
                </span>
                <span className="text-sm text-muted">strike · 0DTE</span>
              </div>
              <p className="mt-3 text-xs text-muted">
                Live mark, Δ, and spread populate when the options route is queried.
              </p>
            </div>
            <div className="rounded-xl border border-red/30 bg-red/[0.05] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TrendingDown className="h-4 w-4 text-red-bright" strokeWidth={2.5} />
                  <span className="text-[0.7rem] font-bold uppercase tracking-[0.12em] text-red-bright">
                    Put
                  </span>
                </div>
                <Pill tone="red" size="xs">0DTE</Pill>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="font-[family-name:var(--font-display)] text-3xl font-extrabold tabular text-text">
                  {view.watchPut !== null ? `$${view.watchPut}` : "—"}
                </span>
                <span className="text-sm text-muted">strike · 0DTE</span>
              </div>
              <p className="mt-3 text-xs text-muted">
                Live mark, Δ, and spread populate when the options route is queried.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

interface ComposedView {
  connected: boolean;
  spotPrice: number | null;
  changePct: number | null;
  changeToneClass: string;
  vixValue: number | null;
  vixRegime: string | null;
  vixToneClass: string;
  decisionLabel: string;
  headline: string;
  bias: { label: string; direction: "call" | "put" | "neutral" };
  signal: { label: string };
  trigger: { name: string; value: number | null; distance: number | null };
  target: { name: string; value: number | null; rr: number | null };
  stop: number | null;
  guardrails: Array<{ label: string; state: string; tone: "green" | "amber" | "red" }>;
  grade: string | null;
  action: string | null;
  intel: Array<{ label: string; value: string; body: string; tone: "green" | "amber" | "blue" }> | null;
  watchCall: number | null;
  watchPut: number | null;
}

function humanizeAction(action: string | null): string | null {
  if (!action) return null;
  // Map app.py decision-state final_decision codes to short, readable labels.
  const map: Record<string, string> = {
    TRADE_ALLOWED: "Trade",
    SELECTIVE_TRADE: "Selective",
    WAIT_FOR_CONFIRMATION: "Wait",
    WAIT_FOR_RETEST: "Retest",
    NO_TRADE: "No trade",
    STOP_TRADING: "Stop",
  };
  return map[action] ?? action.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());
}

function composeView(snapshot: LiveSnapshot | null): ComposedView {
  if (!snapshot) {
    return {
      connected: false,
      spotPrice: null,
      changePct: null,
      changeToneClass: "text-muted",
      vixValue: null,
      vixRegime: null,
      vixToneClass: "text-text",
      decisionLabel: "Reconnecting to live feed…",
      headline: "Awaiting live data",
      bias: { ...DEFAULT_VIEW.bias },
      signal: { label: DEFAULT_VIEW.signal.label },
      trigger: { name: DEFAULT_VIEW.trigger.name, value: null, distance: null },
      target: { name: DEFAULT_VIEW.target.name, value: null, rr: DEFAULT_VIEW.target.rr },
      stop: null,
      guardrails: DEFAULT_VIEW.guardrails,
      grade: null,
      action: null,
      intel: null,
      watchCall: null,
      watchPut: null,
    };
  }

  const spotPrice = snapshot.spot.price;
  const changePct = snapshot.spot.change_pct;
  const changeToneClass =
    changePct === null
      ? "text-muted"
      : changePct >= 0
        ? "text-green-bright"
        : "text-red-bright";

  const vixToneClass =
    snapshot.vix.regime_tone === "green"
      ? "text-green-bright"
      : snapshot.vix.regime_tone === "amber"
        ? "text-amber"
        : snapshot.vix.regime_tone === "red"
          ? "text-red-bright"
          : "text-text";

  const trigger = snapshot.trigger ?? {
    name: DEFAULT_VIEW.trigger.name,
    value: spotPrice !== null ? spotPrice + DEFAULT_VIEW.trigger.offsetFromSpot : null,
    distance: spotPrice !== null ? DEFAULT_VIEW.trigger.offsetFromSpot : null,
  };
  const target = snapshot.target ?? {
    name: DEFAULT_VIEW.target.name,
    value: spotPrice !== null ? spotPrice + DEFAULT_VIEW.target.offsetFromSpot : null,
    rr: DEFAULT_VIEW.target.rr,
  };
  const stop =
    snapshot.stop ??
    (spotPrice !== null ? spotPrice + DEFAULT_VIEW.stopOffsetFromSpot : null);

  // Headline matches the setup direction: PUT setup needs price to
  // close *below* the trigger line (rejection from above); CALL setup
  // needs a close *above* (rejection from below).
  const setup = snapshot.trigger?.setup;
  const headline =
    trigger.value !== null
      ? `Hold for trigger close ${setup === "PUT" ? "below" : "above"} ${trigger.value.toFixed(2)}`
      : "Live read · awaiting structure projection";

  return {
    connected: true,
    spotPrice,
    changePct,
    changeToneClass,
    vixValue: snapshot.vix.value,
    vixRegime: snapshot.vix.regime,
    vixToneClass,
    decisionLabel: snapshot.decision_label || DEFAULT_VIEW.decisionLabel,
    headline,
    bias: snapshot.bias
      ? { label: snapshot.bias.label, direction: snapshot.bias.direction }
      : { ...DEFAULT_VIEW.bias },
    signal: snapshot.signal
      ? { label: snapshot.signal.label }
      : { label: DEFAULT_VIEW.signal.label },
    trigger,
    target,
    stop,
    guardrails: snapshot.guardrails ?? DEFAULT_VIEW.guardrails,
    grade: snapshot.grade,
    action: snapshot.action,
    intel: snapshot.intel ?? null,
    watchCall: snapshot.watch.call,
    watchPut: snapshot.watch.put,
  };
}
