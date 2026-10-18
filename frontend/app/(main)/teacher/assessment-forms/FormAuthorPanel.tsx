"use client";

/**
 * Teacher-side题本 authoring: create a draft, or open a new version of one you
 * created. A published version is frozen server-side, so "edit" always means
 * "new version" — there is no path here that rewrites history.
 *
 * The list comes only from `GET /forms/mine` (newest version per code). That
 * contract carries metadata, not body text, so a teacher opening a new version
 * re-enters the content; an administrator can prefill it from the admin detail
 * route, which is the only route that returns another author's full version.
 */
import { useCallback, useEffect, useState } from "react";

import { Button, Card, EmptyHint, Feedback, Pill } from "@/components/assessment/AssessmentUi";
import { useAuth } from "@/components/AuthProvider";
import {
  assessmentErrorMessage,
  createAssessmentForm,
  createAssessmentFormVersion,
  formReviewStatusLabel,
  getAssessmentFormDetail,
  listMyAssessmentForms,
  type FormSummary,
} from "@/lib/assessmentApi";

import {
  AssessmentFormEditor,
  blankDraft,
  draftFromContent,
  type EditorSubmission,
  type FormEditorDraft,
} from "./AssessmentFormEditor";

type EditTarget =
  | { mode: "create"; draft: FormEditorDraft }
  | { mode: "version"; form: FormSummary; draft: FormEditorDraft; contentKnown: boolean };

export function FormAuthorPanel() {
  const { role } = useAuth();
  const [forms, setForms] = useState<FormSummary[] | null>(null);
  const [listUnavailable, setListUnavailable] = useState(false);
  const [target, setTarget] = useState<EditTarget | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadMine = useCallback(async () => {
    try {
      setForms(await listMyAssessmentForms());
      setListUnavailable(false);
    } catch {
      setForms([]);
      setListUnavailable(true);
    }
  }, []);

  useEffect(() => {
    void loadMine();
  }, [loadMine]);

  async function startVersion(form: FormSummary) {
    setError(null);
    setMessage(null);
    if (role === "admin") {
      // The admin detail route is the only one that returns a full version body.
      setBusy(true);
      try {
        const detail = await getAssessmentFormDetail(form.id);
        setTarget({
          mode: "version",
          form,
          contentKnown: true,
          draft: { ...draftFromContent(detail), code: form.code },
        });
        return;
      } catch {
        // Fall through to the metadata-only draft rather than blocking the flow.
      } finally {
        setBusy(false);
      }
    }
    setTarget({
      mode: "version",
      form,
      contentKnown: false,
      draft: { ...blankDraft(), formId: form.id, code: form.code, title: form.title },
    });
  }

  async function submit(payload: EditorSubmission) {
    if (!target) return;
    setBusy(true);
    setError(null);
    try {
      const result =
        target.mode === "create"
          ? await createAssessmentForm(payload)
          : await createAssessmentFormVersion(target.form.id, payload);
      setTarget(null);
      setMessage(
        `已创建 ${result.code} v${result.version}（待真实教师审核）。` +
          "管理员指派两位教师审核通过后才会发布，未经审核的题本不能用于考试。",
      );
      await loadMine();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  if (target) {
    return (
      <Card
        title={target.mode === "create" ? "创建考核题本" : `创建新版本：${target.form.code}`}
        description={
          target.mode === "create"
            ? "填写五个阶段的临床资料、考核问题、参考答案与六维量表。提交后进入两位真实教师的独立审核流程。"
            : `原为 v${target.form.version}。已发布或已用于考试的版本会保持冻结，本次提交只会产生一个新版本。`
        }
        actions={
          <Button tone="secondary" onClick={() => setTarget(null)} disabled={busy}>
            返回列表
          </Button>
        }
      >
        {target.mode === "version" && !target.contentKnown ? (
          <p className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            说明：题本清单只下发编号、版本与审核状态，不下发旧版本正文，因此这里只能预填编号与名称。
            请把新版本的完整内容重新填写一遍——旧版本不会被改动，新版本会以递增的版本号登记。
          </p>
        ) : null}
        <AssessmentFormEditor
          draft={target.draft}
          mode={target.mode}
          busy={busy}
          error={error}
          onCancel={() => setTarget(null)}
          onSubmit={submit}
        />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      <Card
        title="创建题本"
        description="题本是保密材料：创建后只有被指派的审核教师、评分者与管理员能看到内容，学生端只看到自己当前阶段。"
        actions={
          <Button onClick={() => setTarget({ mode: "create", draft: blankDraft() })}>创建新题本草案</Button>
        }
      >
        <p className="text-sm text-slate-600">
          正式研究使用 A01（未分化多关节炎）与 A02（原因待查的干燥症状，疑似原发性干燥综合征）两套题本。
          请按已修订的病例资料填写阶段信息，并在提交前请两位真实教师核对医学内容与评分锚点。
        </p>
      </Card>

      <Card
        title="我创建的题本"
        description="每个题本显示最新版本。在这里为新版本开一个草案：已发布的版本不会被覆盖。"
        actions={
          <Button tone="secondary" onClick={() => void loadMine()} disabled={busy}>
            刷新
          </Button>
        }
      >
        {listUnavailable ? (
          <p className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            「我创建的题本」接口（/api/assessments/forms/mine）当前不可用。
            在该接口部署之前，本页无法列出你已创建的题本；已创建的题本本身不受影响，管理员可以在题本管理中看到并指派审核。
          </p>
        ) : null}
        {forms === null ? (
          <p className="text-sm text-slate-500" role="status">
            正在加载题本…
          </p>
        ) : forms.length === 0 ? (
          <EmptyHint>还没有你创建的题本。点击上方「创建新题本草案」开始。</EmptyHint>
        ) : (
          <ul className="space-y-2">
            {forms.map((form) => (
              <li
                key={form.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3"
              >
                <div>
                  <p className="font-medium text-ink">
                    {form.code} · v{form.version}
                  </p>
                  <p className="text-sm text-slate-600">{form.title}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Pill tone={form.review_status === "APPROVED_FOR_ASSESSMENT" ? "clinic" : "warn"}>
                    {formReviewStatusLabel(form.review_status)}
                  </Pill>
                  <Button
                    tone="secondary"
                    onClick={() => void startVersion(form)}
                    disabled={busy || form.review_status === "SUPERSEDED"}
                  >
                    创建新版本
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
