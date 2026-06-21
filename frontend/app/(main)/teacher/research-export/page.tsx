import Link from "next/link";

import { exportResearchData } from "@/lib/api";

export default async function ResearchExportPage() {
  const data = await exportResearchData();

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Research Export</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">匿名化研究数据导出</h1>
          <p className="mt-2 text-slate-600">仅导出 student_code，不导出学生姓名，支持形成性评价研究数据整理。</p>
        </div>
        <Link href="/teacher/dashboard" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
          返回教师驾驶舱
        </Link>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap gap-3 text-sm">
          <span className="rounded-full bg-teal-50 px-3 py-1 font-semibold text-clinic">格式：{data.format}</span>
          <span className="rounded-full bg-emerald-50 px-3 py-1 font-semibold text-emerald-700">匿名化：{data.anonymous ? "是" : "否"}</span>
          <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-700">记录数：{data.rows.length}</span>
        </div>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2">student_code</th>
                <th className="px-3 py-2">class_name</th>
                <th className="px-3 py-2">module_type</th>
                <th className="px-3 py-2">score</th>
                <th className="px-3 py-2">created_at</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, index) => (
                <tr key={`${row.student_code}-${row.module_type}-${index}`} className="border-b border-slate-100">
                  <td className="px-3 py-3">{row.student_code}</td>
                  <td className="px-3 py-3">{row.class_name}</td>
                  <td className="px-3 py-3">{row.module_type}</td>
                  <td className="px-3 py-3">{row.score ?? "待评分"}</td>
                  <td className="px-3 py-3">{String(row.created_at).slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
