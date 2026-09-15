import Link from "next/link";

import { evaluationModeShort } from "@/lib/abilityLabels";
import { getLearningHistory } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

/**
 * 学习记录 — the learner's own case history.
 *
 * A historic read of `StudentAnswer` / `TutorTurn` / `Score`; opening this page
 * never starts a model call, and each row links to the same review page the
 * learner saw right after submitting.
 */
export default async function StudentHistoryPage() {
  const data = await getLearningHistory();

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold tracking-[0.22em] text-clinic">学习记录</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">我的病例学习记录</h1>
          <p className="mt-2 text-slate-600">
            {data.student.name} · {data.student.class_name} · 当前{data.current_stage_label}
          </p>
        </div>
        <div className="rounded-full bg-teal-50 px-4 py-2 text-sm font-semibold text-clinic">
          已完成病例训练 {data.count} 次
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        {data.items.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm" data-testid="history-table">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-3 py-2">病例名称</th>
                  <th className="px-3 py-2">训练时间</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">总分</th>
                  <th className="px-3 py-2">评价方式</th>
                  <th className="px-3 py-2">导师互动</th>
                  <th className="px-3 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.session_id} className="border-b border-slate-100">
                    <td className="px-3 py-3 font-medium text-ink">{item.case_title}</td>
                    <td className="px-3 py-3 text-slate-600">{formatDateTime(item.completed_at ?? item.started_at)}</td>
                    <td className="px-3 py-3">
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                        {item.status_label}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-semibold text-clinic">{item.total_score ?? "待评分"}</td>
                    <td className="px-3 py-3 text-slate-600">
                      {evaluationModeShort(item.evaluation_mode, item.degraded)}
                    </td>
                    <td className="px-3 py-3 text-slate-600">{item.tutor_turn_count} 次导师互动</td>
                    <td className="px-3 py-3">
                      <Link href={`/student/result/${item.session_id}`} className="text-clinic hover:underline">
                        查看学习过程
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            还没有完成的病例训练。完成一次病例推理训练后，这里会保留你的五阶段回答、AI 导师对话和评分反馈。
          </p>
        )}
      </section>
    </div>
  );
}
