import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Compass,
  Eye,
  History,
  Layers,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import Link from "next/link";

const FEATURES = [
  {
    icon: Compass,
    title: "Structure-led decisions",
    body: "Prior-session anchors project forward through the day. Levels are protected; you see the read, not the recipe.",
    accent: "blue",
  },
  {
    icon: Sparkles,
    title: "AI-assisted morning brief",
    body: "GEX, max-pain, dark-pool prints, and option flow are checked against your structure before any setup is named.",
    accent: "violet",
  },
  {
    icon: Target,
    title: "Same-day options cockpit",
    body: "Live Tastytrade quotes, projected entry mark, delta-aware P/L on the trigger line — all gated by signal confirmation.",
    accent: "green",
  },
  {
    icon: History,
    title: "Replay Lab",
    body: "Step a session candle-by-candle without look-ahead, or open Full Day Review to grade outcomes.",
    accent: "amber",
  },
  {
    icon: BarChart3,
    title: "Journal analytics",
    body: "Confirmed signals build a personal record. Win rate, R:R distribution, and expectancy update in real time.",
    accent: "blue",
  },
  {
    icon: Eye,
    title: "Wait discipline",
    body: "Decision quality and risk guardrails appear before any trigger fires — no chase, no retest fade, no fake breakout.",
    accent: "violet",
  },
] as const;

