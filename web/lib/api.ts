/**
 * Thin client for the SPY Prophet FastAPI service.
 *
 * Reads the base URL from NEXT_PUBLIC_API_URL. Falls back to localhost in
 * dev so `next dev` works without env config. All fetches are server-side
 * (used from Server Components) and tagged for revalidation.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

const DEFAULT_REVALIDATE_SECONDS = 30;

export interface SpotSnapshot {
  price: number | null;
  change: number | null;
  change_pct: number | null;
}

export interface VixSnapshot {
  value: number | null;
  regime: string | null;
  regime_tone: "green" | "amber" | "red" | null;
}

export interface WatchStrikes {
  call: number | null;
  put: number | null;
}

export interface LiveSnapshot {
  spot: SpotSnapshot;
  vix: VixSnapshot;
  watch: WatchStrikes;
  decision_label: string;
  last_update: string;
  bias: { label: string; direction: "call" | "put" | "neutral"; score?: number } | null;
  signal: { label: string; direction: "call" | "put"; line: string } | null;
  trigger: { name: string; value: number; distance: number } | null;
  target: { name: string; value: number; rr: number } | null;
  stop: number | null;
  guardrails: Array<{ label: string; state: string; tone: "green" | "amber" | "red" }> | null;
  intel: Array<{ label: string; value: string; body: string; tone: "green" | "amber" | "blue" }> | null;
}

export async function getLiveSnapshot(): Promise<LiveSnapshot | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/live`, {
      next: { revalidate: DEFAULT_REVALIDATE_SECONDS, tags: ["live"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as LiveSnapshot;
  } catch {
    return null;
  }
}
