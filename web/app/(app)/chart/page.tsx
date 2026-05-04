import { SoonPage } from "@/components/soon-page";
import { LineChart } from "lucide-react";

export default function ChartPage() {
  return (
    <SoonPage
      kicker="Chart"
      title="Decision map & candles."
      body="Hourly candles with structure overlays. Interactive, zoomable, accessible — built on Recharts + custom SVG."
      Icon={LineChart}
      bullets={[
        "Decision map view with primary + secondary lines",
        "Technical candles view for raw price action",
        "Trigger / target / stop overlays on confirmed signals",
        "Replay-safe — never reveals future candles in step mode",
      ]}
    />
  );
}
