"use client";

import { BrandMark } from "@/components/brand-mark";
import { cn } from "@/lib/cn";
import {
  Activity,
  BarChart3,
  BookOpen,
  History,
  LineChart,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/live", label: "Live", icon: Activity, hint: "Today's structure & active signals" },
  { href: "/foresight", label: "Foresight", icon: Sparkles, hint: "Pre-session structure plan" },
  { href: "/brief", label: "Daily Brief", icon: BookOpen, hint: "Trader-focused day-ahead read" },
  { href: "/chart", label: "Chart", icon: LineChart, hint: "Decision map & candles" },
  { href: "/replay", label: "Replay", icon: History, hint: "Step through prior sessions" },
  { href: "/options", label: "Options", icon: Target, hint: "Contract cockpit" },
  { href: "/journal", label: "Journal", icon: BarChart3, hint: "Outcome analytics" },
];

export function NavRail() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen w-[260px] flex-shrink-0 flex-col border-r border-border/70 bg-surface/40 backdrop-blur-xl lg:flex">
      <div className="flex h-20 items-center gap-3 border-b border-border/70 px-5">
        <Link href="/" className="group inline-flex items-center gap-2.5">
          <BrandMark size={42} animated={false} />
          <span className="flex flex-col leading-none">
            <span className="font-[family-name:var(--font-space-grotesk)] text-base font-extrabold tracking-tight text-text">
              SPY Prophet
            </span>
            <span className="mt-1 text-[0.62rem] font-bold uppercase tracking-[0.22em] text-blue-bright/85">
              Terminal
            </span>
          </span>
        </Link>
      </div>
      <nav className="flex-1 overflow-y-auto p-3" aria-label="Primary">
        <ul className="space-y-1">
          {NAV.map(({ href, label, icon: Icon, hint }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={cn(
                    "group relative flex items-start gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200",
                    active
                      ? "bg-gradient-to-r from-blue/15 via-blue/5 to-transparent text-text shadow-[inset_0_0_0_1px_rgba(78,168,222,0.3)]"
                      : "text-muted hover:bg-white/[0.03] hover:text-text",
                  )}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 h-7 w-[3px] rounded-r bg-gradient-to-b from-blue to-green" aria-hidden />
                  )}
                  <Icon
                    className={cn(
                      "mt-0.5 h-4 w-4 flex-shrink-0 transition-colors",
                      active ? "text-blue-bright" : "text-muted group-hover:text-text",
                    )}
                    strokeWidth={2.4}
                  />
                  <div className="flex min-w-0 flex-col">
                    <span className="font-semibold leading-tight">{label}</span>
                    <span className="mt-0.5 text-[0.7rem] leading-tight text-muted line-clamp-1">{hint}</span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="border-t border-border/70 p-3">
        <div className="rounded-xl border border-border/70 bg-surface-2/60 p-3 text-[0.7rem] text-muted">
          <div className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.1em] text-green-bright">
            <span className="live-pulse-dot" aria-hidden />
            <span>Live data</span>
          </div>
          <p className="mt-1.5 leading-snug">
            Hourly candles · US/Central display
          </p>
        </div>
      </div>
    </aside>
  );
}
