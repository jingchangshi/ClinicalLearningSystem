import Link from "next/link";

import { listTeacherScoreReviews } from "@/lib/api";

export default async function ScoreReviewPage() {
  const reviews = await listTeacherScoreReviews();

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Teacher Score Review</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">教师评分复核</h1>
          <p className="mt-2 text-slate-600">AI形成性评价仅供教学参考，最终评价由教师确认。</p>
        </div>
        <Link href="/teacher/dashboard" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
          返回教师驾驶舱
        </Link>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">复核记录</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2">证据事件</th>
                <th className="px-3 py-2">AI评分</th>
                <th className="px-3 py-2">教师评分</th>
                <th className="px-3 py-2">差值</th>
                <th className="px-3 py-2">备注</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((review) => (
                <tr key={review.id} className="border-b border-slate-100">
                  <td className="px-3 py-3">{review.evidence_event_id}</td>
                  <td className="px-3 py-3">{review.ai_score}</td>
                  <td className="px-3 py-3">{review.teacher_score}</td>
                  <td className="px-3 py-3">{review.agreement_delta}</td>
                  <td className="px-3 py-3">{review.comment}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!reviews.length ? <p className="mt-4 text-sm text-slate-500">暂无复核记录，可通过 API 创建复核记录。</p> : null}
        </div>
      </section>
    </div>
  );
}
