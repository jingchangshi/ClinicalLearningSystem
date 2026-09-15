import Link from "next/link";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { ScoreBarChart } from "@/components/ScoreBarChart";
import { getResult } from "@/lib/api";
import { abilityLabel, evaluationModeLabel } from "@/lib/abilityLabels";
import { formatDateTime } from "@/lib/format";

export default async function ResultPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const resolvedParams = await params;
  const result = await getResult(resolvedParams.sessionId);
  const aiEvaluation = result.score.evaluation_mode === "ai" && !result.score.degraded;
  const modeLabel = evaluationModeLabel(result.score.evaluation_mode, result.score.degraded);
  const dimensions = Object.entries(result.score.evaluation_detail.dimensions ?? {});
  const durationMinutes = trainingMinutes(result.session.started_at, result.session.completed_at);

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">{result.case.title}</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">病例训练评分反馈</h1>
            <p className="mt-1 text-sm text-slate-500">
              训练时间 {formatDateTime(result.session.started_at)}
              {durationMinutes === null ? "" : ` · 用时约 ${durationMinutes} 分钟`}
            </p>
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

      <section className="rounded-lg border border-slate-200 bg-white p-5" data-testid="reasoning-review">
        <h2 className="font-semibold">我的病例推理过程</h2>
        <p className="mt-1 text-sm text-slate-500">
          逐阶段回顾你当时的最终回答，以及 AI 导师的追问和你的回复。这是保存在服务器上的历史记录，重新打开页面看到的内容与你当时提交时一致。
        </p>
        <ol className="mt-4 space-y-4">
          {result.reasoning_review.map((step, index) => (
            <li key={step.step} className="rounded-xl border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold text-ink">
                  {index + 1}. {step.step_title}
                </h3>
                <span className="text-xs text-slate-500">{formatDateTime(step.answered_at)}</span>
              </div>
              <div className="mt-3 rounded-lg bg-slate-50 p-3">
                <p className="text-xs font-semibold text-slate-500">我的最终回答</p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
                  {step.answer_text || "本阶段未作答"}
                </p>
              </div>
              {step.tutor_turns.length ? (
                <div className="mt-3">
                  <p className="text-xs font-semibold text-slate-500">AI 导师追问与我的回复</p>
                  <div className="mt-2 space-y-2">
                    {step.tutor_turns.map((turn, turnIndex) => (
                      <div
                        key={`${turn.role}-${turnIndex}`}
                        className={`flex ${turn.role === "tutor" ? "justify-start" : "justify-end"}`}
                      >
                        <div
                          className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
                            turn.role === "tutor"
                              ? "bg-teal-50 text-teal-900"
                              : "bg-clinic text-white"
                          }`}
                        >
                          <span className="block text-xs opacity-80">
                            {turn.role === "tutor" ? "AI 导师" : "我"} · {formatDateTime(turn.created_at)}
                          </span>
                          <span className="mt-1 block whitespace-pre-wrap">{turn.message}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-400">本阶段没有 AI 导师追问记录。</p>
              )}
            </li>
          ))}
        </ol>
      </section>

      <div className="flex flex-wrap gap-3">
        <Link href="/student/history" className="inline-flex rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
          返回学习记录
        </Link>
        <Link
          href="/student/pathway"
          className="inline-flex rounded-md bg-clinic px-4 py-2 text-white"
        >
          返回学习路径
        </Link>
      </div>
    </div>
  );
}

/** Whole minutes between two naive UTC timestamps; null when either is missing. */
function trainingMinutes(startedAt: string | null, completedAt: string | null): number | null {
  if (!startedAt || !completedAt) return null;
  const millis = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  if (!Number.isFinite(millis) || millis < 0) return null;
  return Math.max(1, Math.round(millis / 60000));
}
