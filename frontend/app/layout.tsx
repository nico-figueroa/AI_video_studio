import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Framewise — AI Video Studio",
  description: "Turn a story idea into a reviewed, cost-transparent video.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
