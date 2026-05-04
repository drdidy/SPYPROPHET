import { SoonPage } from "@/components/soon-page";
import { BookOpen } from "lucide-react";

export default function BriefPage() {
  return (
    <SoonPage
      kicker="Daily Brief"
      title="The trader-focused day-ahead read."
      body="Reconciles structure with external context — flow, GEX, dark-pool, max-pain — into a single, readable plan."
      Icon={BookOpen}
      bullets={[
        "Primary trade trigger with confirmation rule",
        "External context aligned to the trigger (not decoration)",
        "Verdict cards: confidence, alignment, risk",
        "AI-assisted morning briefing with cited sources",
      ]}
    />
  );
}
