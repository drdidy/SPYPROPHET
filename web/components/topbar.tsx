"use client";

import { MobileNav } from "@/components/mobile-nav";
import { Pill } from "@/components/ui/pill";
import { Bell, RefreshCw, Settings2 } from "lucide-react";
import { useEffect, useState } from "react";

export function Topbar() {
  const [now, setNow] = useState<Date>(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Naive market-hours read for the header. Real status comes from the API later.
  const day = now.getDay();
  const ct = new Date(now.toLocaleString("en-US", { timeZone: "America/Chicago" }));
  const minutes = ct.getHours() * 60 + ct.getMinutes();
  const isWeekday = day >= 1 && day <= 5;
  const isLive = isWeekday && minutes >= 8 * 60 + 30 && minutes <= 15 * 60;
  const isPre = isWeekday && minutes < 8 * 60 + 30;
  const sessionTone = isLive ? "live" : isPre ? "amber" : "neutral";
  const sessionLabel = isLive ? "Market Live" : isPre ? "Pre-market" : "Market Closed";

  return (
    <header className="sticky top-0 z-40 flex h-16 flex-shrink-0 items-center justify-between gap-4 border-b border-border/70 bg-surface/60 px-4 lg:px-8 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <MobileNav />
        <Pill tone={sessionTone as "live" | "amber" | "neutral"} pulse={isLive} size="sm">
          {sessionLabel}
        </Pill>
        <span className="hidden md:inline-flex items-center gap-1.5 text-[0.7rem] font-mono tabular text-muted">
          {ct.toLocaleString("en-US", {
            weekday: "short",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
            timeZone: "America/Chicago",
          })}{" "}
          CT
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          aria-label="Refresh data"
          className="hidden md:inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border/70 bg-white/[0.02] text-muted hover:text-text hover:border-blue/40 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
        <button
          aria-label="Notifications"
          className="hidden md:inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border/70 bg-white/[0.02] text-muted hover:text-text hover:border-blue/40 transition-colors"
        >
          <Bell className="h-4 w-4" />
        </button>
        <button
          aria-label="Settings"
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border/70 bg-white/[0.02] text-muted hover:text-text hover:border-blue/40 transition-colors"
        >
          <Settings2 className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
