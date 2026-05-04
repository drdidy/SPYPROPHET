import { SoonPage } from "@/components/soon-page";
import { History } from "lucide-react";

export default function ReplayPage() {
  return (
    <SoonPage
      kicker="Replay Lab"
      title="Walk a session candle by candle."
      body="Step Replay hides future bars. Full Day Review opens hindsight outcome attribution. No look-ahead bias."
      Icon={History}
      bullets={[
        "Step Replay: hour-by-hour, future bars masked",
        "Full Day Review: hindsight outcome attribution",
        "Outcome breakdown: target-first, stop-first, no-hit, ambiguous",
        "Save replay signals into the journal with one click",
      ]}
    />
  );
}
