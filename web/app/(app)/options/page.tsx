import { SoonPage } from "@/components/soon-page";
import { Target } from "lucide-react";

export default function OptionsPage() {
  return (
    <SoonPage
      kicker="Options Cockpit"
      title="The same-day contract bench."
      body="Live Tastytrade quotes, projected entry, delta-aware P/L on the trigger line — armed only on confirmed signals."
      Icon={Target}
      bullets={[
        "Live bid/ask, mark, spread, and Greeks via Tastytrade DXLink",
        "Strike selection aware of GEX walls and OI magnets",
        "Projected entry mark on the trigger line (delta-only)",
        "Zero-bid/zero-ask filter so illiquid strikes never silently price at $0",
      ]}
    />
  );
}
