import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Connectome Fighter · Neural Observatory",
  description: "Watch FightingICE, neural simulation on MaleCNS connectivity, and physical FlyBody movement. Recorded evaluations and verified LIVE observations are clearly separated.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
