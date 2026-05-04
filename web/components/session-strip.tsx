"use client";

import { useEffect, useState } from "react";

type Session = {
  label: string;
  state: "live" | "pre" | "post" | "closed";
  copy: string;
};

function deriveSession(now: Date): Session {
  // CT clock derivation
  const ct = new Date(now.toLocaleString("en-US", { timeZone: "America/Chicago" }));
  const day = ct.getDay(); // Sun=0..Sat=6
  const minutes = ct.getHours() * 60 + ct.getMinutes();
  const isWeekday = day >= 1 && day <= 5;
  if (!isWeekday) {
    return { label: "Markets · Closed", state: "closed", copy: "Weekend — next session opens Monday 8:30 CT" };
  }
  if (minutes < 7 * 60) {
    return { label: "Markets · Pre-session", state: "pre", copy: "Map drawing · Open at 8:30 CT" };
  }
  if (minutes < 8 * 60 + 30) {
    return { label: "Markets · Pre-open", state: "pre", copy: "Brief ready · Cash open at 8:30 CT" };
  }
  if (minutes <= 15 * 60) {
    return { label: "Markets · Live", state: "live", copy: "Hourly closes · Wait gates active" };
  }
  return { label: "Markets · After hours", state: "post", copy: "Outcome graded · Journal updated" };
}

export function SessionStrip() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  // SSR / first-paint stays empty so we don't ship a hydration mismatch.
  if (!now) {
    return <div className="h-14 border-y border-border/60 bg-surface/40" aria-hidden />;
  }

  const session = deriveSession(now);
  const dot =
    session.state === "live"
      ? "bg-green shadow-[0_0_0_4px_rgba(46,204,113,0.18)] animate-pulse"
      : session.state === "pre"
        ? "bg-amber shadow-[0_0_0_4px_rgba(245,196,81,0.18)]"
        : session.state === "post"
          ? "bg-blue shadow-[0_0_0_4px_rgba(78,168,222,0.18)]"
          : "bg-muted";

  const ctTime = now.toLocaleTimeString("en-US", {
    timeZone: "America/Chicago",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const etTime = now.toLocaleTimeString("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return (
    <div
      className="relative overflow-hidden border-y border-border/60 bg-surface/40 backdrop-blur"
      role="status"
      aria-live="polite"
    >
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-3 text-sm">
        <div className="flex items-center gap-3">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${dot}`} aria-hidden />
          <span className="font-bold uppercase tracking-[0.14em] text-text">
            {session.label}
          </span>
          <span className="hidden sm:inline text-muted">·</span>
          <span className="hidden sm:inline text-muted">{session.copy}</span>
        </div>
        <div className="flex items-center gap-4 font-mono text-xs tabular text-muted">
          <span>
            <span className="text-text">{ctTime}</span> CT
          </span>
          <span>·</span>
          <span>
            <span className="text-text">{etTime}</span> ET
          </span>
        </div>
      </div>
    </div>
  );
}
