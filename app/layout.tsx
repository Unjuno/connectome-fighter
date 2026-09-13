import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Connectome Fighter LIVE",
  description: "Shared FightingICE + MaleCNS + neural-driven FlyBody spectator",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
