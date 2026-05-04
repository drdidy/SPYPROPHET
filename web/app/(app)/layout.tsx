import { NavRail } from "@/components/nav-rail";
import { Topbar } from "@/components/topbar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen w-full">
      <NavRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-4 py-6 lg:px-8 lg:py-8">{children}</main>
        <footer className="mt-auto border-t border-border/70 px-4 py-4 lg:px-8 text-xs text-muted">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-text">SPY Prophet</span>
            <span className="text-muted">
              Analysis only · No order execution · Hourly candles · US/Central display
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
