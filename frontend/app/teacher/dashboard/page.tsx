import Link from "next/link";
import { ClipboardList, Target, TrendingUp, Users } from "lucide-react";

import { ClassHeatmap } from "@/components/ClassHeatmap";
import { CompetencyRadar } from "@/components/CompetencyRadar";
import { TeachingInterventionPanel } from "@/components/TeachingInterventionPanel";
import { TrainingLoopFlow } from "@/components/TrainingLoopFlow";
import { getTeacherDashboard } from "@/lib/api";

export default async function TeacherDashboard() {
  const data = await getTeacherDashboard();

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Teacher Analytics Dashboard</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">教师精准教学驾驶舱</h1>
          <p className="mt-2 text-slate-600">基于班级多模块训练数据进行教学诊断与干预建议。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/teacher/case-generator" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
            AI生成病例
          </Link>
          <Link href="/teacher/cases" className="rounded-md bg-clinic px-4 py-2 text-white">
            管理病例
          </Link>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard title="参与学生" value={String(data.student_count)} note="覆盖当前班级学生" icon={Users} />
        <MetricCard title="完成训练总次数" value={String(data.training_total_count || data.completed_session_count)} note={moduleCountText(data.module_counts)} icon={ClipboardList} />
        <MetricCard title="平均能力提升" value={`+${data.average_improvement}%`} note={`平均分 ${data.class_average_total_score || "待评分"}`} icon={TrendingUp} />
        <MetricCard title="当前共性短板" value={data.current_common_weakness} note="基于班级能力画像最低维度" icon={Target} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section>
          <h2 className="mb-3 font-semibold">班级能力热力图</h2>
          <ClassHeatmap rows={data.class_heatmap} />
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">班级能力画像</h2>
          <CompetencyRadar data={data.class_competency.chart_data} />
          <div className="mt-4 space-y-3">
            {data.weak_dimensions.length ? (
              data.weak_dimensions.map((item) => (
                <div key={item.key} className="rounded-xl bg-amber-50 p-3">
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

      <div className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
        <TeachingInterventionPanel interventions={data.teaching_interventions.length ? data.teaching_interventions : data.teaching_focus} />
        <TrainingLoopFlow />
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
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

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
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

function MetricCard({ title, value, note, icon: Icon }: { title: string; value: string; note: string; icon: typeof Users }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="mt-3 line-clamp-2 text-2xl font-semibold text-ink">{value}</p>
        </div>
        <span className="rounded-xl bg-teal-50 p-2 text-clinic">
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3 text-sm text-slate-600">{note}</p>
    </div>
  );
}

function moduleCountText(counts: { knowledge: number; skill: number; case: number; guideline: number; sp: number }) {
  return `知识${counts.knowledge} / 技能${counts.skill} / 病例${counts.case} / 指南${counts.guideline} / SP${counts.sp}`;
}
