import { Reveal, StaggerGroup, StaggerItem } from "@/components/reveal";
import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { getStructure, type StructureLine, type StructureProjection } from "@/lib/api";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

export const revalidate = 60;

export default async function ForesightPage() {
  const projection = await getStructure();

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <CardKicker className="mb-1.5 flex items-center gap-2">
              <Sparkles className="h-3 w-3" strokeWidth={3} /> Foresight
            </CardKicker>
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
              Pre-session structure plan.
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">
              Today&apos;s four primary lines projected from the prior
              session pivots. Descending lines are the active triggers;
              ascending lines are intermediate targets.
            </p>
          </div>
          {projection && (
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone="blue">Pivots · {projection.pivot_session}</Pill>
              <Pill tone="violet">As of {fmtTime(projection.as_of)}</Pill>
            </div>
          )}
        </div>
      </Reveal>

      {!projection ? (
        <Reveal>
          <Card className="border-amber/30 bg-amber/[0.05]">
            <CardBody>
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber" strokeWidth={2} />
                <div>
                  <div className="text-sm font-bold text-amber">Structure projection unavailable</div>
                  <p className="mt-1 max-w-2xl text-xs text-muted">
                    Hourly data fetch failed. The API will retry on the
                    next request — page revalidates every 60 seconds.
                  </p>
                </div>
              </div>
            </CardBody>
          </Card>
        </Reveal>
      ) : (
        <>
          <Reveal delay={0.1}>
            <ActiveLinesStrip projection={projection} />
          </Reveal>

          <Reveal delay={0.2}>
            <Card hoverable className="overflow-hidden">
              <CardHeader>
                <div>
                  <CardKicker className="flex items-center gap-2">
                    <Target className="h-3 w-3" strokeWidth={3} /> Primary lines
                  </CardKicker>
                  <CardTitle className="mt-1.5">Four anchors, projected to now</CardTitle>
                </div>
                <Pill tone="green">Slope 0.20/hr</Pill>
              </CardHeader>
              <CardBody>
                <LinesTable lines={projection.lines} />
              </CardBody>
            </Card>
          </Reveal>

          <Reveal delay={0.3}>
            <Card>
              <CardHeader>
                <div>
                  <CardKicker>How this gets built</CardKicker>
                  <CardTitle className="mt-1.5">Methodology</CardTitle>
                </div>
              </CardHeader>
              <CardBody>
                <ol className="grid grid-cols-1 gap-3 text-sm leading-relaxed text-muted md:grid-cols-2">
                  {[
                    "High pivot = highest High of yesterday's RTH (08:30–15:00 CT)",
                    "Low pivot = lowest Low of the same window",
                    "From the high pivot: UA (ascending +) and UD (descending −)",
                    "From the low pivot: LA (ascending +) and LD (descending −)",
                    "Each line projects forward: anchor + slope × hours_since",
                    "Trigger = closest descending line; target = nearest line on the opposite side",
                  ].map((step, i) => (
                    <li key={step} className="flex items-start gap-3 rounded-xl border border-border/70 bg-surface-2/40 p-3.5">
                      <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue/15 text-[0.62rem] font-bold tabular text-blue-bright">
                        {i + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              </CardBody>
            </Card>
          </Reveal>
        </>
      )}
    </div>
  );
}

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function ActiveLinesStrip({ projection }: { projection: StructureProjection }) {
  const triggerAbove = projection.closest_descending_above;
  const triggerBelow = projection.closest_descending_below;

  const cards = [
    {
      side: "PUT setup",
      tone: "red",
      icon: TrendingDown,
      line: triggerAbove,
      caption: triggerAbove
        ? "Closest descending line above spot — rejection from above triggers a PUT signal."
        : "No descending line above spot in the projection window.",
    },
    {
      side: "CALL setup",
      tone: "green",
      icon: TrendingUp,
      line: triggerBelow,
      caption: triggerBelow
        ? "Closest descending line below spot — rejection from below triggers a CALL signal."
        : "No descending line below spot in the projection window.",
    },
  ] as const;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {cards.map((c) => (
        <Card
          key={c.side}
          glow={c.tone === "green" ? "green" : "red"}
          className="overflow-hidden"
        >
          <CardBody>
            <div className="flex items-start gap-3">
              <div
                className={
                  "grid h-10 w-10 flex-shrink-0 place-items-center rounded-xl border " +
                  (c.tone === "green"
                    ? "border-green/40 bg-green/10 text-green-bright"
                    : "border-red/40 bg-red/10 text-red-bright")
                }
              >
                <c.icon className="h-5 w-5" strokeWidth={2.5} />
              </div>
              <div className="flex-1">
                <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">
                  {c.side}
                </div>
                {c.line ? (
                  <>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className={"font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tabular " + (c.tone === "green" ? "text-green-bright" : "text-red-bright")}>
                        ${c.line.projected_value.toFixed(2)}
                      </span>
                      <span className="text-sm text-muted">
                        {c.line.label ?? c.line.name}
                      </span>
                    </div>
                    {c.line.distance !== null && (
                      <div className="mt-1 text-[0.78rem] font-medium text-muted">
                        {c.line.distance > 0 ? "+" : ""}
                        {c.line.distance.toFixed(2)} from spot
                      </div>
                    )}
                  </>
                ) : (
                  <div className="mt-1 text-base text-muted">No active line on this side</div>
                )}
                <p className="mt-2 text-xs leading-relaxed text-muted">
                  {c.caption}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

function LinesTable({ lines }: { lines: StructureLine[] }) {
  const sorted = [...lines].sort((a, b) => b.projected_value - a.projected_value);

  return (
    <div className="overflow-hidden rounded-xl border border-border/70">
      <div className="grid grid-cols-[2fr_1fr_1fr_1fr] gap-px bg-border/60 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">
        <div className="bg-surface-2/60 px-4 py-3">Line</div>
        <div className="bg-surface-2/60 px-4 py-3 text-right">Projected</div>
        <div className="bg-surface-2/60 px-4 py-3 text-right">Distance</div>
        <div className="bg-surface-2/60 px-4 py-3">Role</div>
      </div>
      <StaggerGroup className="divide-y divide-border/50" delayChildren={0.05}>
        {sorted.map((row) => {
          const isDescending = row.kind === "descending";
          const dist = row.distance ?? 0;
          const isAbove = dist > 0;
          return (
            <StaggerItem key={row.name}>
              <div className="grid grid-cols-[2fr_1fr_1fr_1fr] items-center bg-surface/40 transition-colors hover:bg-surface-2/40">
                <div className="px-4 py-3">
                  <div className="font-mono text-sm tabular text-text">
                    {row.label ?? row.name}
                  </div>
                  <div className="mt-0.5 text-[0.62rem] uppercase tracking-[0.14em] text-muted">
                    {row.kind}
                  </div>
                </div>
                <div className="px-4 py-3 text-right font-[family-name:var(--font-space-grotesk)] text-base font-bold tabular text-text">
                  ${row.projected_value.toFixed(2)}
                </div>
                <div className="px-4 py-3 text-right">
                  <span
                    className={
                      "inline-flex items-center gap-0.5 text-xs font-bold tabular " +
                      (isAbove ? "text-green-bright" : "text-red-bright")
                    }
                  >
                    {isAbove ? (
                      <ArrowUpRight className="h-3 w-3" strokeWidth={2.5} />
                    ) : (
                      <ArrowDownRight className="h-3 w-3" strokeWidth={2.5} />
                    )}
                    {Math.abs(dist).toFixed(2)}
                  </span>
                </div>
                <div className="px-4 py-3">
                  {isDescending ? (
                    <Pill tone="amber" size="xs">Trigger</Pill>
                  ) : (
                    <Pill tone="blue" size="xs">Target</Pill>
                  )}
                </div>
              </div>
            </StaggerItem>
          );
        })}
      </StaggerGroup>
    </div>
  );
}
