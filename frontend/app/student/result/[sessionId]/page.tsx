import Link from "next/link";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { ScoreBarChart } from "@/components/ScoreBarChart";
import { getResult } from "@/lib/api";

export default async function ResultPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const resolvedParams = await params;
  const result = await getResult(resolvedParams.sessionId);

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">{result.case.title}</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">评分反馈</h1>
            <p className="mt-2 max-w-3xl text-slate-600">{result.score.feedback}</p>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-500">总分</div>
            <div className="text-4xl font-semibold text-clinic">{result.score.total_score}</div>
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">六项分项评分</h2>
          <ScoreBarChart data={result.score.chart_data} />
        </section>
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">更新后的能力画像</h2>
          <CompetencyRadar data={result.competency.chart_data} />
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">主要优点</h2>
          <p className="mt-3 text-sm leading-6 text-slate-700">{result.score.strengths}</p>
        </section>
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">主要不足</h2>
          <p className="mt-3 text-sm leading-6 text-slate-700">{result.score.weaknesses}</p>
        </section>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">下一步推荐病例</h2>
        {result.recommendation ? (
          <div className="mt-4 rounded-md bg-slate-50 p-4">
            <div className="font-medium">{result.recommendation.case.title}</div>
            <p className="mt-1 text-sm text-slate-600">{result.recommendation.recommendation_reason}</p>
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">推理链回顾</h2>
        <div className="mt-4 space-y-3">
          {result.answers.map((item) => (
            <div key={item.id} className="rounded-md bg-slate-50 p-3">
              <div className="text-sm font-medium">{item.step}</div>
              <p className="mt-1 text-sm text-slate-700">{item.answer_text}</p>
            </div>
          ))}
        </div>
      </section>

      <Link
        href={`/student/pathway?studentId=${result.session.student.id}`}
        className="inline-flex rounded-md bg-clinic px-4 py-2 text-white"
      >
        返回学习路径
      </Link>
    </div>
  );
}
