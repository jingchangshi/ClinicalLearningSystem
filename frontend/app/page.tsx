import Link from "next/link";
import { GraduationCap, LayoutDashboard } from "lucide-react";

export default function Home() {
  return (
    <div className="grid min-h-[70vh] content-center gap-8">
      <section className="max-w-3xl">
        <p className="text-sm font-medium text-clinic">诊途</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">临床推理与自适应学习系统</h1>
        <p className="mt-3 text-slate-600">
          围绕风湿免疫病例训练、临床推理追问、自动评分、能力画像和教师驾驶舱形成医学教育闭环。
        </p>
      </section>
      <div className="grid gap-4 md:grid-cols-2">
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
