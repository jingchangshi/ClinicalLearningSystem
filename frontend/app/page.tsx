import Link from "next/link";
import { GraduationCap, LayoutDashboard, MonitorUp } from "lucide-react";

export default function Home() {
  return (
    <div className="grid min-h-[70vh] content-center gap-8">
      <section className="max-w-3xl">
        <p className="text-sm font-medium text-clinic">ClinPath</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">AI辅助临床教学与自适应学习路径系统</h1>
        <p className="mt-3 text-slate-600">
          围绕风湿免疫病例训练、临床推理追问、自动评分、能力画像和教师驾驶舱形成医学教育闭环。
        </p>
      </section>
      <div className="grid gap-4 md:grid-cols-3">
        <Link href="/demo" className="rounded-lg border border-clinic/30 bg-white p-6 shadow-sm hover:border-clinic">
          <MonitorUp className="h-8 w-8 text-clinic" />
          <h2 className="mt-4 text-xl font-semibold">展示模式</h2>
          <p className="mt-2 text-sm text-slate-600">用于课题申报、教学汇报和系统截图展示。</p>
          <span className="mt-4 inline-flex rounded-md bg-clinic px-3 py-2 text-sm font-medium text-white">
            进入 ClinPath 展示模式
          </span>
        </Link>
        <Link href="/student/dashboard" className="rounded-lg border border-slate-200 bg-white p-6 hover:border-clinic">
          <GraduationCap className="h-8 w-8 text-clinic" />
          <h2 className="mt-4 text-xl font-semibold">学生端</h2>
          <p className="mt-2 text-sm text-slate-600">进入病例训练、查看能力画像和自适应学习路径。</p>
        </Link>
        <Link href="/teacher/dashboard" className="rounded-lg border border-slate-200 bg-white p-6 hover:border-clinic">
          <LayoutDashboard className="h-8 w-8 text-clinic" />
          <h2 className="mt-4 text-xl font-semibold">教师端</h2>
          <p className="mt-2 text-sm text-slate-600">查看班级表现、共性短板、教学重点和病例管理。</p>
        </Link>
      </div>
    </div>
  );
}
