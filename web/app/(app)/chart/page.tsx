import { Reveal } from "@/components/reveal";
import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { getChart, type CandleBar, type ChartResponse, type StructureLine } from "@/lib/api";
import { AlertTriangle, LineChart as LineChartIcon } from "lucide-react";

export const revalidate = 60;

export default async function ChartPage() {
  const data = await getChart("5d");
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <CardKicker className="mb-1.5 flex items-center gap-2">
              <LineChartIcon className="h-3 w-3" strokeWidth={3} /> Chart
            </CardKicker>
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
              Decision map & candles.
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">
              Hourly SPY candles with the four primary structure lines
              projected on top. Yellow = descending (triggers), blue =
              ascending (intermediate / targets).
            </p>
          </div>
          {data && data.spot_price !== null && (
            <Pill tone="violet">SPY ${data.spot_price.toFixed(2)}</Pill>
          )}
        </div>
      </Reveal>

      {!data || data.bars.length === 0 ? (
        <Reveal>
          <Card className="border-amber/30 bg-amber/[0.05]">
            <CardBody>
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber" strokeWidth={2} />
                <div>
                  <div className="text-sm font-bold text-amber">Chart data unavailable</div>
                  <p className="mt-1 max-w-2xl text-xs text-muted">
                    Hourly bars failed to load. Page revalidates every 60 seconds.
                  </p>
                </div>
              </div>
            </CardBody>
          </Card>
        </Reveal>
      ) : (
        <Reveal delay={0.1}>
          <Card hoverable className="overflow-hidden">
            <CardHeader>
              <div>
                <CardKicker>Decision map</CardKicker>
                <CardTitle className="mt-1.5">
                  {data.bars.length} hourly bars · {data.period}
                </CardTitle>
              </div>
              <Pill tone="green">Auto-refresh 60s</Pill>
            </CardHeader>
            <CardBody>
              <CandleSvg data={data} />
              <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted">
                <LegendDot tone="green" label="Bullish candle" />
                <LegendDot tone="red" label="Bearish candle" />
                <LegendDot tone="amber" label="Descending line (trigger)" />
                <LegendDot tone="blue" label="Ascending line (target)" />
                <LegendDot tone="violet" label="Spot" />
              </div>
            </CardBody>
          </Card>
        </Reveal>
      )}
    </div>
  );
}

