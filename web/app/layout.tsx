import type { Metadata } from "next";
import { Manrope, Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "SPY Prophet — Same-day SPY structure terminal",
  description:
    "Structure-led decision support for same-day SPY. Prior-session anchors, dynamic projection, signal confirmation, and a live options cockpit.",
  metadataBase: new URL("https://spyprophet.app"),
  applicationName: "SPY Prophet",
  authors: [{ name: "drdidy" }],
  keywords: [
    "SPY",
    "options",
    "0DTE",
    "structure",
    "trading terminal",
    "morning briefing",
    "decision support",
  ],
  openGraph: {
    title: "SPY Prophet",
    description: "Structure-led decision support for same-day SPY.",
    url: "https://spyprophet.app",
    siteName: "SPY Prophet",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "SPY Prophet",
    description: "Structure-led decision support for same-day SPY.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${manrope.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-full">{children}</body>
    </html>
  );
}
