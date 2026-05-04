import { Card, CardBody, CardHeader, CardKicker, CardTitle } from "@/components/ui/card";
import { Pill } from "@/components/ui/pill";
import { ArrowRight, Sparkles, type LucideIcon } from "lucide-react";
import Link from "next/link";

interface SoonPageProps {
  kicker: string;
  title: string;
  body: string;
  bullets: string[];
  accent?: "blue" | "green" | "amber" | "violet" | "red";
  Icon: LucideIcon;
}

export function SoonPage({ kicker, title, body, bullets, accent = "blue", Icon }: SoonPageProps) {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <CardKicker className="mb-1.5 flex items-center gap-2">
            <Icon className="h-3 w-3" strokeWidth={3} /> {kicker}
          </CardKicker>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-extrabold tracking-tight text-text md:text-4xl">
            {title}
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted md:text-base">{body}</p>
        </div>
        <div className="flex items-center gap-2">
          <Pill tone="violet">In progress</Pill>
        </div>
      </div>

      <Card premium className="overflow-hidden">
        <CardHeader>
          <div>
            <CardKicker className="flex items-center gap-2">
              <Sparkles className="h-3 w-3" strokeWidth={3} /> Building this out
            </CardKicker>
            <CardTitle className="mt-1.5">A fully-realized page is coming.</CardTitle>
          </div>
          <Icon className="h-7 w-7 text-blue-bright" strokeWidth={2} />
        </CardHeader>
        <CardBody>
          <p className="max-w-2xl text-sm leading-relaxed text-muted md:text-base">
            The Streamlit version of this view is already live; the Next.js
            rebuild is being layered in tab-by-tab. Each replacement gets the
            full design treatment and connects to the same Python signal
            engine through a JSON API.
          </p>

          <ul className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {bullets.map((b) => (
              <li
                key={b}
                className="flex items-start gap-3 rounded-xl border border-border/70 bg-surface-2/40 p-3.5"
              >
                <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue/15 text-[0.62rem] font-bold tabular text-blue-bright">
                  ✓
                </span>
                <span className="text-sm leading-snug text-text">{b}</span>
              </li>
            ))}
          </ul>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="https://spyprophet.onrender.com"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-border-2 bg-surface-2 px-5 text-sm font-semibold text-text transition-all hover:-translate-y-0.5 hover:border-blue/60"
            >
              Use the Streamlit version
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/live"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-blue via-blue-bright to-green px-5 text-sm font-semibold text-[#06121a] shadow-[0_8px_28px_-6px_rgba(78,168,222,0.6)] transition-all hover:-translate-y-0.5"
            >
              Back to Live console
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
