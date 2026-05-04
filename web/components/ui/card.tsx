import { cn } from "@/lib/cn";
import * as React from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glow?: "blue" | "green" | "red" | "amber" | "violet" | "none";
  premium?: boolean;
  hoverable?: boolean;
}

export function Card({ className, glow = "none", premium = false, hoverable = false, children, ...props }: CardProps) {
  const glowMap: Record<string, string> = {
    blue: "shadow-[0_0_0_1px_rgba(78,168,222,0.32),0_18px_60px_-10px_rgba(78,168,222,0.35)]",
    green: "shadow-[0_0_0_1px_rgba(46,204,113,0.32),0_18px_60px_-10px_rgba(46,204,113,0.35)]",
    red: "shadow-[0_0_0_1px_rgba(244,93,117,0.32),0_18px_60px_-10px_rgba(244,93,117,0.35)]",
    amber: "shadow-[0_0_0_1px_rgba(245,196,81,0.32),0_18px_60px_-10px_rgba(245,196,81,0.35)]",
    violet: "shadow-[0_0_0_1px_rgba(167,139,250,0.32),0_18px_60px_-10px_rgba(167,139,250,0.35)]",
    none: "",
  };
  return (
    <div
      className={cn(
        "relative rounded-2xl border border-border bg-surface/70 backdrop-blur-md",
        premium && "premium-border",
        hoverable && "transition-transform duration-300 hover:-translate-y-1",
        glowMap[glow],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-start justify-between gap-4 p-5 pb-3", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-base font-bold leading-tight text-text font-[family-name:var(--font-display)]", className)}
      {...props}
    />
  );
}

export function CardKicker({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "text-[0.66rem] font-bold uppercase tracking-[0.16em] text-blue",
        className,
      )}
      {...props}
    />
  );
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5", className)} {...props} />;
}

export function CardFoot({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border-t border-border/60 px-5 py-3 text-xs text-muted", className)} {...props} />;
}
