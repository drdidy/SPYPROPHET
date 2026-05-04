import { SoonPage } from "@/components/soon-page";
import { Sparkles } from "lucide-react";

export default function ForesightPage() {
  return (
    <SoonPage
      kicker="Foresight"
      title="Pre-session structure plan."
      body="Tomorrow's anchors, dynamic projection, and learning-profile-weighted scenarios — built before the bell."
      Icon={Sparkles}
      bullets={[
        "Prior-session high/low anchors with dynamic projection",
        "Slope calibration locked from the structure engine",
        "Learning profile factored in (sample size + matching context)",
        "Scenarios bench-tested against GEX, max-pain, dark-pool levels",
      ]}
    />
  );
}
