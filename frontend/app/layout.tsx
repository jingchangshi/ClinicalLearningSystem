import type { Metadata } from "next";
import Link from "next/link";
import { GraduationCap, LayoutDashboard, Stethoscope } from "lucide-react";

import "./globals.css";

export const metadata: Metadata = {
  title: "诊途：临床推理与自适应学习系统",
  description: "面向临床医学本科生的病例推理训练 MVP",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
            <Link href="/student/dashboard" className="flex items-center gap-2 font-semibold">
              <Stethoscope className="h-6 w-6 text-clinic" />
              <span>诊途</span>
            </Link>
            <nav className="flex items-center gap-2 text-sm">
              <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/student/dashboard">
                <GraduationCap className="h-4 w-4" />
                学生端
              </Link>
              <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/teacher/dashboard">
                <LayoutDashboard className="h-4 w-4" />
                教师端
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-5 py-6">{children}</main>
      </body>
    </html>
  );
}
