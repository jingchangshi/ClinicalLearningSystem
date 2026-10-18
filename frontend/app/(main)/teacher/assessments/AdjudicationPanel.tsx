"use client";

/**
 * Disagreement adjudication.
 *
 * The adjudicator sees both raters' six dimensions and their delta, and records
 * an independent adjudicated score. Neither original rating is editable here —
 * the API only accepts a new adjudication row.
 */
import { useCallback, useEffect, useState } from "react";

import {
  AnswerKeyView,
  Button,
  Card,
  DimensionComparison,
  DimensionScoreInputs,
  DisagreementView,
  EmptyHint,
  Feedback,
  Pill,
  RubricView,
  StageBlock,
  weightedTotal,
} from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  getAdjudicationDetail,
  getAdjudicationQueue,
  STUDY_DIMENSIONS,
  submitAdjudication,
  type AdjudicationDetail,
  type AdjudicationQueueItem,
} from "@/lib/assessmentApi";

function emptyScores(): Record<string, number> {
  return Object.fromEntries(STUDY_DIMENSIONS.map(([key]) => [key, Number.NaN])) as Record<string, number>;
}

function scoresComplete(scores: Record<string, number>): boolean {
  return STUDY_DIMENSIONS.every(([key]) => Number.isFinite(scores[key]) && scores[key] >= 0 && scores[key] <= 100);
}

export function AdjudicationPanel() {
  const [queue, setQueue] = useState<AdjudicationQueueItem[] | null>(null);
  const [detail, setDetail] = useState<AdjudicationDetail | null>(null);
  const [scores, setScores] = useState<Record<string, number>>(emptyScores);
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadQueue = useCallback(async () => {
    try {
      setQueue(await getAdjudicationQueue());
      setError(null);
    } catch (reason) {
      setQueue([]);
      setError(assessmentErrorMessage(reason));
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  async function open(blindCode: string) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setDetail(await getAdjudicationDetail(blindCode));
      setScores(emptyScores());
      setRationale("");
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!detail) return;
    if (!scoresComplete(scores)) {
      setError("裁决评分必须填写六个维度（0–100）。");
      return;
    }
    if (rationale.trim().length < 5) {
      setError("请填写裁决理由（至少 5 个字），这是裁决记录的必要组成部分。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await submitAdjudication(detail.blind_code, scores, rationale.trim());
      setDetail(null);
      setMessage(`裁决已记录（加权总分 ${result.total_score}）。两位评分者的原始评分记录未被改动。`);
      await loadQueue();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  const preview = weightedTotal(scores, detail?.rubric);
  const pending = queue?.filter((item) => !item.adjudicated).length ?? 0;

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      {detail ? (
        <Card
          title={`裁决：匿名答卷 ${detail.blind_code.slice(0, 8)}…`}
          description="两位评分者的六维评分与差值如下。裁决形成独立记录，不改写原始评分。"
          actions={
            <Button tone="secondary" onClick={() => setDetail(null)} disabled={busy}>
              返回裁决队列
            </Button>
          }
        >
          <DisagreementView disagreement={detail.disagreement} />

          <div className="mt-4 overflow-x-auto">
            <DimensionComparison reviews={detail.reviews} disagreement={detail.disagreement} />
          </div>

          {detail.reviews.some((review) => review.rationale) ? (
            <div className="mt-3 space-y-2">
              {detail.reviews
                .filter((review) => review.rationale)
                .map((review) => (
                  <p key={review.label} className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    <span className="font-medium">{review.label === "rater_1" ? "评分者 1" : "评分者 2"} 的评分依据：</span>
                    {review.rationale}
                  </p>
                ))}
            </div>
          ) : null}

          <ol className="mt-4 space-y-3">
            {detail.stages.map((stage, index) => (
              <li key={index}>
                <StageBlock
                  stage={stage}
                  index={index}
                  answer={detail.answers.find((item) => item.index === index)?.answer_text ?? "（该阶段无作答内容）"}
                />
              </li>
            ))}
          </ol>

          <div className="mt-4 space-y-3">
            <RubricView rubric={detail.rubric} />
            <AnswerKeyView answerKey={detail.answer_key} />
          </div>

          {detail.already_adjudicated ? (
            <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
              本答卷已经完成裁决。裁决记录不可修改；如需更正，请联系研究管理员按审计流程处理。
            </p>
          ) : (
            <>
              <h3 className="mt-5 font-semibold text-ink">裁决评分（0–100）</h3>
              <p className="mt-1 text-sm text-slate-600">
                请参考两位评分者的依据，独立给出你判断的六维分数。该裁决结果将成为最终成绩的来源。
              </p>
              <div className="mt-3">
                <DimensionScoreInputs scores={scores} onChange={setScores} rubric={detail.rubric} disabled={busy} />
              </div>
              <label className="mt-4 block text-sm">
                <span className="text-slate-600">裁决理由（必填，至少 5 个字）</span>
                <textarea
                  rows={3}
                  aria-label="裁决理由"
                  value={rationale}
                  onChange={(event) => setRationale(event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2"
                  placeholder="例如：评分者 2 未考虑抗 SSA 阴性对分类标准的影响，据此调整鉴别诊断与循证安全两项。"
                />
              </label>
              <p className="mt-3 text-sm text-slate-600">
                按当前量表权重的参考总分：<span className="font-semibold text-ink">{preview ?? "—"}</span>
              </p>
              <div className="mt-4">
                <Button
                  onClick={() => void submit()}
                  disabled={busy || !scoresComplete(scores) || rationale.trim().length < 5}
                >
                  {busy ? "正在提交…" : "提交裁决"}
                </Button>
              </div>
            </>
          )}
        </Card>
      ) : (
        <Card
          title="待裁决分歧"
          description="只有两位评分者都完成评分、且差值超过阈值的答卷才会进入这里。"
          actions={<Pill tone={pending > 0 ? "warn" : "clinic"}>待裁决 {pending}</Pill>}
        >
          {queue === null ? (
            <p className="text-sm text-slate-500" role="status">
              正在加载裁决队列…
            </p>
          ) : queue.length === 0 ? (
            <EmptyHint>当前没有需要你裁决的分歧答卷。</EmptyHint>
          ) : (
            <ul className="space-y-2">
              {queue.map((item, index) => (
                <li key={item.blind_code}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void open(item.blind_code)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-200 p-3 text-left hover:border-clinic disabled:opacity-50"
                  >
                    <span>
                      <span className="font-medium text-ink">第 {index + 1} 份分歧答卷</span>
                      <span className="ml-2 font-mono text-xs text-slate-500">{item.blind_code.slice(0, 8)}…</span>
                    </span>
                    <Pill tone={item.adjudicated ? "clinic" : "warn"}>{item.adjudicated ? "已裁决" : "待裁决"}</Pill>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