function LegendDot({ tone, label }: { tone: "green" | "red" | "amber" | "blue" | "violet"; label: string }) {
  const colorMap: Record<typeof tone, string> = {
    green: "bg-green",
    red: "bg-red",
    amber: "bg-amber",
    blue: "bg-blue",
    violet: "bg-violet",
  };
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2.5 w-2.5 rounded-full ${colorMap[tone]}`} aria-hidden />
      <span>{label}</span>
    </span>
  );
}

function CandleSvg({ data }: { data: ChartResponse }) {
  const bars = data.bars.filter((b) => b.o !== null && b.h !== null && b.l !== null && b.c !== null);
  if (bars.length === 0) return null;

  const lines = data.structure?.lines ?? [];
  const spot = data.spot_price;

  // Y range: include candles + projected line values + spot
  const allPrices: number[] = [];
  for (const b of bars) {
    allPrices.push(b.h as number, b.l as number);
  }
  for (const l of lines) {
    if (typeof l.projected_value === "number") allPrices.push(l.projected_value);
  }
  if (typeof spot === "number") allPrices.push(spot);

  const minP = Math.min(...allPrices);
  const maxP = Math.max(...allPrices);
  const padP = (maxP - minP) * 0.05 || 1;
  const yMin = minP - padP;
  const yMax = maxP + padP;

  const W = 1200;
  const H = 480;
  const padL = 40;
  const padR = 60;
  const padT = 20;
  const padB = 40;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const xFor = (i: number) => padL + (i / Math.max(bars.length - 1, 1)) * innerW;
  const yFor = (p: number) =>
    padT + innerH - ((p - yMin) / (yMax - yMin)) * innerH;

  // Candle width
  const cw = Math.max(2, (innerW / bars.length) * 0.6);

  // Project lines through the bar timeline using the line's slope.
  // We approximate by using the projected_value as the value at the
  // last bar and extrapolating backwards using the line's slope. Since
  // the API doesn't return slope directly, we draw a horizontal line
  // at the projected_value as a flat overlay — close enough for a
  // visual reference. (Real per-bar projection comes when the API
  // exposes per-bar values for each line.)
  const horizontalLineFor = (val: number) => {
    const y = yFor(val);
    return { y, d: `M ${padL} ${y} L ${W - padR} ${y}` };
  };

  const lineColor = (kind: string) => (kind === "descending" ? "#f5c451" : "#67c2ff");
  const lineDash = (kind: string) => (kind === "descending" ? "" : "4 6");

  const lastTimes = bars.map((b) => formatBarLabel(b.t));
  const xTicks = pickTickIndices(bars.length, 6);

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="SPY hourly candles with structure overlay"
      >
        {/* horizontal price grid */}
        {gridYValues(yMin, yMax, 5).map((p) => (
          <g key={p}>
            <line
              x1={padL}
              y1={yFor(p)}
              x2={W - padR}
              y2={yFor(p)}
              stroke="rgba(255,255,255,0.05)"
            />
            <text
              x={W - padR + 6}
              y={yFor(p) + 3}
              fontSize={10}
              fill="rgba(255,255,255,0.45)"
              fontFamily="JetBrains Mono, monospace"
            >
              {p.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Candles */}
        {bars.map((b, i) => {
          const o = b.o as number;
          const h = b.h as number;
          const l = b.l as number;
          const c = b.c as number;
          const isUp = c >= o;
          const color = isUp ? "#2ecc71" : "#f45d75";
          const bodyTop = yFor(Math.max(o, c));
          const bodyHeight = Math.max(1, Math.abs(yFor(o) - yFor(c)));
          const x = xFor(i);
          return (
            <g key={b.t}>
              <line
                x1={x}
                x2={x}
                y1={yFor(h)}
                y2={yFor(l)}
                stroke={color}
                strokeWidth={1}
                opacity={0.85}
              />
              <rect
                x={x - cw / 2}
                y={bodyTop}
                width={cw}
                height={bodyHeight}
                fill={color}
                opacity={0.95}
                rx={1}
              />
            </g>
          );
        })}

        {/* Structure lines (drawn flat at projected_value — see note above) */}
        {lines.map((line: StructureLine) => {
          const { d } = horizontalLineFor(line.projected_value);
          return (
            <g key={line.name}>
              <path
                d={d}
                stroke={lineColor(line.kind)}
                strokeWidth={1.5}
                strokeDasharray={lineDash(line.kind)}
                fill="none"
                opacity={0.9}
              />
              <text
                x={W - padR - 4}
                y={yFor(line.projected_value) - 4}
                fontSize={10}
                fontWeight={700}
                textAnchor="end"
                fill={lineColor(line.kind)}
                fontFamily="JetBrains Mono, monospace"
              >
                {line.name} {line.projected_value.toFixed(2)}
              </text>
            </g>
          );
        })}

        {/* Spot line */}
        {typeof spot === "number" && (
          <g>
            <line
              x1={padL}
              y1={yFor(spot)}
              x2={W - padR}
              y2={yFor(spot)}
              stroke="#a78bfa"
              strokeWidth={1.5}
              strokeDasharray="2 4"
              opacity={0.85}
            />
            <text
              x={padL + 4}
              y={yFor(spot) - 4}
              fontSize={10}
              fontWeight={700}
              fill="#a78bfa"
              fontFamily="JetBrains Mono, monospace"
            >
              SPOT {spot.toFixed(2)}
            </text>
          </g>
        )}

        {/* x-axis labels */}
        {xTicks.map((i) => (
          <text
            key={i}
            x={xFor(i)}
            y={H - padB + 18}
            fontSize={10}
            fill="rgba(255,255,255,0.45)"
            textAnchor="middle"
            fontFamily="JetBrains Mono, monospace"
          >
            {lastTimes[i]}
          </text>
        ))}
      </svg>
    </div>
  );
}

function formatBarLabel(iso: string): string {
  try {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()} ${d
      .getHours()
      .toString()
      .padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  } catch {
    return iso;
  }
}

function pickTickIndices(n: number, count: number): number[] {
  if (n <= count) return [...Array(n).keys()];
  const step = Math.floor(n / (count - 1));
  const out = [];
  for (let i = 0; i < count - 1; i += 1) out.push(i * step);
  out.push(n - 1);
  return out;
}

function gridYValues(min: number, max: number, count: number): number[] {
  const out: number[] = [];
  for (let i = 0; i <= count; i += 1) {
    out.push(min + ((max - min) * i) / count);
  }
  return out;
}

// CandleBar import is currently used only for typing in helper functions.
// Keep the type import explicit.
export type _CandleBarType = CandleBar;
