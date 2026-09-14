import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Connectome Fighter · Neural Observatory",
  description: "FightingICEの戦闘、MaleCNS接続データ上の神経シミュレーション、FlyBodyの物理的な身体運動を観測する。評価録画と検証済みLIVEは明確に区別しています。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
