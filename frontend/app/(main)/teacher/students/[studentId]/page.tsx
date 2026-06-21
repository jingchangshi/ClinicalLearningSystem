import Link from "next/link";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { LearningEvidenceCards } from "@/components/LearningEvidenceCards";
import { RecommendedTaskCard } from "@/components/RecommendedTaskCard";
import { getTeacherStudentProfile } from "@/lib/api";

export default async function TeacherStudentProfilePage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = await params;
  const data = await getTeacherStudentProfile(studentId);

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Learner Profile</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">{data.student.name} 学习画像</h1>
          <p className="mt-2 text-slate-600">汇总五模块学习证据、能力画像、推荐任务与成长趋势，供教师精准干预。</p>
        </div>
        <Link href="/teacher/dashboard" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
          返回教师驾驶舱
        </Link>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">八维能力画像</h2>
          <CompetencyRadar data={data.competency.expanded_chart_data} />
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">成长趋势</h2>
          <div className="mt-4 space-y-3">
            {data.growth_trend.length ? (
              data.growth_trend.slice(-6).map((item) => (
                <div key={item.event_id} className="rounded-xl bg-slate-50 p-3 text-sm">
                  <div className="font-semibold">{item.module_type} · {item.average_after}</div>
                  <div className="mt-1 text-slate-500">得分：{item.score ?? "待评分"}</div>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">暂无学习证据事件。</p>
            )}
          </div>
        </section>
      </div>

      <LearningEvidenceCards evidence={data.learning_evidence} />

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">推荐训练任务</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.recommended_tasks.map((task) => (
            <RecommendedTaskCard key={`${task.type}-${task.id}`} task={task} href={taskHref(task.type, task.id, Number(studentId))} />
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">学习证据事件</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2">模块</th>
                <th className="px-3 py-2">分数</th>
                <th className="px-3 py-2">能力更新</th>
                <th className="px-3 py-2">时间</th>
              </tr>
            </thead>
            <tbody>
              {data.evidence_events.map((event) => (
                <tr key={event.id} className="border-b border-slate-100">
                  <td className="px-3 py-3">{event.module_type}</td>
                  <td className="px-3 py-3">{event.score ?? "待评分"}</td>
                  <td className="px-3 py-3">{Object.keys(event.competency_updates).join("、")}</td>
                  <td className="px-3 py-3">{String(event.created_at).slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function taskHref(type: string, id: number, studentId: number) {
  const paths: Record<string, string> = {
    knowledge_unit: `/student/knowledge/${id}`,
    clinical_skill: `/student/skills/${id}`,
    case: `/student/case/${id}`,
    guideline: `/student/guidelines/${id}`,
    sp_case: `/student/sp/${id}`,
  };
  void studentId;
  return paths[type] ?? "/student/dashboard";
}
