import { SessionStrip } from "./session-strip";

/**
 * Marketing strip below the hero. Was a live Yahoo ticker; replaced with a
 * deterministic market-session indicator so the page never shows stale dashes
 * when an upstream is rate-limited. The real-time data lives on /live where
 * it belongs (proper broker feed via the FastAPI backend).
 */
export function TickerTape() {
  return <SessionStrip />;
}
