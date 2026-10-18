"use client";

/**
 * Blinded rater queue.
 *
 * What appears here is exactly what the rating API returns: an opaque blind
 * code, the case, the (best-effort de-identified) answers, the rubric and the
 * anchors. Student, cohort, group, timepoint, form identity and the other
 * rater's scores are not fetched, so they cannot be rendered by accident.
 */
import { useCallback, useEffect, useState } from "react";

import {
  AnswerKeyView,
  Button,
  Card,
  DimensionScoreInputs,
  EmptyHint,
  Feedback,
  IDENTIFIER_REDACTION_NOTE,
  Pill,
  RubricView,
  StageBlock,
  weightedTotal,
} from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  getBlindDetail,
  getBlindQueue,
  submitBlindReview,
  STUDY_DIMENSIONS,
  type BlindDetail,
  type BlindQueueItem,
} from "@/lib/assessmentApi";

function emptyScores(): Record<string, number> {
  return Object.fromEntries(STUDY_DIMENSIONS.map(([key]) => [key, Number.NaN])) as Record<string, number>;
}

function scoresComplete(scores: Record<string, number>): boolean {
  return STUDY_DIMENSIONS.every(([key]) => Number.isFinite(scores[key]) && scores[key] >= 0 && scores[key] <= 100);
}

export function BlindQueuePanel() {
  const [queue, setQueue] = useState<BlindQueueItem[] | null>(null);
  const [detail, setDetail] = useState<BlindDetail | null>(null);
  const [scores, setScores] = useState<Record<string, number>>(emptyScores);
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const loadQueue = useCallback(async () => {
    try {
      setQueue(await getBlindQueue());
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
      const next = await getBlindDetail(blindCode);
      setDetail(next);
      setScores(emptyScores());
      setRationale("");
      setConfirming(false);
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!detail) return;
    if (!scoresComplete(scores)) {
      setError("六个维度都必须填写 0–100 之间的分数。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await submitBlindReview(detail.blind_code, scores, rationale.trim() || undefined);
      setDetail(null);
      setConfirming(false);
      setMessage(`评分已锁定（加权总分 ${result.total_score}）。提交后不能修改，也看不到另一位评分者的分数。`);
      await loadQueue();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  const preview = weightedTotal(scores, detail?.rubric);
  const reviewed = queue?.filter((item) => item.reviewed).length ?? 0;
  const pending = (queue?.length ?? 0) - reviewed;

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      {detail ? (
        <Card
          title={`匿名答卷 ${detail.blind_code.slice(0, 8)}…`}
          description="评分依据：病例资料、学生作答与评分锚点。本页不显示学生身份、教学组别、批次、考核时点与另一位评分者的分数。"
          actions={
            <Button tone="secondary" onClick={() => setDetail(null)} disabled={busy}>
              返回队列
            </Button>
          }
        >
          <div className="flex flex-wrap gap-2">
            {detail.already_reviewed ? <Pill tone="warn">你已提交并锁定本答卷评分</Pill> : <Pill tone="clinic">待评分</Pill>}
            {detail.identifier_redactions > 0 ? <Pill>已自动去标识 {detail.identifier_redactions} 处</Pill> : null}
          </div>
          {detail.identifier_redactions > 0 ? (
            <p className="mt-2 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">{IDENTIFIER_REDACTION_NOTE}</p>
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

          {detail.already_reviewed ? (
            <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
              本答卷的评分已由你提交并锁定。系统不回显已锁定的评分记录，也不显示另一位评分者的分数。
              如需更正，请联系研究管理员，由其按审计流程作废该评分记录。
            </p>
          ) : (
            <>
              <h3 className="mt-5 font-semibold text-ink">六维独立评分（0–100）</h3>
              <p className="mt-1 text-sm text-slate-600">
                请独立完成评分，不要与他人讨论。提交后立即锁定，不能修改。
              </p>
              <div className="mt-3">
                <DimensionScoreInputs scores={scores} onChange={setScores} rubric={detail.rubric} disabled={busy} />
              </div>
              <label className="mt-4 block text-sm">
                <span className="text-slate-600">评分依据说明（可选，保存为评分记录的一部分）</span>
                <textarea
                  rows={3}
                  aria-label="评分依据说明"
                  value={rationale}
                  onChange={(event) => setRationale(event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2"
                />
              </label>
              <p className="mt-3 text-sm text-slate-600">
                按当前量表权重的参考总分：<span className="font-semibold text-ink">{preview ?? "—"}</span>
                <span className="ml-2 text-xs text-slate-500">（最终总分由服务器按题本量表计算并保存）</span>
              </p>
              {confirming ? (
                <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-4">
                  <p className="text-sm text-amber-900">确认提交这六个维度的评分？提交后立即锁定，不能修改。</p>
                  <div className="mt-3 flex flex-wrap gap-3">
                    <Button onClick={() => void submit()} disabled={busy}>
                      {busy ? "正在提交…" : "确认提交并锁定"}
                    </Button>
                    <Button tone="secondary" onClick={() => setConfirming(false)} disabled={busy}>
                      返回检查
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-5">
                  <Button onClick={() => setConfirming(true)} disabled={busy || !scoresComplete(scores)}>
                    提交独立评分
                  </Button>
                </div>
              )}
            </>
          )}
        </Card>
      ) : (
        <Card
          title="我的盲评队列"
          description="队列顺序由服务器按评分者与盲评编码打乱，与提交顺序、批次和考核时点无关。"
          actions={
            <Pill tone={pending > 0 ? "warn" : "clinic"}>
              待评 {pending} / 共 {queue?.length ?? 0}
            </Pill>
          }
        >
          {queue === null ? (
            <p className="text-sm text-slate-500" role="status">
              正在加载队列…
            </p>
          ) : queue.length === 0 ? (
            <EmptyHint>当前没有分配给你的匿名答卷。答卷提交后才会进入盲评队列。</EmptyHint>
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
                      <span className="font-medium text-ink">第 {index + 1} 份匿名答卷</span>
                      <span className="ml-2 font-mono text-xs text-slate-500">{item.blind_code.slice(0, 8)}…</span>
                      <span className="mt-1 block text-xs text-slate-500">
                        不含姓名、学号、组别、批次与时点
                      </span>
                    </span>
                    <Pill tone={item.reviewed ? "clinic" : "warn"}>{item.reviewed ? "已评分并锁定" : "待评分"}</Pill>
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
