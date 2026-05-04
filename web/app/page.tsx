import { AnimatedNumber } from "@/components/animated-number";
import { BrandLogo, BrandMark } from "@/components/brand-mark";
import { LiveChart } from "@/components/live-chart";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/reveal";
import { SpotlightCard } from "@/components/spotlight-card";
import { TickerTape } from "@/components/ticker-tape";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/ui/pill";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Eye,
  History,
  ShieldCheck,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="relative isolate flex min-h-screen flex-col overflow-x-hidden">
      {/* Top nav */}
      <header className="relative z-30 mx-auto flex w-full max-w-7xl items-center justify-between gap-6 px-6 py-6">
        <Link href="/" className="group inline-flex items-center gap-3" aria-label="SPY Prophet home">
          <BrandMark size={56} animated />
          <span className="flex flex-col leading-none">
            <span className="font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold tracking-tight text-text">
              SPY Prophet
            </span>
            <span className="mt-1 text-[0.7rem] font-bold uppercase tracking-[0.22em] text-blue-bright/85">
              Structure Terminal
            </span>
          </span>
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
      <section className="relative z-10 mx-auto w-full max-w-7xl px-6 pt-6 pb-16 md:pt-12 md:pb-20">
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
          {/* Left: copy */}
          <div>
            <Reveal>
              <Pill tone="blue" size="md" pulse>
                <Zap className="h-3 w-3" strokeWidth={3} />
                <span>Live · Same-day SPY</span>
              </Pill>
            </Reveal>

            <Reveal delay={0.1} as="h1" className="mt-6 font-[family-name:var(--font-space-grotesk)] text-[2.6rem] font-extrabold leading-[0.95] tracking-tight text-text sm:text-[3.2rem] md:text-[3.7rem] lg:text-[4.1rem]">
              <span className="block">Read the structure.</span>
              <span className="block text-brand-gradient">Wait for the close.</span>
              <span className="block text-bullish-gradient">Take only the trigger.</span>
            </Reveal>

            <Reveal delay={0.18} as="p" className="mt-6 max-w-xl text-balance text-base leading-relaxed text-muted md:text-lg">
              A short-term SPY terminal for traders who&apos;d rather miss a
              trade than take a bad one.
            </Reveal>

            <Reveal delay={0.26} className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/live">
                <Button variant="primary" size="xl">
                  Launch Terminal
                  <ArrowRight className="h-5 w-5" />
                </Button>
              </Link>
              <Link href="/brief">
                <Button variant="ghost" size="xl">See Today&apos;s Brief</Button>
              </Link>
            </Reveal>

            <Reveal delay={0.32} className="mt-7 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
              <span className="inline-flex items-center gap-1.5 font-bold uppercase tracking-[0.16em] text-green-bright">
                <ShieldCheck className="h-3.5 w-3.5" strokeWidth={3} /> Live data
              </span>
              <span className="font-bold uppercase tracking-[0.16em] text-muted">Hourly candles</span>
              <span className="font-bold uppercase tracking-[0.16em] text-muted">Same-day options</span>
            </Reveal>
          </div>

          {/* Right: animated terminal preview */}
          <Reveal delay={0.18}>
            <div className="relative">
              <span className="absolute -top-3 left-5 z-20 inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2.5 py-1 text-[0.6rem] font-bold uppercase tracking-[0.16em] text-amber backdrop-blur">
                Example session
              </span>
            <SpotlightCard premium tilt className="overflow-hidden">
              {/* Title bar */}
              <div className="flex items-center justify-between gap-4 border-b border-border/70 bg-surface-2/60 px-5 py-3">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-red/70" />
                  <span className="h-2.5 w-2.5 rounded-full bg-amber/70" />
                  <span className="h-2.5 w-2.5 rounded-full bg-green/70" />
                </div>
                <div className="flex items-center gap-2">
                  <span className="live-pulse-dot" aria-hidden />
                  <span className="font-mono text-[0.7rem] tabular text-muted">spyprophet.app/live</span>
                </div>
                <span className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-blue-bright">
                  Terminal
                </span>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-px bg-border/60">
                <div className="bg-surface/80 p-4">
                  <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">SPY · Last</div>
                  <div className="mt-1.5 font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold tabular text-text md:text-3xl">
                    $<AnimatedNumber value={623.41} decimals={2} startDelay={400} />
                  </div>
                  <div className="mt-1 inline-flex items-center gap-1.5 text-[0.78rem] font-bold tabular text-green-bright">
                    ▲ +<AnimatedNumber value={1.04} decimals={2} startDelay={500} />%
                    <span className="font-medium text-muted">today</span>
                  </div>
                </div>
                <div className="bg-surface/80 p-4">
                  <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">VIX</div>
                  <div className="mt-1.5 font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold tabular text-green-bright md:text-3xl">
                    <AnimatedNumber value={14.82} decimals={2} startDelay={500} />
                  </div>
                  <div className="mt-1 text-[0.78rem] font-medium text-muted">Calm regime</div>
                </div>
                <div className="bg-surface/80 p-4">
                  <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">Decision</div>
                  <div className="mt-1.5 font-[family-name:var(--font-space-grotesk)] text-base font-bold leading-tight text-text">
                    Watch upper trigger
                  </div>
                  <div className="mt-1 text-[0.78rem] font-medium text-muted">Live read</div>
                </div>
              </div>

              {/* Chart */}
              <div className="bg-surface/50 p-3 sm:p-4">
                <LiveChart className="h-44 w-full sm:h-56" />
              </div>

              {/* Wait-discipline pills */}
              <div className="flex flex-wrap gap-2 border-t border-border/70 bg-surface-2/40 px-4 py-3">
                <Pill tone="green" size="xs" pulse>Wait gate · clean</Pill>
                <Pill tone="blue" size="xs">Bias · Bullish</Pill>
                <Pill tone="amber" size="xs">Trigger · 624.85</Pill>
                <Pill tone="violet" size="xs">Target · 627.10</Pill>
              </div>
            </SpotlightCard>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Ticker */}
      <Reveal delay={0.1}>
        <TickerTape />
      </Reveal>

      {/* Stats band */}
      <section className="relative z-10 mx-auto w-full max-w-7xl px-6 py-16 md:py-20">
        <StaggerGroup className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border bg-border/60 md:grid-cols-4">
          {[
            { k: "Hourly", v: "candles", note: "Same cadence as the close" },
            { k: "0", v: "delay", note: "Live options quotes" },
            { k: "100%", v: "structure-led", note: "No discretionary trigger naming" },
            { k: "Zero", v: "execution", note: "Decision support, not a broker" },
          ].map((s) => (
            <StaggerItem key={s.k} className="bg-surface/70 p-6 backdrop-blur">
              <div className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tabular text-brand-gradient md:text-4xl">
                {s.k}
              </div>
              <div className="mt-1 text-sm font-bold text-text">{s.v}</div>
              <div className="mt-1 text-xs text-muted">{s.note}</div>
            </StaggerItem>
          ))}
        </StaggerGroup>
      </section>

      {/* Bento features */}
      <section id="features" className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-24">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <Reveal>
            <Pill tone="violet" size="md">
              <Sparkles className="h-3 w-3" strokeWidth={3} />
              What&apos;s inside
            </Pill>
          </Reveal>
          <Reveal delay={0.1} as="h2" className="mt-5 font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-5xl">
            What you get.
          </Reveal>
          <Reveal delay={0.2} as="p" className="mt-4 text-balance text-base text-muted md:text-lg">
            Six purpose-built panels. Every one of them is here to make the
            next decision easier.
          </Reveal>
        </div>

        <StaggerGroup className="grid grid-cols-1 gap-4 md:grid-cols-6">
          {/* Big card 1 — structure */}
          <StaggerItem className="md:col-span-4 md:row-span-2">
            <SpotlightCard className="h-full overflow-hidden">
              <div className="flex h-full flex-col gap-4 p-6">
                <div className="flex items-center gap-3">
                  <BrandMark size={44} animated />
                  <div>
                    <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-blue-bright">Foundation</div>
                    <h3 className="font-[family-name:var(--font-space-grotesk)] text-xl font-bold text-text">Pre-open structure</h3>
                  </div>
                </div>
                <p className="text-sm leading-relaxed text-muted">
                  By 8am the day is drawn. Levels, projections, bias — all
                  ready before the bell. You wake up to a plan, not a blank chart.
                </p>
                <div className="mt-auto rounded-xl border border-border/70 bg-surface-2/40 p-4">
                  <LiveChart className="h-32 w-full" />
                </div>
              </div>
            </SpotlightCard>
          </StaggerItem>

          {/* Card — AI brief */}
          <StaggerItem className="md:col-span-2">
            <SpotlightCard className="h-full overflow-hidden">
              <div className="flex h-full flex-col gap-3 p-6">
                <div className="grid h-11 w-11 place-items-center rounded-xl border border-violet/40 bg-violet/10 text-violet">
                  <Sparkles className="h-5 w-5" strokeWidth={2.5} />
                </div>
                <h3 className="font-[family-name:var(--font-space-grotesk)] text-lg font-bold text-text">Daily Brief</h3>
                <p className="text-sm leading-relaxed text-muted">
                  One screen. The day&apos;s read, the catalysts, the contracts
                  to watch. Skip the thirty-tab morning routine.
                </p>
              </div>
            </SpotlightCard>
          </StaggerItem>

          {/* Card — options */}
          <StaggerItem className="md:col-span-2">
            <SpotlightCard className="h-full overflow-hidden">
              <div className="flex h-full flex-col gap-3 p-6">
                <div className="grid h-11 w-11 place-items-center rounded-xl border border-green/40 bg-green/10 text-green-bright">
                  <Target className="h-5 w-5" strokeWidth={2.5} />
                </div>
                <h3 className="font-[family-name:var(--font-space-grotesk)] text-lg font-bold text-text">Options Cockpit</h3>
                <p className="text-sm leading-relaxed text-muted">
                  Strike, mark, spread, Greeks — all visible before you commit.
                  See the contract before you open the broker tab.
                </p>
              </div>
            </SpotlightCard>
          </StaggerItem>

          {/* Card — Replay */}
          <StaggerItem className="md:col-span-2">
            <SpotlightCard className="h-full overflow-hidden">
              <div className="flex h-full flex-col gap-3 p-6">
                <div className="grid h-11 w-11 place-items-center rounded-xl border border-amber/40 bg-amber/10 text-amber">
                  <History className="h-5 w-5" strokeWidth={2.5} />
                </div>
                <h3 className="font-[family-name:var(--font-space-grotesk)] text-lg font-bold text-text">Replay Lab</h3>
                <p className="text-sm leading-relaxed text-muted">
                  Step yesterday candle-by-candle with future bars masked.
                  Practice the read. Grade the outcome. Sharpen the eye.
                </p>
              </div>
            </SpotlightCard>
          </StaggerItem>

          {/* Card — Journal (wide) */}
          <StaggerItem className="md:col-span-4">
            <SpotlightCard className="h-full overflow-hidden">
              <div className="grid h-full grid-cols-1 gap-4 p-6 md:grid-cols-[auto_1fr]">
                <div className="grid h-11 w-11 place-items-center rounded-xl border border-blue/40 bg-blue/10 text-blue-bright">
                  <BarChart3 className="h-5 w-5" strokeWidth={2.5} />
                </div>
                <div>
                  <h3 className="font-[family-name:var(--font-space-grotesk)] text-lg font-bold text-text">Journal & Analytics</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">
                    Every signal becomes a row. Win rate, R:R, expectancy —
                    your actual edge, not what you remember it to be.
                  </p>
                  <div className="mt-4 grid grid-cols-3 gap-3">
                    {[
                      { l: "Win rate", v: "62%" },
                      { l: "Avg R:R", v: "1.42" },
                      { l: "Expectancy", v: "+$0.38" },
                    ].map((m) => (
                      <div key={m.l} className="rounded-lg border border-border/70 bg-surface-2/40 p-3">
                        <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">
                          {m.l}
                        </div>
                        <div className="mt-0.5 font-[family-name:var(--font-space-grotesk)] text-lg font-bold tabular text-text">
                          {m.v}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </SpotlightCard>
          </StaggerItem>
        </StaggerGroup>
      </section>

      {/* Workflow */}
      <section id="workflow" className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-24">
        <Reveal>
          <SpotlightCard premium tilt={false} className="overflow-hidden p-8 md:p-12">
            <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1.2fr_1fr]">
              <div>
                <Pill tone="green" size="md">
                  <Eye className="h-3 w-3" strokeWidth={3} />
                  Your day
                </Pill>
                <h3 className="mt-5 font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold leading-tight text-text md:text-4xl">
                  One trade-able read per close.
                  <br />
                  <span className="text-bullish-gradient">The rest is patience.</span>
                </h3>
                <p className="mt-5 max-w-xl text-base text-muted md:text-lg">
                  You don&apos;t need to watch every tick. The terminal does
                  that. You show up at key moments and decide.
                </p>
              </div>
              <StaggerGroup className="grid grid-cols-1 gap-3" delayChildren={0.1}>
                {[
                  ["Pre-open", "Day is mapped. Levels, projection, bias — ready before 8:30."],
                  ["First hour", "Catalysts and flow reconciled with structure."],
                  ["Live", "Wait gates show. Green means actionable, amber means stand down."],
                  ["Trigger", "Hourly close confirms. Strike and entry are already on screen."],
                  ["After close", "Outcome graded. Journal updates itself."],
                ].map(([when, what], i) => (
                  <StaggerItem key={when}>
                    <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-surface-2/40 p-3.5">
                      <span className="inline-flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-blue/15 font-mono text-[0.78rem] font-bold tabular text-blue-bright">
                        {i + 1}
                      </span>
                      <div>
                        <div className="text-sm font-bold text-text">{when}</div>
                        <div className="text-xs leading-relaxed text-muted">{what}</div>
                      </div>
                    </div>
                  </StaggerItem>
                ))}
              </StaggerGroup>
            </div>
          </SpotlightCard>
        </Reveal>
      </section>

      {/* Discipline */}
      <section id="safety" className="relative z-10 mx-auto w-full max-w-5xl px-6 pb-24 text-center">
        <Reveal as="h3" className="font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold tracking-tight text-text md:text-3xl">
          Knowing which trades to <span className="text-bullish-gradient">skip</span> is the skill.
        </Reveal>
        <Reveal delay={0.1} as="p" className="mt-4 text-base text-muted md:text-lg">
          SPY Prophet makes that easier.
        </Reveal>
      </section>

      {/* CTA */}
      <section className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-24">
        <Reveal>
          <SpotlightCard premium tilt={false} className="relative overflow-hidden p-12 text-center">
            <div className="absolute inset-x-0 top-0 -z-10 h-full w-full">
              <div className="absolute -top-1/2 left-1/2 h-[120%] w-[120%] -translate-x-1/2 rounded-full bg-blue/20 blur-[120px]" />
            </div>
            <h3 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-5xl">
              See what tomorrow looks like.
            </h3>
            <p className="mx-auto mt-4 max-w-xl text-base text-muted md:text-lg">
              The map is drawn before the bell. Open it.
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
          </SpotlightCard>
        </Reveal>
      </section>

      <footer className="relative z-10 mx-auto w-full max-w-7xl px-6 py-8 text-xs text-muted">
        <div className="flex flex-col items-center gap-3 border-t border-border/70 pt-6 md:flex-row md:justify-between">
          <span className="font-semibold text-text">SPY Prophet</span>
          <span>© {new Date().getFullYear()} · Built for traders who read structure</span>
        </div>
      </footer>
    </div>
  );
}
