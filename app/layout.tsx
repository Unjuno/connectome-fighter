import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Connectome Fighter · Latest Model Round",
  description: "Watch the latest post-update Connectome Fighter candidate for one fixed-condition FightingICE round.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
