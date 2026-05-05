"use client";

import type { ReplayBar, ReplaySession } from "@/lib/api";
import { Pause, Play, SkipBack, SkipForward, StepBack, StepForward } from "lucide-react";
import * as React from "react";

interface ReplayPlayerProps {
  session: ReplaySession;
}

const LINE_COLOR: Record<string, string> = {
  ascending: "#67c2ff",
  descending: "#f5c451",
};

export function ReplayPlayer({ session }: ReplayPlayerProps) {
  const total = session.bars.length;
  const [step, setStep] = React.useState(Math.min(2, total - 1));
  const [playing, setPlaying] = React.useState(false);

  React.useEffect(() => {
    if (!playing) return;
    if (step >= total - 1) {
      setPlaying(false);
      return;
    }
    const id = setTimeout(() => setStep((s) => Math.min(s + 1, total - 1)), 600);
    return () => clearTimeout(id);
  }, [playing, step, total]);

  const visibleBars = session.bars.slice(0, step + 1);
  const currentBar = session.bars[step];

  const lineNames = session.lines.map((l) => l.name);
  const lineKindByName: Record<string, string> = {};
  for (const l of session.lines) lineKindByName[l.name] = l.kind;

  return (
    <div className="flex flex-col gap-4">
      <ReplayChart bars={visibleBars} totalBars={session.bars} lineNames={lineNames} lineKinds={lineKindByName} step={step} />

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-surface-2/50 px-4 py-3">
        <div className="flex items-center gap-2">
          <Btn onClick={() => setStep(0)} aria-label="Reset to first bar">
            <SkipBack className="h-4 w-4" />
          </Btn>
          <Btn onClick={() => setStep((s) => Math.max(0, s - 1))} aria-label="Step back one bar">
            <StepBack className="h-4 w-4" />
          </Btn>
          <Btn
            onClick={() => setPlaying((p) => !p)}
            primary
            aria-label={playing ? "Pause autoplay" : "Start autoplay"}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            <span className="ml-1.5 text-xs">{playing ? "Pause" : "Play"}</span>
          </Btn>
          <Btn onClick={() => setStep((s) => Math.min(total - 1, s + 1))} aria-label="Step forward one bar">
            <StepForward className="h-4 w-4" />
          </Btn>
          <Btn onClick={() => setStep(total - 1)} aria-label="Skip to last bar">
            <SkipForward className="h-4 w-4" />
          </Btn>
        </div>

        <div className="text-sm tabular text-muted">
          Bar {step + 1} of {total}
          {currentBar && (
            <span className="ml-2 font-mono text-xs">
              · {formatTime(currentBar.t)}
            </span>
          )}
        </div>
      </div>

      {currentBar && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Cell label="Close" value={currentBar.c !== null ? `$${currentBar.c.toFixed(2)}` : "—"} />
          <Cell label="High" value={currentBar.h !== null ? `$${currentBar.h.toFixed(2)}` : "—"} />
          <Cell label="Low" value={currentBar.l !== null ? `$${currentBar.l.toFixed(2)}` : "—"} />
          <Cell
            label="Volume"
            value={currentBar.v !== null ? Intl.NumberFormat("en-US").format(Math.round(currentBar.v)) : "—"}
          />
        </div>
      )}

      {currentBar && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Object.entries(currentBar.lines).map(([name, value]) => (
            <Cell
              key={name}
              label={name}
              value={value !== null ? `$${value.toFixed(2)}` : "—"}
              tone={lineKindByName[name] === "descending" ? "amber" : "blue"}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Cell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "amber" | "blue";
}) {
  const tint =
    tone === "amber"
      ? "text-amber"
      : tone === "blue"
        ? "text-blue-bright"
        : "text-text";
  return (
    <div className="rounded-lg border border-border/70 bg-surface/60 p-3">
      <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className={"mt-0.5 font-[family-name:var(--font-space-grotesk)] text-base font-bold tabular " + tint}>
        {value}
      </div>
    </div>
  );
}

function Btn({
  children,
  onClick,
  primary,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "inline-flex h-9 items-center rounded-lg border px-3 text-text transition-colors " +
        (primary
          ? "border-blue/60 bg-blue/15 hover:bg-blue/25"
          : "border-border bg-surface hover:bg-surface-2")
      }
      {...rest}
    >
      {children}
    </button>
  );
}

interface ReplayChartProps {
  bars: ReplayBar[];
  totalBars: ReplayBar[];
  lineNames: string[];
  lineKinds: Record<string, string>;
  step: number;
}

function ReplayChart({ bars, totalBars, lineNames, lineKinds, step }: ReplayChartProps) {
  if (bars.length === 0) return null;

  // Y range across the FULL session (so the axis doesn't jump as you step).
  const allPrices: number[] = [];
  for (const b of totalBars) {
    if (b.h !== null) allPrices.push(b.h);
    if (b.l !== null) allPrices.push(b.l);
    for (const v of Object.values(b.lines)) {
      if (v !== null) allPrices.push(v);
    }
  }
  const minP = Math.min(...allPrices);
  const maxP = Math.max(...allPrices);
  const padP = (maxP - minP) * 0.05 || 1;
  const yMin = minP - padP;
  const yMax = maxP + padP;

  const W = 1200;
  const H = 480;
  const padL = 40;
  const padR = 80;
  const padT = 20;
  const padB = 40;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const totalLen = totalBars.length;
  const xFor = (i: number) => padL + (i / Math.max(totalLen - 1, 1)) * innerW;
  const yFor = (p: number) => padT + innerH - ((p - yMin) / (yMax - yMin)) * innerH;
  const cw = Math.max(2, (innerW / totalLen) * 0.6);

  return (
    <div className="overflow-x-auto rounded-xl border border-border/60 bg-surface-2/30">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Replay session chart"
      >
        {/* y-axis grid */}
        {gridYValues(yMin, yMax, 5).map((p) => (
          <g key={p}>
            <line x1={padL} y1={yFor(p)} x2={W - padR} y2={yFor(p)} stroke="rgba(255,255,255,0.05)" />
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

        {/* mask: dim the future portion of the chart */}
        <rect
          x={xFor(step) + cw / 2}
          y={padT}
          width={Math.max(0, W - padR - (xFor(step) + cw / 2))}
          height={innerH}
          fill="rgba(15,21,28,0.55)"
        />

        {/* structure lines: connect across visible bars only */}
        {lineNames.map((name) => {
          const points: string[] = [];
          for (let i = 0; i <= step; i += 1) {
            const v = totalBars[i].lines[name];
            if (v === null || v === undefined) continue;
            points.push(`${xFor(i)},${yFor(v)}`);
          }
          if (points.length < 2) return null;
          const color = LINE_COLOR[lineKinds[name] ?? ""] ?? "#67c2ff";
          const dash = lineKinds[name] === "ascending" ? "4 6" : "";
          return (
            <polyline
              key={name}
              points={points.join(" ")}
              fill="none"
              stroke={color}
              strokeWidth={1.5}
              strokeDasharray={dash}
              opacity={0.95}
            />
          );
        })}

        {/* candles up to step */}
        {bars.map((b, i) => {
          if (b.o === null || b.h === null || b.l === null || b.c === null) return null;
          const isUp = b.c >= b.o;
          const color = isUp ? "#2ecc71" : "#f45d75";
          const x = xFor(i);
          const bodyTop = yFor(Math.max(b.o, b.c));
          const bodyHeight = Math.max(1, Math.abs(yFor(b.o) - yFor(b.c)));
          return (
            <g key={b.t}>
              <line x1={x} x2={x} y1={yFor(b.h)} y2={yFor(b.l)} stroke={color} strokeWidth={1} opacity={0.85} />
              <rect x={x - cw / 2} y={bodyTop} width={cw} height={bodyHeight} fill={color} opacity={0.95} rx={1} />
            </g>
          );
        })}

        {/* line labels at the right edge */}
        {lineNames.map((name) => {
          const v = totalBars[step].lines[name];
          if (v === null || v === undefined) return null;
          const color = LINE_COLOR[lineKinds[name] ?? ""] ?? "#67c2ff";
          return (
            <text
              key={name}
              x={W - padR + 6}
              y={yFor(v) - 4}
              fontSize={10}
              fontWeight={700}
              fill={color}
              fontFamily="JetBrains Mono, monospace"
            >
              {name} {v.toFixed(2)}
            </text>
          );
        })}

        {/* current step marker */}
        <line
          x1={xFor(step)}
          x2={xFor(step)}
          y1={padT}
          y2={H - padB}
          stroke="rgba(167,139,250,0.7)"
          strokeWidth={1}
          strokeDasharray="3 5"
        />
      </svg>
    </div>
  );
}

function gridYValues(min: number, max: number, count: number): number[] {
  const out: number[] = [];
  for (let i = 0; i <= count; i += 1) {
    out.push(min + ((max - min) * i) / count);
  }
  return out;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  } catch {
    return iso;
  }
}
