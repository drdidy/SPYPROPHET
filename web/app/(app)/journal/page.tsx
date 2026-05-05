import { Reveal } from "@/components/reveal";
import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import {
  getJournal,
  getJournalSummary,
  type JournalEntry,
} from "@/lib/api";
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Clock,
  TrendingDown,
  TrendingUp,
  XCircle,
} from "lucide-react";

export const revalidate = 30;

export default async function JournalPage() {
  const [list, summary] = await Promise.all([
    getJournal(100, 0),
    getJournalSummary(),
  ]);

  const entries = list?.entries ?? [];
  const empty = !list || list.total === 0;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <CardKicker className="mb-1.5 flex items-center gap-2">
              <BarChart3 className="h-3 w-3" strokeWidth={3} /> Journal
            </CardKicker>
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
              Outcome analytics, in your own data.
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">
              Confirmed signals, graded outcomes, and the actual edge they
              produced. Read-only for now — write path moves to a persistent
              disk in the next iteration.
            </p>
          </div>
          {list && (
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone="blue">{list.total} entries</Pill>
              {!empty && <Pill tone="violet">Newest first</Pill>}
            </div>
          )}
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <SummaryStrip summary={summary} />
      </Reveal>

      {empty ? (
        <Reveal delay={0.2}>
          <Card>
            <CardBody>
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 flex-shrink-0 text-amber" strokeWidth={2} />
                <div>
                  <div className="text-sm font-bold text-amber">
                    No journal entries yet
                  </div>
                  <p className="mt-1 max-w-2xl text-xs text-muted">
                    The Streamlit terminal writes to{" "}
                    <code className="rounded bg-surface-2/60 px-1.5 py-0.5 font-mono text-text">
                      data/signal_journal.json
                    </code>
                    . To see entries here, copy that file to the API
                    service&apos;s persistent disk at the same path. Until
                    then, this view stays empty.
                  </p>
                </div>
              </div>
            </CardBody>
          </Card>
        </Reveal>
      ) : (
        <Reveal delay={0.2}>
          <Card hoverable className="overflow-hidden">
            <CardHeader>
              <div>
                <CardKicker>Confirmed signals</CardKicker>
                <CardTitle className="mt-1.5">{entries.length} most recent</CardTitle>
              </div>
              <Pill tone="green">Auto-refresh 30s</Pill>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-1 gap-3">
                {entries.map((e) => (
                  <EntryRow key={e.journal_id} entry={e} />
                ))}
              </div>
            </CardBody>
          </Card>
        </Reveal>
      )}
    </div>
  );
}

function SummaryStrip({ summary }: { summary: Awaited<ReturnType<typeof getJournalSummary>> }) {
  if (!summary) {
    return (
      <Card>
        <CardBody>
          <div className="text-sm text-muted">Summary unavailable.</div>
        </CardBody>
      </Card>
    );
  }
  const stats: { label: string; value: string; tone: "blue" | "green" | "amber" | "red" }[] = [
    { label: "Total", value: String(summary.total), tone: "blue" },
    { label: "Confirmed", value: String(summary.confirmed), tone: "blue" },
    {
      label: "Win rate",
      value: summary.win_rate !== null ? `${(summary.win_rate * 100).toFixed(0)}%` : "—",
      tone: summary.win_rate !== null && summary.win_rate >= 0.5 ? "green" : "amber",
    },
    {
      label: "Avg R:R",
      value: summary.avg_rr !== null ? `1 : ${summary.avg_rr.toFixed(2)}` : "—",
      tone: summary.avg_rr !== null && summary.avg_rr >= 1 ? "green" : "amber",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {stats.map((s) => (
        <Card key={s.label}>
          <CardBody>
            <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-muted">
              {s.label}
            </div>
            <div
              className={
                "mt-2 font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tabular " +
                (s.tone === "green"
                  ? "text-green-bright"
                  : s.tone === "amber"
                    ? "text-amber"
                    : s.tone === "red"
                      ? "text-red-bright"
                      : "text-text")
              }
            >
              {s.value}
            </div>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

function EntryRow({ entry }: { entry: JournalEntry }) {
  const isCall = entry.signal_type === "CALL";
  const isWin = entry.outcome === "TARGET_FIRST";
  const isLoss = entry.outcome === "STOP_FIRST";
  const sideTone = isCall ? "text-green-bright" : "text-red-bright";
  const SideIcon = isCall ? TrendingUp : TrendingDown;
  const OutcomeIcon = isWin ? CheckCircle2 : isLoss ? XCircle : Clock;
  const outcomeTone = isWin
    ? "text-green-bright"
    : isLoss
      ? "text-red-bright"
      : "text-muted";
  const outcomeLabel = isWin ? "Win" : isLoss ? "Loss" : entry.outcome ?? "Pending";

  const date = entry.trade_date ?? entry.created_at?.slice(0, 10) ?? "—";

  return (
    <div className="rounded-xl border border-border/70 bg-surface-2/40 p-4 transition-colors hover:bg-surface-2/60">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_auto_auto]">
        <div className="flex items-start gap-3">
          <SideIcon className={"mt-0.5 h-5 w-5 flex-shrink-0 " + sideTone} strokeWidth={2.5} />
          <div>
            <div className="flex flex-wrap items-baseline gap-2">
              <span className={"font-[family-name:var(--font-space-grotesk)] text-base font-bold " + sideTone}>
                {entry.signal_type ?? "—"}
              </span>
              <span className="text-sm text-text">{entry.line_name ?? "—"}</span>
              {entry.bias && (
                <span className="text-[0.62rem] font-bold uppercase tracking-[0.14em] text-muted">
                  · {entry.bias}
                </span>
              )}
              {entry.quality_grade && (
                <Pill tone="blue" size="xs">Grade {entry.quality_grade}</Pill>
              )}
            </div>
            <div className="mt-1 text-xs text-muted">
              {date}
              {entry.entry_time && (
                <> · entered {new Date(entry.entry_time).toLocaleTimeString()}</>
              )}
            </div>
            {entry.notes && (
              <div className="mt-2 text-xs italic text-muted">&ldquo;{entry.notes}&rdquo;</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border/60 bg-surface/60 px-3 py-2 text-right">
          <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">Entry → Stop</div>
          <div className="font-mono text-sm tabular text-text">
            ${entry.entry_price?.toFixed(2)}
          </div>
          <div className="font-mono text-xs tabular text-red-bright">
            ${entry.stop_price?.toFixed(2)}
          </div>
        </div>

        <div className="rounded-lg border border-border/60 bg-surface/60 px-3 py-2 text-right">
          <div className="text-[0.6rem] font-bold uppercase tracking-[0.14em] text-muted">Target / R:R</div>
          <div className="font-mono text-sm tabular text-text">
            ${entry.target_price?.toFixed(2)}
          </div>
          <div className="font-mono text-xs tabular text-blue-bright">
            1 : {entry.rr_ratio?.toFixed(2)}
          </div>
        </div>

        <div className="flex items-center gap-2 self-start md:self-center">
          <OutcomeIcon className={"h-5 w-5 " + outcomeTone} strokeWidth={2.5} />
          <span className={"text-sm font-bold " + outcomeTone}>{outcomeLabel}</span>
        </div>
      </div>
    </div>
  );
}
