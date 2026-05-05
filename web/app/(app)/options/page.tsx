import { Reveal, StaggerGroup, StaggerItem } from "@/components/reveal";
import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { getOptionsChain, type OptionsChain } from "@/lib/api";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Layers,
  Target,
} from "lucide-react";

export const revalidate = 60;

export default async function OptionsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const chainResult = await getOptionsChain(today, 12);
  const chain: OptionsChain | null =
    chainResult && "strikes" in chainResult ? chainResult : null;
  const errorStatus =
    chainResult && "error" in chainResult ? chainResult : null;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <CardKicker className="mb-1.5 flex items-center gap-2">
              <Target className="h-3 w-3" strokeWidth={3} /> Options Cockpit
            </CardKicker>
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
              The same-day contract bench.
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">
              SPY chain centered on spot. Click any strike to pull a live
              bid/ask + Greeks read.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {chain ? (
              <>
                <Pill tone="blue">{chain.expiration}</Pill>
                {chain.spot_price !== null && (
                  <Pill tone="violet">SPY ${chain.spot_price.toFixed(2)}</Pill>
                )}
                <Pill tone="live" pulse>Live chain</Pill>
              </>
            ) : (
              <Pill tone="amber">Chain unavailable</Pill>
            )}
          </div>
        </div>
      </Reveal>

      {errorStatus && (
        <Reveal>
          <Card className="border-amber/30 bg-amber/[0.05]">
            <CardBody>
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber" strokeWidth={2} />
                <div>
                  <div className="text-sm font-bold text-amber">
                    {errorStatus.status === 503
                      ? "Tastytrade not configured"
                      : errorStatus.status === 502
                        ? "Chain feed unavailable"
                        : errorStatus.status === 404
                          ? "Expiration not in chain"
                          : "Chain request failed"}
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {errorStatus.status > 0
                      ? `HTTP ${errorStatus.status}. Try again in a moment.`
                      : "API unreachable. Check NEXT_PUBLIC_API_URL."}
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>
        </Reveal>
      )}

      {chain && (
        <Reveal delay={0.1}>
          <Card hoverable className="overflow-hidden">
            <CardHeader>
              <div>
                <CardKicker className="flex items-center gap-2">
                  <Layers className="h-3 w-3" strokeWidth={3} /> Strikes around spot
                </CardKicker>
                <CardTitle className="mt-1.5">
                  {chain.strikes.length} contracts · {chain.expiration}
                </CardTitle>
              </div>
              <Pill tone="green">Cached 60s</Pill>
            </CardHeader>
            <CardBody>
              <ChainTable chain={chain} />
            </CardBody>
          </Card>
        </Reveal>
      )}

      <Reveal delay={0.2}>
        <Card>
          <CardHeader>
            <div>
              <CardKicker>Per-strike quote</CardKicker>
              <CardTitle className="mt-1.5">Live bid / ask / Greeks</CardTitle>
            </div>
          </CardHeader>
          <CardBody>
            <p className="text-sm leading-relaxed text-muted">
              Every chain row above is a strike pair. The full live quote
              (bid, ask, mark, spread, delta, gamma, theta, vega, IV) for
              any pair is one fetch away — wired in the next iteration as a
              click-to-quote panel. The endpoint is already serving:{" "}
              <code className="rounded bg-surface-2/60 px-1.5 py-0.5 font-mono text-xs text-text">
                GET /api/quotes/spy?call_strike=&put_strike=
              </code>
              .
            </p>
          </CardBody>
        </Card>
      </Reveal>
    </div>
  );
}

function ChainTable({ chain }: { chain: OptionsChain }) {
  const spot = chain.spot_price ?? 0;
  return (
    <div className="overflow-hidden rounded-xl border border-border/70">
      <div className="grid grid-cols-[1fr_auto_1fr] gap-px bg-border/60 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">
        <div className="bg-surface-2/60 px-4 py-3 text-right">
          Call
        </div>
        <div className="bg-surface-2/60 px-6 py-3 text-center font-[family-name:var(--font-display)] tracking-[0.2em]">
          Strike
        </div>
        <div className="bg-surface-2/60 px-4 py-3 text-left">
          Put
        </div>
      </div>
      <StaggerGroup className="divide-y divide-border/50" delayChildren={0.05}>
        {chain.strikes.map((row) => {
          const distance = spot ? row.strike - spot : 0;
          const isAboveSpot = distance > 0;
          const isAtSpot = Math.abs(distance) < 0.5;
          const tone = isAtSpot
            ? "bg-blue/[0.08] hover:bg-blue/[0.12]"
            : "bg-surface/40 hover:bg-surface-2/40";
          return (
            <StaggerItem key={row.strike}>
              <div
                className={
                  "grid grid-cols-[1fr_auto_1fr] items-center transition-colors " + tone
                }
              >
                <div className="px-4 py-3 text-right">
                  <div className="font-mono text-sm tabular text-text">
                    {row.call_symbol ?? "—"}
                  </div>
                  <div className="mt-0.5 text-[0.62rem] uppercase tracking-[0.14em] text-muted">
                    {row.call_streamer_symbol ? "Streamer ready" : "No live feed"}
                  </div>
                </div>
                <div className="flex flex-col items-center gap-0.5 border-x border-border/60 bg-surface-2/30 px-6 py-3">
                  <span className="font-[family-name:var(--font-space-grotesk)] text-lg font-extrabold tabular text-text">
                    {row.strike.toFixed(0)}
                  </span>
                  {isAtSpot ? (
                    <Pill tone="blue" size="xs">at spot</Pill>
                  ) : (
                    <span
                      className={
                        "inline-flex items-center gap-0.5 text-[0.62rem] font-bold tabular " +
                        (isAboveSpot ? "text-green-bright" : "text-red-bright")
                      }
                    >
                      {isAboveSpot ? (
                        <ArrowUpRight className="h-3 w-3" strokeWidth={2.5} />
                      ) : (
                        <ArrowDownRight className="h-3 w-3" strokeWidth={2.5} />
                      )}
                      {Math.abs(distance).toFixed(2)}
                    </span>
                  )}
                </div>
                <div className="px-4 py-3 text-left">
                  <div className="font-mono text-sm tabular text-text">
                    {row.put_symbol ?? "—"}
                  </div>
                  <div className="mt-0.5 text-[0.62rem] uppercase tracking-[0.14em] text-muted">
                    {row.put_streamer_symbol ? "Streamer ready" : "No live feed"}
                  </div>
                </div>
              </div>
            </StaggerItem>
          );
        })}
      </StaggerGroup>
    </div>
  );
}
