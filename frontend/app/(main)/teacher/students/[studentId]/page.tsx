import Link from "next/link";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { GrowthTrendChart, changeText } from "@/components/GrowthTrendChart";
import { LearningEvidenceCards } from "@/components/LearningEvidenceCards";
import { RecommendedTaskCard } from "@/components/RecommendedTaskCard";
import { getTeacherStudentProfile } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

// A teacher reads the newest few events; the rest are one click away and stay
// in the database. This is a view rule, not a data rule.
const EVIDENCE_PREVIEW_COUNT = 10;
const CHANGES_SHOWN_PER_ROW = 3;

export default async function TeacherStudentProfilePage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = await params;
  const data = await getTeacherStudentProfile(studentId);
  const events = data.evidence_events;
  const preview = events.slice(0, EVIDENCE_PREVIEW_COUNT);
  const rest = events.slice(EVIDENCE_PREVIEW_COUNT);

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold tracking-[0.22em] text-clinic">教学驾驶舱 · 学生画像</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">{data.student.name} 学习画像</h1>
          <p className="mt-2 text-slate-600">
            {data.student.class_name} · 当前{data.student.current_stage_label} · 汇总五模块学习证据、能力画像、推荐任务与阶段性学习表现。
          </p>
        </div>
        <Link href="/teacher/dashboard" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
          返回教学驾驶舱
        </Link>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.15fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">九维能力画像</h2>
          <CompetencyRadar data={data.competency.expanded_chart_data} />
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">阶段性学习表现趋势</h2>
          <p className="mt-1 text-sm text-slate-500">
            每次训练的总得分（0–100）。鼠标悬停可看到该次训练带来哪些能力变化。
          </p>
          <GrowthTrendChart points={data.growth_trend} />
        </section>
      </div>

      <LearningEvidenceCards evidence={data.learning_evidence} />

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">学习证据事件</h2>
          <p className="text-sm text-slate-500">
            共 {events.length} 条，默认显示最近 {preview.length} 条
          </p>
        </div>
        <EvidenceTable events={preview} />
        {rest.length ? (
          <details className="mt-4">
            <summary className="cursor-pointer text-sm font-semibold text-clinic">
              查看全部 {events.length} 条学习证据
            </summary>
            <EvidenceTable events={rest} />
          </details>
        ) : null}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">推荐训练任务</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.recommended_tasks.map((task) => (
            <RecommendedTaskCard key={`${task.type}-${task.id}`} task={task} href={taskHref(task.type, task.id)} />
          ))}
        </div>
      </section>
    </div>
  );
}

type EvidenceEvent = Awaited<ReturnType<typeof getTeacherStudentProfile>>["evidence_events"][number];

function EvidenceTable({ events }: { events: EvidenceEvent[] }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-3 py-2">学习活动</th>
            <th className="px-3 py-2">训练内容</th>
            <th className="px-3 py-2">训练得分</th>
            <th className="px-3 py-2">能力变化</th>
            <th className="px-3 py-2">完成时间</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => {
            const changes = [...event.competency_changes].sort(
              (a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0),
            );
            return (
              <tr key={event.id} className="border-b border-slate-100">
                <td className="px-3 py-3 font-medium text-ink">{event.module_label}</td>
                <td className="px-3 py-3 text-slate-600">{event.activity_title ?? event.event_label}</td>
                <td className="px-3 py-3 font-semibold text-clinic">{event.score ?? "待评分"}</td>
                <td className="px-3 py-3 text-slate-600">
                  {changes.length ? (
                    <ul className="space-y-0.5">
                      {changes.slice(0, CHANGES_SHOWN_PER_ROW).map((change) => (
                        <li key={change.key}>{changeText(change)}</li>
                      ))}
                      {changes.length > CHANGES_SHOWN_PER_ROW ? (
                        <li className="text-slate-400">另有 {changes.length - CHANGES_SHOWN_PER_ROW} 项能力更新</li>
                      ) : null}
                    </ul>
                  ) : (
                    <span className="text-slate-400">无能力变化记录</span>
                  )}
                </td>
                <td className="px-3 py-3 text-slate-600">{formatDateTime(event.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function taskHref(type: string, id: number) {
  const paths: Record<string, string> = {
    knowledge_unit: `/student/knowledge/${id}`,
    clinical_skill: `/student/skills/${id}`,
    case: `/student/case/${id}`,
    guideline: `/student/guidelines/${id}`,
    sp_case: `/student/sp/${id}`,
  };
  return paths[type] ?? "/student/dashboard";
}
