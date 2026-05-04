import { SoonPage } from "@/components/soon-page";
import { BarChart3 } from "lucide-react";

export default function JournalPage() {
  return (
    <SoonPage
      kicker="Journal"
      title="Outcome analytics, in your own data."
      body="Confirmed signals build a personal record. Win rate, R:R distribution, expectancy, and outcome breakdowns update in real time."
      Icon={BarChart3}
      bullets={[
        "Atomic, lock-protected JSON store (Postgres path coming)",
        "Auto-journal toggle for live signals",
        "Replay-mode bulk save with insert/update/skip counts",
        "Export to CSV / JSON, plus filtered analytics by line, bias, hour",
      ]}
    />
  );
}
