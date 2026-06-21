import type { Metadata } from "next";
import Link from "next/link";
import { GraduationCap, LayoutDashboard, LogIn, MonitorUp, Stethoscope } from "lucide-react";

import "./globals.css";

export const metadata: Metadata = {
  title: "ClinPath：AI辅助临床教学与自适应学习路径系统",
  description: "面向临床医学本科生的 AI 辅助临床教学与自适应学习路径系统",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <Stethoscope className="h-6 w-6 text-clinic" />
              <span>ClinPath</span>
            </Link>
            <nav className="flex items-center gap-2 text-sm">
              <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/demo">
                <MonitorUp className="h-4 w-4" />
                展示模式
              </Link>
              <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/student/dashboard">
                <GraduationCap className="h-4 w-4" />
                学生端
              </Link>
              <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/teacher/dashboard">
                <LayoutDashboard className="h-4 w-4" />
                教师端
              </Link>
              <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/login">
                <LogIn className="h-4 w-4" />
                登录
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-5 py-6">{children}</main>
      </body>
    </html>
  );
}
