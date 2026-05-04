import { TickerMarquee, type TickerItem } from "./ticker-marquee";

const SYMBOLS: { yahoo: string; display: string }[] = [
  { yahoo: "SPY", display: "SPY" },
  { yahoo: "^VIX", display: "VIX" },
  { yahoo: "QQQ", display: "QQQ" },
  { yahoo: "IWM", display: "IWM" },
  { yahoo: "ES=F", display: "/ES" },
  { yahoo: "NQ=F", display: "/NQ" },
  { yahoo: "TLT", display: "TLT" },
  { yahoo: "DX-Y.NYB", display: "DXY" },
  { yahoo: "GLD", display: "GLD" },
  { yahoo: "BTC-USD", display: "BTC" },
];

const FALLBACK: TickerItem[] = SYMBOLS.map((s) => ({
  symbol: s.display,
  price: null,
  changePct: null,
}));

type SparkResult = {
  symbol: string;
  response?: Array<{
    meta?: {
      regularMarketPrice?: number;
      chartPreviousClose?: number;
      previousClose?: number;
    };
  }>;
};

async function fetchQuotes(): Promise<TickerItem[]> {
  // Yahoo's spark endpoint accepts up to ~50 symbols per call. One request
  // beats Promise.all-of-10 because Yahoo rate-limits aggressively.
  const symbolParam = SYMBOLS.map((s) => s.yahoo).join(",");
  const url = `https://query1.finance.yahoo.com/v7/finance/spark?symbols=${encodeURIComponent(symbolParam)}&range=2d&interval=1d`;
  try {
    const res = await fetch(url, {
      // 5 minutes — gentle on Yahoo's free unauth endpoint and more than fresh
      // enough for a marketing ticker. The /live page will hit a real broker
      // feed for true real-time data once the API backend is wired.
      next: { revalidate: 300 },
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        Accept: "application/json",
        "Accept-Language": "en-US,en;q=0.9",
      },
    });
    if (!res.ok) {
      console.warn(`[ticker] spark HTTP ${res.status}`);
      return FALLBACK;
    }
    const data = (await res.json()) as { spark?: { result?: SparkResult[] } };
    const results = data.spark?.result ?? [];
    const bySymbol = new Map<string, SparkResult>(results.map((r) => [r.symbol, r]));
    return SYMBOLS.map((s) => {
      const r = bySymbol.get(s.yahoo);
      const meta = r?.response?.[0]?.meta;
      if (!meta) return { symbol: s.display, price: null, changePct: null };
      const price = meta.regularMarketPrice ?? null;
      const prev = meta.chartPreviousClose ?? meta.previousClose ?? null;
      const changePct = price != null && prev ? ((price - prev) / prev) * 100 : null;
      return { symbol: s.display, price, changePct };
    });
  } catch (err) {
    console.warn(`[ticker] spark fetch failed:`, err instanceof Error ? err.message : err);
    return FALLBACK;
  }
}

export async function TickerTape() {
  const items = await fetchQuotes();
  return <TickerMarquee items={items} />;
}
