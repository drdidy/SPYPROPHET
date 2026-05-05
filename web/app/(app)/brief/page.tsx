import { Reveal, StaggerGroup, StaggerItem } from "@/components/reveal";
import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { getDailyBrief, type DailyBrief, type EconomicEvent, type NewsItem } from "@/lib/api";
import {
  AlertTriangle,
  BookOpenText,
  CalendarClock,
  ExternalLink,
  Newspaper,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

export const revalidate = 120;

export default async function BriefPage() {
  const brief = await getDailyBrief();

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <CardKicker className="mb-1.5 flex items-center gap-2">
              <BookOpenText className="h-3 w-3" strokeWidth={3} /> Daily Brief
            </CardKicker>
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
              Trader-focused day-ahead read.
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">
              Spot, regime, structure, and the catalysts on deck — one
              screen, before the bell.
            </p>
          </div>
          {brief && (
            <Pill tone="violet">As of {fmtTime(brief.as_of)}</Pill>
          )}
        </div>
      </Reveal>

      {!brief ? (
        <BriefError />
      ) : (
        <>
          <Reveal delay={0.1}>
            <BriefSnapshot brief={brief} />
          </Reveal>

          <Reveal delay={0.2}>
            <Card hoverable className="overflow-hidden">
              <CardHeader>
                <div>
                  <CardKicker className="flex items-center gap-2">
                    <Newspaper className="h-3 w-3" strokeWidth={3} /> Market news
                  </CardKicker>
                  <CardTitle className="mt-1.5">
                    {brief.news.length > 0
                      ? `${brief.news.length} fresh headlines`
                      : "No headlines available"}
                  </CardTitle>
                </div>
                <Pill tone="green">Auto-refresh 15m</Pill>
              </CardHeader>
              <CardBody>
                {brief.news.length === 0 ? (
                  <p className="text-sm text-muted">
                    No same-day market headlines from configured RSS feeds yet.
                  </p>
                ) : (
                  <StaggerGroup className="grid grid-cols-1 gap-3" delayChildren={0.05}>
                    {brief.news.map((item) => (
                      <StaggerItem key={`${item.url}-${item.published}`}>
                        <NewsRow item={item} />
                      </StaggerItem>
                    ))}
                  </StaggerGroup>
                )}
              </CardBody>
            </Card>
          </Reveal>

          <Reveal delay={0.3}>
            <Card hoverable className="overflow-hidden">
              <CardHeader>
                <div>
                  <CardKicker className="flex items-center gap-2">
                    <CalendarClock className="h-3 w-3" strokeWidth={3} /> Catalysts on deck
                  </CardKicker>
                  <CardTitle className="mt-1.5">
                    {brief.events.length > 0
                      ? `Next 7 days · ${brief.events.length} scheduled`
                      : "No high-impact events on deck"}
                  </CardTitle>
                </div>
              </CardHeader>
              <CardBody>
                {brief.events.length === 0 ? (
                  <p className="text-sm text-muted">
                    The configured economic calendar has no scheduled
                    high-impact events in the next week.
                  </p>
                ) : (
                  <div className="grid grid-cols-1 gap-3">
                    {brief.events.map((ev, i) => (
                      <EventRow key={`${ev.title}-${ev.scheduled_at}-${i}`} event={ev} />
                    ))}
                  </div>
                )}
              </CardBody>
            </Card>
          </Reveal>
        </>
      )}
    </div>
  );
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function BriefError() {
  return (
    <Reveal>
      <Card className="border-amber/30 bg-amber/[0.05]">
        <CardBody>
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber" strokeWidth={2} />
            <div>
              <div className="text-sm font-bold text-amber">Brief unavailable</div>
              <p className="mt-1 max-w-2xl text-xs text-muted">
                The morning brief composite failed to load. Page revalidates every 2 minutes.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>
    </Reveal>
  );
}

function BriefSnapshot({ brief }: { brief: DailyBrief }) {
  const desc_above = brief.structure?.closest_descending_above;
  const desc_below = brief.structure?.closest_descending_below;
  const change_pct = brief.spot.change_pct ?? 0;
  const change_tone =
    brief.spot.change_pct === null
      ? "text-muted"
      : change_pct >= 0
        ? "text-green-bright"
        : "text-red-bright";
  const ChangeIcon = change_pct >= 0 ? TrendingUp : TrendingDown;

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Card>
        <CardBody>
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">SPY</div>
          <div className="mt-2 font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tabular text-text">
            {brief.spot.price !== null ? `$${brief.spot.price.toFixed(2)}` : "—"}
          </div>
          <div className={"mt-1 inline-flex items-center gap-1.5 text-xs font-bold tabular " + change_tone}>
            {brief.spot.change_pct !== null ? (
              <>
                <ChangeIcon className="h-3.5 w-3.5" strokeWidth={2.5} />
                {change_pct >= 0 ? "+" : ""}
                {change_pct.toFixed(2)}%
              </>
            ) : (
              <span className="text-muted">change unavailable</span>
            )}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">VIX</div>
          <div
            className={
              "mt-2 font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tabular " +
              (brief.vix.regime_tone === "green"
                ? "text-green-bright"
                : brief.vix.regime_tone === "amber"
                  ? "text-amber"
                  : brief.vix.regime_tone === "red"
                    ? "text-red-bright"
                    : "text-text")
            }
          >
            {brief.vix.value !== null ? brief.vix.value.toFixed(2) : "—"}
          </div>
          <div className="mt-1 text-xs text-muted">
            {brief.vix.regime ?? "Regime unavailable"}
          </div>
        </CardBody>
      </Card>

      <Card glow={desc_above ? "red" : "none"}>
        <CardBody>
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">PUT trigger</div>
          <div className="mt-2 font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold tabular text-red-bright">
            {desc_above ? `$${desc_above.projected_value.toFixed(2)}` : "—"}
          </div>
          <div className="mt-1 text-xs text-muted">
            {desc_above
              ? `${desc_above.label ?? desc_above.name} · ${desc_above.distance !== null ? (desc_above.distance > 0 ? "+" : "") + desc_above.distance.toFixed(2) + " from spot" : ""}`
              : "No active line above spot"}
          </div>
        </CardBody>
      </Card>

      <Card glow={desc_below ? "green" : "none"}>
        <CardBody>
          <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">CALL trigger</div>
          <div className="mt-2 font-[family-name:var(--font-space-grotesk)] text-2xl font-extrabold tabular text-green-bright">
            {desc_below ? `$${desc_below.projected_value.toFixed(2)}` : "—"}
          </div>
          <div className="mt-1 text-xs text-muted">
            {desc_below
              ? `${desc_below.label ?? desc_below.name} · ${desc_below.distance !== null ? desc_below.distance.toFixed(2) + " from spot" : ""}`
              : "No active line below spot"}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function NewsRow({ item }: { item: NewsItem }) {
  const fmt = item.published ? fmtTime(item.published) : "—";
  const inner = (
    <div className="flex items-start gap-3">
      <div className="flex-1">
        <div className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">
          <span>{item.source ?? "—"}</span>
          <span>·</span>
          <span>{fmt}</span>
          {item.relevance && <Pill tone="blue" size="xs">{item.relevance}</Pill>}
        </div>
        <div className="mt-1.5 text-sm font-bold text-text">
          {item.title ?? "Untitled"}
        </div>
        {item.summary && (
          <div className="mt-1 line-clamp-2 text-xs text-muted">{item.summary}</div>
        )}
      </div>
      {item.url && <ExternalLink className="h-4 w-4 flex-shrink-0 text-muted" strokeWidth={2} />}
    </div>
  );

  if (item.url) {
    return (
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block rounded-xl border border-border/70 bg-surface-2/40 p-4 transition-colors hover:bg-surface-2/60"
      >
        {inner}
      </a>
    );
  }
  return (
    <div className="rounded-xl border border-border/70 bg-surface-2/40 p-4">{inner}</div>
  );
}

function EventRow({ event }: { event: EconomicEvent }) {
  const fmt = event.scheduled_at ? fmtTime(event.scheduled_at) : "—";
  const impactTone =
    event.impact?.toLowerCase() === "high"
      ? "red"
      : event.impact?.toLowerCase() === "medium"
        ? "amber"
        : "blue";

  return (
    <div className="rounded-xl border border-border/70 bg-surface-2/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">
            <span>{fmt}</span>
            {event.country && (
              <>
                <span>·</span>
                <span>{event.country}</span>
              </>
            )}
            {event.impact && (
              <Pill tone={impactTone as "red" | "amber" | "blue"} size="xs">{event.impact}</Pill>
            )}
          </div>
          <div className="mt-1.5 text-sm font-bold text-text">
            {event.title ?? "Untitled"}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 text-right text-xs md:gap-3">
          {[
            { label: "Forecast", value: event.forecast },
            { label: "Previous", value: event.previous },
            { label: "Actual", value: event.actual },
          ].map((cell) => (
            <div key={cell.label} className="rounded-lg border border-border/60 bg-surface/60 px-3 py-2">
              <div className="text-[0.6rem] font-bold uppercase tracking-[0.12em] text-muted">
                {cell.label}
              </div>
              <div className="mt-0.5 font-mono tabular text-text">
                {cell.value ?? "—"}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
