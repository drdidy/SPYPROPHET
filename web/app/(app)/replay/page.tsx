import { ReplayPlayer } from "@/components/replay-player";
import { Reveal } from "@/components/reveal";
import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { getReplay } from "@/lib/api";
import { AlertTriangle, History } from "lucide-react";

export const revalidate = 300;

export default async function ReplayPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const params = await searchParams;
  const session = await getReplay(params.date);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <CardKicker className="mb-1.5 flex items-center gap-2">
              <History className="h-3 w-3" strokeWidth={3} /> Replay Lab
            </CardKicker>
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
              Walk a session candle by candle.
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">
              Step through a prior trading day with future bars masked.
              Structure lines slope across the day so you can see how
              price respected (or broke) them.
            </p>
          </div>
          {session && (
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone="blue">Session · {session.session}</Pill>
              <Pill tone="violet">Pivots · {session.pivot_session}</Pill>
            </div>
          )}
        </div>
      </Reveal>

      {!session ? (
        <Reveal>
          <Card className="border-amber/30 bg-amber/[0.05]">
            <CardBody>
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber" strokeWidth={2} />
                <div>
                  <div className="text-sm font-bold text-amber">Replay unavailable</div>
                  <p className="mt-1 max-w-2xl text-xs text-muted">
                    No prior session data could be loaded. Try again
                    after the next deploy or pass an explicit
                    <code className="mx-1 rounded bg-surface-2/60 px-1.5 py-0.5 font-mono text-[0.7rem] text-text">?date=YYYY-MM-DD</code>
                    in the URL.
                  </p>
                </div>
              </div>
            </CardBody>
          </Card>
        </Reveal>
      ) : (
        <Reveal delay={0.1}>
          <Card hoverable className="overflow-hidden">
            <CardHeader>
              <div>
                <CardKicker>Session walk</CardKicker>
                <CardTitle className="mt-1.5">
                  {session.bar_count} hourly bars · pivots from {session.pivot_session}
                </CardTitle>
              </div>
              <Pill tone="green">Step or auto-play</Pill>
            </CardHeader>
            <CardBody>
              <ReplayPlayer session={session} />
            </CardBody>
          </Card>
        </Reveal>
      )}
    </div>
  );
}
