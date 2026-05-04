import { BrandLogo } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";
import { ArrowLeft, ArrowUpRight, Compass } from "lucide-react";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="relative isolate flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 py-16">
      {/* big atmospheric glow */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-1/3 h-[60vmax] w-[60vmax] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue/15 blur-[140px]" />
      </div>

      <Link href="/" className="absolute left-6 top-6">
        <BrandLogo size={36} animated={false} />
      </Link>

      <div className="text-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-amber/40 bg-amber/10 px-3 py-1 text-[0.7rem] font-bold uppercase tracking-[0.16em] text-amber">
          <Compass className="h-3.5 w-3.5" strokeWidth={3} />
          Off-trigger
        </span>
        <h1 className="mt-6 font-[family-name:var(--font-space-grotesk)] text-7xl font-extrabold tracking-tight text-text md:text-9xl">
          <span className="text-brand-gradient">4</span>
          <span className="text-bullish-gradient">0</span>
          <span className="text-brand-gradient">4</span>
        </h1>
        <p className="mx-auto mt-5 max-w-md text-balance text-base leading-relaxed text-muted md:text-lg">
          That route isn&apos;t on the structure map. Head back to the terminal —
          all live levels stay armed.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="lg">
              <ArrowLeft className="h-4 w-4" />
              Back to landing
            </Button>
          </Link>
          <Link href="/live">
            <Button variant="primary" size="lg">
              Open Terminal
              <ArrowUpRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
