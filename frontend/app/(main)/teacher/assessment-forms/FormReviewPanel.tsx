"use client";

/**
 * Independent form review.
 *
 * A teacher only ever sees forms the study admin invited them to review — an
 * exam is confidential before it runs — and never the other reviewer's opinion,
 * so the two reviews really are independent. The admin checks both before
 * publishing.
 */
import { useCallback, useEffect, useState } from "react";

import {
  AnswerKeyView,
  Button,
  Card,
  EmptyHint,
  Feedback,
  Pill,
  RubricView,
  StageBlock,
} from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  formReviewStatusLabel,
  listReviewableAssessmentForms,
  recordAssessmentFormReview,
  type ReviewableForm,
} from "@/lib/assessmentApi";

export function FormReviewPanel() {
  const [forms, setForms] = useState<ReviewableForm[] | null>(null);
  const [comments, setComments] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setForms(await listReviewableAssessmentForms());
      setError(null);
    } catch (reason) {
      setForms([]);
      setError(assessmentErrorMessage(reason));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(form: ReviewableForm, decision: "approve" | "reject") {
    const comment = (comments[form.id] ?? "").trim();
    if (comment.length < 2) {
      setError("请先填写审核意见（医学核对、修改意见或确认理由），至少 2 个字符。");
      return;
    }
    setBusyId(form.id);
    setError(null);
    try {
      await recordAssessmentFormReview(form.id, decision, comment);
      setMessage(
        decision === "approve"
          ? `已记录你对《${form.title}》的审核通过意见。管理员核对两位教师结论后才会发布。`
          : `已记录你对《${form.title}》的驳回意见，该题本进入修改状态。`,
      );
      await load();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      {forms === null ? (
        <p className="text-sm text-slate-500" role="status">
          正在加载待审核题本…
        </p>
      ) : forms.length === 0 ? (
        <Card title="待我审核的题本">
          <EmptyHint>
            当前没有指派给你的待审题本。题本在运行前属于保密材料，只有被指派的教师才能看到内容；
            如需参与审核，请联系研究管理员在题本上指派你的教师账号。
          </EmptyHint>
        </Card>
      ) : (
        forms.map((form) => (
          <Card
            key={form.id}
            title={`${form.code}（v${form.version}）：${form.title}`}
            description="请核对医学准确性、阶段信息释放顺序、参考答案与六维评分锚点。你可以独立作出结论，另一位审核教师的意见不会显示在这里。"
            actions={<Pill tone={form.reviewed_by_me ? "clinic" : "warn"}>{formReviewStatusLabel(form.review_status)}</Pill>}
          >
            <ol className="space-y-3">
              {form.stages.map((stage, index) => (
                <li key={index}>
                  <StageBlock stage={stage} index={index} />
                </li>
              ))}
            </ol>

            <div className="mt-4 space-y-3">
              <RubricView rubric={form.rubric} />
              <AnswerKeyView answerKey={form.answer_key} />
            </div>

            {form.reviewed_by_me ? (
              <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
                本账号已提交审核结论（{form.my_decision === "approve" ? "审核通过" : "驳回修改"}），不能重复提交。
                如需改变结论，请联系研究管理员创建新版本后重新指派。
              </p>
            ) : (
              <>
                <label className="mt-4 block text-sm">
                  <span className="text-slate-600">审核意见（医学核对结论、需要修改的内容）</span>
                  <textarea
                    rows={3}
                    aria-label={`${form.code}审核意见`}
                    value={comments[form.id] ?? ""}
                    onChange={(event) => setComments((current) => ({ ...current, [form.id]: event.target.value }))}
                    className="mt-1 w-full rounded-md border border-slate-300 p-2"
                    placeholder="例如：抗 SSA 阴性一节与「疑似原发性干燥综合征」的表述一致；第 3 阶段建议补充眼科客观检查的适用条件。"
                  />
                </label>
                <div className="mt-3 flex flex-wrap gap-3">
                  <Button onClick={() => void decide(form, "approve")} disabled={busyId === form.id}>
                    审核通过这一版内容
                  </Button>
                  <Button tone="danger" onClick={() => void decide(form, "reject")} disabled={busyId === form.id}>
                    驳回并退回修改
                  </Button>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  审核结论会被记录：审核人、时间、结论以及你当时看到的内容指纹。内容一旦变更，原审核结论自动失效。
                </p>
              </>
            )}
          </Card>
        ))
      )}
    </div>
  );
}
