"use client";

/**
 * Study-administrator view of题本: review status, reviewer assignment, publication.
 *
 * The admin verifies and publishes; the publish endpoint takes no reviewer input,
 * so nothing here can supply or forge a teacher's decision. Reviewer and author
 * identities are shown by name from the staff directory, never as database ids.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  AnswerKeyView,
  Button,
  Card,
  EmptyHint,
  Feedback,
  Moment,
  Pill,
  RubricView,
  StageBlock,
} from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  assignAssessmentFormReviewers,
  formReviewStatusLabel,
  getAssessmentFormDetail,
  listAllAssessmentForms,
  listAssessmentStaff,
  publishAssessmentForm,
  type FormDetail,
  type FormSummary,
  type StaffAccount,
} from "@/lib/assessmentApi";

export function FormAdminPanel() {
  const [forms, setForms] = useState<FormSummary[] | null>(null);
  const [staff, setStaff] = useState<StaffAccount[]>([]);
  const [staffUnavailable, setStaffUnavailable] = useState(false);
  const [selected, setSelected] = useState<FormDetail | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadForms = useCallback(async () => {
    try {
      setForms(await listAllAssessmentForms());
      setError(null);
    } catch (reason) {
      setForms([]);
      setError(assessmentErrorMessage(reason));
    }
  }, []);

  useEffect(() => {
    void loadForms();
    listAssessmentStaff()
      .then(setStaff)
      .catch(() => setStaffUnavailable(true));
  }, [loadForms]);

  const staffById = useMemo(() => new Map(staff.map((account) => [account.user_id, account])), [staff]);
  const teachers = useMemo(() => staff.filter((account) => account.role === "teacher"), [staff]);
  const nameOf = useCallback(
    (userId: number | null) => {
      if (userId === null) return "（未知账号）";
      return staffById.get(userId)?.display_name ?? `账号 #${userId}`;
    },
    [staffById],
  );

  async function open(form: FormSummary) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const detail = await getAssessmentFormDetail(form.id);
      setSelected(detail);
      setPicked(detail.assigned_reviewers);
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveReviewers() {
    if (!selected) return;
    const chosen = picked.filter((id) => staffById.get(id)?.role === "teacher" && id !== selected.author_user_id);
    if (chosen.length < 2) {
      setError("至少需要两位不同的真实教师账号作为审核人（作者本人不能担任审核人）。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await assignAssessmentFormReviewers(selected.id, chosen);
      setMessage("已指派审核人。被指派的教师会在「病例审核」页看到这份题本。");
      await open(selected);
      await loadForms();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await publishAssessmentForm(selected.id);
      setMessage("已发布该题本版本。发布后内容冻结，考试将按这一版执行。");
      await open(selected);
      await loadForms();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  const approvalsOfCurrent = selected
    ? selected.reviews.filter((review) => review.decision === "approve" && review.matches_current_content).length
    : 0;
  const editable = selected
    ? selected.review_status === "PENDING_REAL_REVIEW" || selected.review_status === "CHANGES_REQUESTED"
    : false;

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      {staffUnavailable ? (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          人员目录接口（/api/assessments/admin/staff）当前不可用，因此无法按姓名指派审核人。
          这是本页唯一的降级项：题本列表、审核状态与发布仍然可用。请让后端提供该接口后刷新本页。
        </p>
      ) : null}

      <Card
        title="全部题本版本"
        description="每一版内容都是独立的：已发布版本冻结，修改医学内容会产生新的版本号。"
        actions={
          <Button tone="secondary" onClick={() => void loadForms()} disabled={busy}>
            刷新
          </Button>
        }
      >
        {forms === null ? (
          <p className="text-sm text-slate-500" role="status">
            正在加载题本列表…
          </p>
        ) : forms.length === 0 ? (
          <EmptyHint>还没有创建任何考核题本。可由教师或管理员在上方「创建题本」中建立草案。</EmptyHint>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-3 py-2">编号 / 版本</th>
                  <th className="px-3 py-2">名称</th>
                  <th className="px-3 py-2">审核状态</th>
                  <th className="px-3 py-2">发布时间</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {forms.map((form) => (
                  <tr key={form.id} className="border-b border-slate-100">
                    <td className="px-3 py-2 font-mono text-xs">
                      {form.code} · v{form.version}
                    </td>
                    <td className="px-3 py-2">{form.title}</td>
                    <td className="px-3 py-2">
                      <Pill tone={form.review_status === "APPROVED_FOR_ASSESSMENT" ? "clinic" : "warn"}>
                        {formReviewStatusLabel(form.review_status)}
                      </Pill>
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      <Moment value={form.published_at ?? null} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Button tone="secondary" onClick={() => void open(form)} disabled={busy}>
                        查看与处理
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selected ? (
        <Card
          title={`${selected.code} v${selected.version}：${selected.title}`}
          description={`安排使用该版本的考试场次：${selected.sittings} 场 · 内容指纹 ${selected.content_sha256?.slice(0, 12) ?? "—"} · 作者 ${nameOf(selected.author_user_id)}`}
          actions={
            <Button tone="secondary" onClick={() => setSelected(null)} disabled={busy}>
              收起
            </Button>
          }
        >
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone={selected.review_status === "APPROVED_FOR_ASSESSMENT" ? "clinic" : "warn"}>
              {formReviewStatusLabel(selected.review_status)}
            </Pill>
            <Pill tone={approvalsOfCurrent >= 2 ? "clinic" : "alert"}>
              当前内容获得 {approvalsOfCurrent} / 2 位教师审核通过
            </Pill>
          </div>

          <h3 className="mt-4 font-semibold text-ink">审核记录</h3>
          {selected.reviews.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">
              还没有任何教师提交审核结论。必须两位不同的真实教师审核通过同一版内容后才能发布。
            </p>
          ) : (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2">审核人</th>
                    <th className="px-3 py-2">结论</th>
                    <th className="px-3 py-2">意见</th>
                    <th className="px-3 py-2">时间</th>
                    <th className="px-3 py-2">内容一致</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.reviews.map((review) => (
                    <tr key={review.teacher_user_id} className="border-b border-slate-100 align-top">
                      <td className="px-3 py-2">{nameOf(review.teacher_user_id)}</td>
                      <td className="px-3 py-2">
                        <Pill tone={review.decision === "approve" ? "clinic" : "alert"}>
                          {review.decision === "approve" ? "审核通过" : "驳回修改"}
                        </Pill>
                      </td>
                      <td className="px-3 py-2 text-slate-700">{review.comment}</td>
                      <td className="px-3 py-2 text-slate-600">
                        <Moment value={review.reviewed_at} />
                      </td>
                      <td className="px-3 py-2">
                        {review.matches_current_content ? "是" : "否（内容已变更，结论失效）"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h3 className="mt-5 font-semibold text-ink">审核人指派</h3>
          <p className="mt-1 text-sm text-slate-600">
            只能指派真实教师账号；题本作者不能同时担任审核人。管理员只负责核对与发布，不能代教师提交审核结论。
          </p>
          {staffUnavailable ? (
            <p className="mt-2 text-sm text-amber-800">人员目录不可用，暂时无法指派审核人。</p>
          ) : (
            <>
              <div className="mt-2 grid gap-2 sm:grid-cols-3">
                {teachers.map((account) => (
                  <label key={account.user_id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={picked.includes(account.user_id)}
                      disabled={editable === false || account.user_id === selected.author_user_id}
                      onChange={(event) =>
                        setPicked((current) =>
                          event.target.checked
                            ? [...current, account.user_id]
                            : current.filter((id) => id !== account.user_id),
                        )
                      }
                    />
                    <span>
                      {account.display_name}
                      {account.user_id === selected.author_user_id ? "（作者，不可担任审核人）" : ""}
                    </span>
                  </label>
                ))}
              </div>
              {teachers.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">人员目录中没有教师账号。</p>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-3">
                <Button onClick={() => void saveReviewers()} disabled={busy || !editable}>
                  保存审核人指派
                </Button>
                <Button
                  onClick={() => void publish()}
                  disabled={busy || !editable || approvalsOfCurrent < 2}
                  title={approvalsOfCurrent < 2 ? "需要两位教师审核通过当前内容" : undefined}
                >
                  核验并发布（双教师审核通过后）
                </Button>
              </div>
              {!editable ? (
                <p className="mt-2 text-xs text-slate-500">
                  该版本的审核流程已结束（已发布或已被新版本取代），不能再指派审核人或发布。
                </p>
              ) : null}
            </>
          )}

          <details className="mt-5 rounded-xl border border-slate-200 p-3">
            <summary className="cursor-pointer text-sm font-semibold text-ink">查看该版本内容（发布前核对）</summary>
            <ol className="mt-3 space-y-3">
              {selected.stages.map((stage, index) => (
                <li key={index}>
                  <StageBlock stage={stage} index={index} />
                </li>
              ))}
            </ol>
            <div className="mt-3 space-y-3">
              <RubricView rubric={selected.rubric} />
              <AnswerKeyView answerKey={selected.answer_key} />
            </div>
          </details>
        </Card>
      ) : null}
    </div>
  );
}
