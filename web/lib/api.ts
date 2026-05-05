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

export interface ChainStrike {
  strike: number;
  call_symbol: string | null;
  put_symbol: string | null;
  call_streamer_symbol: string | null;
  put_streamer_symbol: string | null;
}

export interface OptionsChain {
  underlying: string;
  expiration: string;
  spot_price: number | null;
  strikes: ChainStrike[];
}

export async function getOptionsChain(
  expiration?: string,
  width = 10
): Promise<OptionsChain | { error: string; status: number } | null> {
  try {
    const params = new URLSearchParams();
    if (expiration) params.set("expiration", expiration);
    params.set("width", String(width));
    const res = await fetch(`${API_BASE_URL}/api/options/spy?${params.toString()}`, {
      next: { revalidate: 60, tags: ["options"] },
    });
    if (!res.ok) {
      const body = await res.text();
      return { error: body || res.statusText, status: res.status };
    }
    return (await res.json()) as OptionsChain;
  } catch (e) {
    return { error: e instanceof Error ? e.message : String(e), status: 0 };
  }
}

export interface OptionQuote {
  symbol: string;
  underlying: string;
  expiration: string | null;
  strike: number;
  option_type: "CALL" | "PUT";
  bid: number | null;
  ask: number | null;
  mark: number | null;
  spread: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  iv: number | null;
  provider: string;
  warning?: string | null;
}

export interface QuotePairResponse {
  underlying: string;
  underlying_price: number | null;
  expiration: string;
  call: OptionQuote | null;
  put: OptionQuote | null;
  provider_status: Record<string, unknown>;
  warning: string | null;
}

export async function getStrikeQuotes(
  callStrike: number,
  putStrike: number,
  expiration?: string
): Promise<QuotePairResponse | null> {
  try {
    const params = new URLSearchParams();
    if (expiration) params.set("expiration", expiration);
    params.set("call_strike", String(callStrike));
    params.set("put_strike", String(putStrike));
    const res = await fetch(`${API_BASE_URL}/api/quotes/spy?${params.toString()}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as QuotePairResponse;
  } catch {
    return null;
  }
}
