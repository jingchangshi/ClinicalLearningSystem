import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "ClinPath：AI辅助临床教学与自适应学习路径系统",
  description: "面向临床医学本科生的 AI 辅助临床教学与自适应学习路径系统",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
