import { cn } from "@/lib/cn";
import { ArrowDown, ArrowUp, Minus, Pause, type LucideIcon } from "lucide-react";

type Direction = "call" | "put" | "wait" | "neutral";

const map: Record<
  Direction,
  { Icon: LucideIcon; tint: string; label: string }
> = {
  call: { Icon: ArrowUp, tint: "text-green-bright bg-green/10 border-green/40", label: "Call" },
  put: { Icon: ArrowDown, tint: "text-red-bright bg-red/10 border-red/40", label: "Put" },
  wait: { Icon: Pause, tint: "text-amber bg-amber/10 border-amber/40", label: "Wait" },
  neutral: { Icon: Minus, tint: "text-blue-bright bg-blue/10 border-blue/40", label: "Neutral" },
};

export function DirectionGlyph({
  direction,
  label,
  size = "md",
  className,
}: {
  direction: Direction;
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const { Icon, tint, label: defaultLabel } = map[direction];
  const sizeMap = {
    sm: { wrap: "h-7 px-2.5 text-xs gap-1.5", icon: "h-3.5 w-3.5" },
    md: { wrap: "h-8 px-3 text-sm gap-2", icon: "h-4 w-4" },
    lg: { wrap: "h-10 px-4 text-base gap-2.5", icon: "h-5 w-5" },
  };
  return (
    <span
      role="img"
      aria-label={label || defaultLabel}
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full border font-bold tracking-tight",
        sizeMap[size].wrap,
        tint,
        className,
      )}
    >
      <Icon className={cn(sizeMap[size].icon, "shrink-0")} strokeWidth={3} aria-hidden />
      <span className="leading-none">{label || defaultLabel}</span>
    </span>
  );
}
