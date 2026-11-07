import type { Metadata } from "next";
import "./globals.css";
import { WorkflowConfirmation } from "@/components/workflow-confirmation";

export const metadata: Metadata = {
  title: "Framewise — AI Video Studio",
  description: "Turn a story idea into a reviewed, cost-transparent video.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><WorkflowConfirmation />{children}</body>
    </html>
  );
}
