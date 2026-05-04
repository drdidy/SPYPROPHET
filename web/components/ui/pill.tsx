import { cn } from "@/lib/cn";
import * as React from "react";

type Tone = "neutral" | "blue" | "green" | "red" | "amber" | "violet" | "live";

const toneMap: Record<Tone, string> = {
  neutral: "border-border bg-white/[0.03] text-muted",
  blue: "border-blue/40 bg-blue/10 text-blue-bright",
  green: "border-green/40 bg-green/10 text-green-bright",
  red: "border-red/40 bg-red/10 text-red-bright",
  amber: "border-amber/40 bg-amber/10 text-amber",
  violet: "border-violet/40 bg-violet/10 text-violet",
  live: "border-green/50 bg-green/10 text-green-bright",
};

interface PillProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  pulse?: boolean;
  size?: "xs" | "sm" | "md";
}

export function Pill({ tone = "neutral", pulse = false, size = "sm", className, children, ...props }: PillProps) {
  const sizeMap = {
    xs: "text-[0.62rem] px-2 py-[2px]",
    sm: "text-[0.7rem] px-2.5 py-1",
    md: "text-xs px-3 py-1.5",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-bold uppercase tracking-[0.08em]",
        sizeMap[size],
        toneMap[tone],
        className,
      )}
      {...props}
    >
      {pulse && <span className="live-pulse-dot" aria-hidden />}
      {children}
    </span>
  );
}
