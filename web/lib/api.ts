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
  bias: {
    label: string;
    direction: "call" | "put" | "neutral";
    code?: string;
    explanation?: string;
    score?: number;
    primary_line?: string | null;
    take_profit_line?: string | null;
  } | null;
  signal: {
    label: string;
    direction: "call" | "put";
    line: string;
    status?: string;
    signal_id?: string;
    explanation?: string;
    rejection_time?: string;
    rr_ratio?: number | null;
  } | null;
  trigger: {
    name: string;
    value: number;
    distance: number;
    line_code?: string;
    setup?: "CALL" | "PUT";
    kind?: string;
  } | null;
  target: {
    name: string;
    value: number;
    rr: number | null;
    line_code?: string;
    distance?: number;
    kind?: string;
  } | null;
  stop: number | null;
  guardrails: Array<{
    label: string;
    state: string;
    tone: "green" | "amber" | "red";
  }> | null;
  intel: Array<{
    label: string;
    value: string;
    body: string;
    tone: "green" | "amber" | "blue";
  }> | null;
  decision: {
    final_decision: string | null;
    explanation: string | null;
    grade: string | null;
    action_label: string | null;
  } | null;
  grade: string | null;
  action: string | null;
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

export interface JournalEntry {
  journal_id: string;
  created_at: string;
  trade_date: string | null;
  source: string;
  signal_id: string | null;
  signal_type: string | null;
  signal_status: string | null;
  line_name: string | null;
  line_zone_type: string | null;
  bias: string | null;
  quality_grade: string | null;
  quality_score: number;
  final_decision: string | null;
  action_label: string | null;
  entry_time: string | null;
  entry_price: number;
  stop_price: number;
  target_line_name: string | null;
  target_price: number;
  rr_ratio: number;
  outcome: string | null;
  outcome_time: string | null;
  max_favorable_move: number;
  max_adverse_move: number;
  bars_to_outcome: number | null;
  selected_option_type: string | null;
  selected_option_strike: number | null;
  estimated_entry_mark: number;
  estimated_target_mark: number;
  estimated_profit_per_contract: number;
  provider_used: string | null;
  notes: string | null;
  tags: string[];
}

export interface JournalListResponse {
  total: number;
  offset: number;
  limit: number;
  path: string;
  entries: JournalEntry[];
}

export interface JournalSummary {
  total: number;
  confirmed: number;
  target_first?: number;
  stop_first?: number;
  win_rate: number | null;
  avg_rr: number | null;
}

export async function getJournal(limit = 100, offset = 0): Promise<JournalListResponse | null> {
  try {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    const res = await fetch(`${API_BASE_URL}/api/journal?${params.toString()}`, {
      next: { revalidate: 30, tags: ["journal"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as JournalListResponse;
  } catch {
    return null;
  }
}

export async function getJournalSummary(): Promise<JournalSummary | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/journal/summary`, {
      next: { revalidate: 30, tags: ["journal"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as JournalSummary;
  } catch {
    return null;
  }
}

export interface StructureLine {
  name: string;
  label: string | null;
  role: string | null;
  kind: "ascending" | "descending" | string;
  zone_type: string | null;
  projected_value: number;
  distance: number | null;
}

export interface StructureProjection {
  pivot_session: string;
  as_of: string;
  lines: StructureLine[];
  closest_above: StructureLine | null;
  closest_below: StructureLine | null;
  closest_descending_above: StructureLine | null;
  closest_descending_below: StructureLine | null;
}

export async function getStructure(): Promise<StructureProjection | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/structure/spy`, {
      next: { revalidate: 60, tags: ["structure"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as StructureProjection;
  } catch {
    return null;
  }
}

export interface NewsItem {
  title: string | null;
  summary: string | null;
  source: string | null;
  url: string | null;
  published: string | null;
  score: number | null;
  relevance: string | null;
}

export interface EconomicEvent {
  title: string | null;
  country: string | null;
  impact: string | null;
  scheduled_at: string | null;
  actual: string | null;
  forecast: string | null;
  previous: string | null;
  source: string | null;
}

export interface SentimentSummary {
  score: number;
  tone: "bullish" | "bearish" | "neutral";
  headline_count: number;
  positive_count?: number;
  negative_count?: number;
  explanation: string;
}

export interface DailyBrief {
  as_of: string;
  spot: SpotSnapshot;
  vix: VixSnapshot;
  watch: WatchStrikes;
  structure: StructureProjection | null;
  news: NewsItem[];
  events: EconomicEvent[];
  sentiment?: SentimentSummary;
}

export async function getDailyBrief(): Promise<DailyBrief | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/brief/spy`, {
      next: { revalidate: 120, tags: ["brief"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as DailyBrief;
  } catch {
    return null;
  }
}

export interface CandleBar {
  t: string;
  o: number | null;
  h: number | null;
  l: number | null;
  c: number | null;
  v: number | null;
  lines?: Record<string, number | null>;
}

export interface ChartResponse {
  period: string;
  spot_price: number | null;
  bars: CandleBar[];
  structure: StructureProjection | null;
}

export async function getChart(period = "5d"): Promise<ChartResponse | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/chart/spy?period=${period}`, {
      next: { revalidate: 60, tags: ["chart"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as ChartResponse;
  } catch {
    return null;
  }
}

export interface ReplayBar extends CandleBar {
  lines: Record<string, number | null>;
}

export interface ReplaySession {
  session: string;
  pivot_session: string;
  bar_count: number;
  lines: Array<{ name: string; label: string | null; kind: string }>;
  bars: ReplayBar[];
}

export async function getReplay(date?: string): Promise<ReplaySession | null> {
  try {
    const url = date
      ? `${API_BASE_URL}/api/replay/spy?date=${date}`
      : `${API_BASE_URL}/api/replay/spy`;
    const res = await fetch(url, {
      next: { revalidate: 300, tags: ["replay"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as ReplaySession;
  } catch {
    return null;
  }
}
