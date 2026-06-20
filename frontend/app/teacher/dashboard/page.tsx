import Link from "next/link";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { StatCard } from "@/components/StatCard";
import { getTeacherDashboard } from "@/lib/api";

export default async function TeacherDashboard() {
  const data = await getTeacherDashboard();

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">教师驾驶舱</p>
          <h1 className="text-2xl font-semibold">班级临床推理表现</h1>
        </div>
        <Link href="/teacher/cases" className="rounded-md bg-clinic px-4 py-2 text-white">
          管理病例
        </Link>
      </section>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="学生人数" value={data.student_count} />
        <StatCard label="完成病例数" value={data.completed_session_count} />
        <StatCard label="平均分" value={data.class_average_total_score || "待评分"} />
        <StatCard label="平均能力提升" value={`${data.average_improvement}%`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">班级能力画像</h2>
          <CompetencyRadar data={data.class_competency.chart_data} />
        </section>
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">共性短板</h2>
          <div className="mt-4 space-y-3">
            {data.weak_dimensions.length ? (
              data.weak_dimensions.map((item) => (
                <div key={item.key} className="rounded-md bg-slate-50 p-3">
                  <div className="font-medium">{item.label}</div>
                  <div className="mt-1 text-sm text-slate-500">
                    {item.level} · 平均 {item.score}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">暂无明显短板。</p>
            )}
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">推荐教学重点</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {data.teaching_focus.map((item) => (
            <div key={item} className="rounded-md bg-clinic-soft p-3 text-sm text-teal-900">
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">学生表现</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2">学生姓名</th>
                <th className="px-3 py-2">当前阶段</th>
                <th className="px-3 py-2">最近得分</th>
                <th className="px-3 py-2">最弱能力</th>
                <th className="px-3 py-2">推荐训练方向</th>
                <th className="px-3 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              {data.students.map((student) => (
                <tr key={student.id} className="border-b border-slate-100">
                  <td className="px-3 py-3">{student.name}</td>
                  <td className="px-3 py-3">{student.current_stage}</td>
                  <td className="px-3 py-3">{student.recent_score ?? "待评分"}</td>
                  <td className="px-3 py-3">{student.weakest_ability}</td>
                  <td className="px-3 py-3">{student.recommended_training}</td>
                  <td className="px-3 py-3 text-slate-400">查看详情</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">最近训练记录</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {data.recent_sessions.length ? (
            data.recent_sessions.map((item) => (
              <div key={item.session_id} className="rounded-md bg-slate-50 p-3 text-sm">
                <div className="font-medium">{item.student_name} · {item.case_title}</div>
                <div className="mt-1 text-slate-500">得分：{item.score ?? "待评分"}</div>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">暂无完成记录。</p>
          )}
        </div>
      </section>
    </div>
  );
}
