import Link from "next/link";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { ScoreBarChart } from "@/components/ScoreBarChart";
import { getResult } from "@/lib/api";
import { abilityLabel, evaluationModeLabel } from "@/lib/abilityLabels";

export default async function ResultPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const resolvedParams = await params;
  const result = await getResult(resolvedParams.sessionId);
  const aiEvaluation = result.score.evaluation_mode === "ai" && !result.score.degraded;
  const modeLabel = evaluationModeLabel(result.score.evaluation_mode, result.score.degraded);
  const dimensions = Object.entries(result.score.evaluation_detail.dimensions ?? {});

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">{result.case.title}</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">评分反馈</h1>
            <p className="mt-2 max-w-3xl text-slate-600">{result.score.feedback}</p>
            <p
              data-testid="evaluation-mode"
              className={`mt-3 inline-flex rounded-md px-3 py-1 text-xs font-medium ${
                aiEvaluation ? "bg-teal-50 text-teal-800" : "bg-amber-50 text-amber-800"
              }`}
            >
              {modeLabel}
              {aiEvaluation && result.score.model ? `（${result.score.model}）` : ""}
            </p>
            <p className="mt-2 text-xs text-slate-500">形成性评价，仅供教学参考，最终评价由教师确认。</p>
            <p className="mt-1 text-xs font-medium text-slate-600">
              {result.score.teacher_confirmed_score === null ? "待教师确认" : "教师已确认"}
            </p>
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

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">评分依据、遗漏点与安全提示</h2>
        <p className="mt-2 text-sm text-slate-600">
          {modeLabel}
          {result.score.teacher_confirmed_score !== null ? `；教师确认总分：${result.score.teacher_confirmed_score}` : ""}
        </p>
        {dimensions.map(([dimension, detail]) => (
          <div key={dimension} className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
            <div className="flex flex-wrap items-center gap-2 font-medium">
              <span>{abilityLabel(dimension)}</span>
              <span className="rounded bg-white px-2 py-0.5 text-xs text-slate-500">
                {detail.source === "ai" ? "AI 评价" : "规则评价"} · 置信度 {Math.round((detail.confidence ?? 0) * 100)}%
              </span>
            </div>
            <p className="mt-1">{detail.feedback}</p>
            {detail.evidence.length ? <p className="mt-1">评分依据：{detail.evidence.join("；")}</p> : null}
            {detail.missing_points.length ? <p className="mt-1">遗漏点：{detail.missing_points.join("；")}</p> : null}
          </div>
        ))}
        {result.score.safety_flags.length ? (
          <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-alert">
            安全提示：{result.score.safety_flags.join("；")}
          </p>
        ) : null}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">改进建议</h2>
        <p className="mt-3 text-sm leading-6 text-slate-700">
          {result.score.evaluation_detail.overall_feedback ?? result.score.feedback}
        </p>
        {result.score.evaluation_detail.priority_gaps?.length ? (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {result.score.evaluation_detail.priority_gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        ) : null}
      </section>

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
        href="/student/pathway"
        className="inline-flex rounded-md bg-clinic px-4 py-2 text-white"
      >
        返回学习路径
      </Link>
    </div>
  );
}