export default function LandingPage() {
  return (
    <div className="relative isolate flex min-h-screen flex-col overflow-x-hidden">
      {/* Top nav */}
      <header className="z-30 mx-auto flex w-full max-w-7xl items-center justify-between gap-6 px-6 py-6">
        <Link href="/" className="group flex items-center gap-2.5">
          <div className="relative grid h-10 w-10 place-items-center rounded-xl border border-blue/40 bg-gradient-to-br from-blue/30 via-surface-2 to-surface-3 shadow-[0_0_0_1px_rgba(78,168,222,0.15),0_8px_22px_-6px_rgba(78,168,222,0.5)]">
            <Compass className="h-5 w-5 text-blue-bright" strokeWidth={2.5} />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-[family-name:var(--font-display)] text-base font-bold text-text">SPY Prophet</span>
            <span className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-blue-bright/80">Terminal</span>
          </div>
        </Link>
        <nav className="hidden gap-7 text-sm font-medium text-muted md:flex">
          <a className="transition-colors hover:text-text" href="#features">Features</a>
          <a className="transition-colors hover:text-text" href="#workflow">Workflow</a>
          <a className="transition-colors hover:text-text" href="#safety">Safety</a>
        </nav>
        <div className="flex items-center gap-3">
          <Link href="/live" className="hidden sm:inline-flex">
            <Button variant="ghost" size="sm">
              Open Terminal
              <ArrowUpRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/live" className="sm:hidden">
            <Button variant="primary" size="sm">Launch</Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 mx-auto flex w-full max-w-7xl flex-col items-center px-6 pt-12 pb-24 text-center md:pt-20 md:pb-32">
        <Pill tone="blue" size="md" className="mb-7">
          <Zap className="h-3 w-3" strokeWidth={3} />
          Structure-led · Same-day SPY
        </Pill>

        <h1 className="font-[family-name:var(--font-display)] text-5xl font-extrabold leading-[0.95] tracking-tight text-text sm:text-6xl md:text-7xl lg:text-[5.25rem]">
          The decision support
          <br />
          <span className="text-brand-gradient">your same-day SPY</span>
          <br />
          <span className="text-bullish-gradient">trades have been missing.</span>
        </h1>

        <p className="mt-8 max-w-2xl text-balance text-lg leading-relaxed text-muted md:text-xl">
          A purpose-built terminal for the trader who reads structure first.
          Prior-session anchors, dynamic projection, signal confirmation, and a
          live options cockpit — all gated by wait discipline.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link href="/live">
            <Button variant="primary" size="xl">
              Launch Terminal
              <ArrowRight className="h-5 w-5" />
            </Button>
          </Link>
          <Link href="/brief">
            <Button variant="ghost" size="xl">See Today&apos;s Brief</Button>
          </Link>
        </div>

        <p className="mt-7 text-xs font-bold uppercase tracking-[0.16em] text-muted">
          <span className="text-green-bright">✓ Analysis only</span>{"  ·  "}
          <span>No order execution</span>{"  ·  "}
          <span>Tastytrade integrated</span>
        </p>

        {/* Hero terminal preview card */}
        <div className="relative mt-16 w-full max-w-5xl">
          <div className="absolute inset-0 -z-10 mx-auto h-[60%] w-[80%] rounded-full bg-blue/20 blur-[120px]" aria-hidden />
          <Card premium hoverable className="overflow-hidden text-left">
            <div className="flex items-center justify-between gap-4 border-b border-border/70 bg-surface-2/50 px-5 py-3">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-red/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-green/70" />
              </div>
              <div className="flex items-center gap-2">
                <span className="live-pulse-dot" aria-hidden />
                <span className="font-mono text-[0.7rem] tabular text-muted">spyprophet.app/live</span>
              </div>
              <span className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-blue-bright">Terminal</span>
            </div>
            <div className="grid grid-cols-1 gap-px bg-border/60 sm:grid-cols-3">
              <div className="bg-surface/80 p-5">
                <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">SPY · Last</div>
                <div className="mt-1.5 font-[family-name:var(--font-display)] text-3xl font-extrabold tabular text-text">$623.41</div>
                <div className="mt-1 inline-flex items-center gap-1.5 text-xs font-bold tabular text-green-bright">
                  ▲ +1.04% <span className="font-medium text-muted">today</span>
                </div>
              </div>
              <div className="bg-surface/80 p-5">
                <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">VIX</div>
                <div className="mt-1.5 font-[family-name:var(--font-display)] text-3xl font-extrabold tabular text-green-bright">14.82</div>
                <div className="mt-1 text-xs font-medium text-muted">Calm regime</div>
              </div>
              <div className="bg-surface/80 p-5">
                <div className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">Decision</div>
                <div className="mt-1.5 font-[family-name:var(--font-display)] text-lg font-bold leading-tight text-text">
                  Watch upper structure trigger
                </div>
                <div className="mt-1 text-xs font-medium text-muted">Live read</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4">
              {[
                { label: "Bias", value: "Bullish" },
                { label: "Grade", value: "A" },
                { label: "Trigger", value: "624.85" },
                { label: "Target", value: "627.10" },
              ].map((c) => (
                <div key={c.label} className="rounded-xl border border-border/70 bg-surface-2/40 p-3">
                  <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">{c.label}</div>
                  <div className="mt-0.5 font-[family-name:var(--font-display)] text-lg font-bold tabular text-text">{c.value}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-24">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <Pill tone="violet" size="md" className="mb-5">
            <Layers className="h-3 w-3" strokeWidth={3} />
            What’s inside
          </Pill>
          <h2 className="font-[family-name:var(--font-display)] text-4xl font-extrabold tracking-tight text-text md:text-5xl">
            A terminal that thinks like a structure trader.
          </h2>
          <p className="mt-5 text-balance text-base text-muted md:text-lg">
            Built around discipline, not signals. Every panel exists to keep
            you out of bad trades and clear-headed in the good ones.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body, accent }) => (
            <Card key={title} hoverable glow={accent} className="p-6">
              <div
                className={
                  "mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl border " +
                  (accent === "blue"
                    ? "border-blue/40 bg-blue/10 text-blue-bright"
                    : accent === "green"
                      ? "border-green/40 bg-green/10 text-green-bright"
                      : accent === "violet"
                        ? "border-violet/40 bg-violet/10 text-violet"
                        : "border-amber/40 bg-amber/10 text-amber")
                }
              >
                <Icon className="h-5 w-5" strokeWidth={2.5} />
              </div>
              <h3 className="font-[family-name:var(--font-display)] text-lg font-bold text-text">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{body}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* Workflow strip */}
      <section id="workflow" className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-24">
        <Card premium className="overflow-hidden p-8 md:p-12">
          <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1.2fr_1fr]">
            <div>
              <Pill tone="green" size="md" className="mb-5">
                <Eye className="h-3 w-3" strokeWidth={3} />
                The day, in five steps
              </Pill>
              <h3 className="font-[family-name:var(--font-display)] text-3xl font-extrabold leading-tight text-text md:text-4xl">
                Open at 8:30 CT.
                <br />
                Read structure. Wait for the trigger.
                <br />
                <span className="text-bullish-gradient">Take the trade only on confirmation.</span>
              </h3>
              <p className="mt-5 max-w-xl text-base text-muted md:text-lg">
                The terminal walks the same loop you would: anchors set,
                projection drawn, bias declared, signal armed, contract priced.
                You only act when every gate flashes green.
              </p>
            </div>
            <ol className="grid grid-cols-1 gap-3">
              {[
                ["Pre-open", "Foresight projects today’s structure from prior anchors."],
                ["09:00 CT", "Daily Brief reconciles structure with GEX, max pain, dark pool, flow."],
                ["09:30 ET", "Live tab arms — wait discipline gates appear before any signal."],
                ["Trigger", "Hourly close confirms a rejection. Options cockpit prices the entry."],
                ["After close", "Replay Lab and Journal Analytics grade today’s outcome."],
              ].map(([when, what], i) => (
                <li key={when} className="flex items-start gap-3 rounded-xl border border-border/70 bg-surface-2/40 p-3.5">
                  <span className="inline-flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-blue/15 font-mono text-[0.78rem] font-bold tabular text-blue-bright">
                    {i + 1}
                  </span>
                  <div>
                    <div className="text-sm font-bold text-text">{when}</div>
                    <div className="text-xs leading-relaxed text-muted">{what}</div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </Card>
      </section>

      {/* Safety */}
      <section id="safety" className="relative z-10 mx-auto w-full max-w-5xl px-6 pb-24 text-center">
        <h3 className="font-[family-name:var(--font-display)] text-2xl font-extrabold tracking-tight text-text md:text-3xl">
          Built with discipline. Bounded by safety.
        </h3>
        <p className="mt-4 text-base text-muted md:text-lg">
          No order execution is implemented. No submit, cancel, replace, or
          dry-run trading endpoints exist anywhere in the codebase. SPY Prophet
          is decision support — every action is yours to take.
        </p>
        <div className="mt-7 flex flex-wrap items-center justify-center gap-2">
          <Pill tone="green">✓ Analysis only</Pill>
          <Pill tone="green">✓ No order execution</Pill>
          <Pill tone="blue">Hourly candles</Pill>
          <Pill tone="blue">US/Central display</Pill>
          <Pill tone="violet">Tastytrade live quotes</Pill>
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-24">
        <Card premium className="relative overflow-hidden p-12 text-center">
          <div className="absolute inset-x-0 top-0 -z-10 h-full w-full">
            <div className="absolute -top-1/2 left-1/2 h-[120%] w-[120%] -translate-x-1/2 rounded-full bg-blue/20 blur-[120px]" />
          </div>
          <h3 className="font-[family-name:var(--font-display)] text-3xl font-extrabold tracking-tight text-text md:text-5xl">
            Open the terminal.
          </h3>
          <p className="mx-auto mt-4 max-w-xl text-base text-muted md:text-lg">
            One URL. No setup. Your structure, your discipline, your edge.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/live">
              <Button variant="primary" size="xl">
                Launch Terminal
                <ArrowRight className="h-5 w-5" />
              </Button>
            </Link>
            <Link href="/foresight">
              <Button variant="ghost" size="xl">See Foresight</Button>
            </Link>
          </div>
        </Card>
      </section>

      <footer className="relative z-10 mx-auto w-full max-w-7xl px-6 py-8 text-xs text-muted">
        <div className="flex flex-col items-center gap-3 border-t border-border/70 pt-6 md:flex-row md:justify-between">
          <span className="font-semibold text-text">SPY Prophet</span>
          <span>Analysis only · No order execution · © {new Date().getFullYear()}</span>
        </div>
      </footer>
    </div>
  );
}
