import type { Metadata } from "next";
import "./globals.css";
import "./observatory-polish.css";

export const metadata: Metadata = {
  title: "Connectome Fighter · Neural Observatory",
  description: "Observe FightingICE combat, neural simulation on MaleCNS connectivity, and physical FlyBody motion. Recorded evaluations and verified LIVE observations are clearly distinguished.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
