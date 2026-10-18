"use client";

/**
 * The题本 editor, shared by "创建题本" and "创建新版本".
 *
 * Published versions are frozen on the server, so a change to medical content is
 * always a new version: this editor carries the source form's id and never
 * offers to overwrite v1. Nothing is sent as JSON-as-text — the teacher fills in
 * real fields, and the six weights must add up to 100 before submission.
 */
import { useState } from "react";

import { Button, ContentValue, Pill } from "@/components/assessment/AssessmentUi";
import { STUDY_DIMENSIONS, dimensionLabel, type FormContent, type FormStage } from "@/lib/assessmentApi";

export type StageDraft = { title: string; clinical_information: string; question: string };

export type FormEditorDraft = {
  /** Set when this editor is producing a new version of an existing form. */
  formId: number | null;
  code: string;
  title: string;
  stages: StageDraft[];
  answerKey: Record<string, string>;
  extras: { key: string; value: string }[];
  rubricVersion: string;
  weights: Record<string, number>;
  anchors: Record<string, string>;
  totalThreshold: number;
  dimensionThreshold: string;
};

/** The study proposal from R3.2; the real values still need two teachers' confirmation. */
export const STUDY_DEFAULT_WEIGHTS: Record<string, number> = {
  medical_knowledge: 10,
  key_information: 20,
  differential_diagnosis: 25,
  evidence_integration: 15,
  clinical_decision: 20,
  evidence_based_medicine: 10,
};

const ANSWER_KEY_FIELDS: [string, string][] = [
  ["diagnosis", "参考诊断"],
  ["differential_diagnosis", "参考鉴别诊断"],
  ["treatment_plan", "参考处理计划"],
  ["key_points", "关键要点"],
];

export function blankDraft(): FormEditorDraft {
  return {
    formId: null,
    code: "",
    title: "",
    stages: Array.from({ length: 5 }, () => ({ title: "", clinical_information: "", question: "" })),
    answerKey: Object.fromEntries(ANSWER_KEY_FIELDS.map(([key]) => [key, ""])),
    extras: [],
    rubricVersion: "STUDY-RUBRIC-A01A02-v1",
    weights: { ...STUDY_DEFAULT_WEIGHTS },
    anchors: Object.fromEntries(STUDY_DIMENSIONS.map(([key]) => [key, ""])),
    totalThreshold: 10,
    dimensionThreshold: "20",
  };
}

function asString(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map((item) => asString(item)).join("\n");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${key}：${asString(item)}`)
      .join("\n");
  }
  return String(value);
}

/** Reopen an existing version's content in the editor, so a new version starts from it. */
export function draftFromContent(form: { id: number; code: string; title: string } & FormContent): FormEditorDraft {
  const base = blankDraft();
  const answerKey = { ...base.answerKey };
  const extras: { key: string; value: string }[] = [];
  for (const [key, value] of Object.entries(form.answer_key ?? {})) {
    const text = asString(value);
    if (key in answerKey) answerKey[key] = text;
    else extras.push({ key, value: text });
  }
  const anchors = { ...base.anchors };
  for (const [key, value] of Object.entries(form.rubric?.anchors ?? {})) {
    anchors[key] = asString(value);
  }
  const disagreement = form.rubric?.disagreement;
  return {
    formId: form.id,
    code: form.code,
    title: form.title,
    stages: form.stages.map((stage) => ({
      title: stage.title,
      clinical_information: stage.clinical_information,
      question: stage.question,
    })),
    answerKey,
    extras,
    rubricVersion: form.rubric?.rubric_version ?? base.rubricVersion,
    weights: { ...base.weights, ...(form.rubric?.weights ?? {}) },
    anchors,
    totalThreshold: disagreement?.total_threshold ?? base.totalThreshold,
    dimensionThreshold:
      disagreement?.dimension_threshold === null || disagreement?.dimension_threshold === undefined
        ? ""
        : String(disagreement.dimension_threshold),
  };
}

export type EditorSubmission = {
  code: string;
  title: string;
  stages: FormStage[];
  answer_key: Record<string, unknown>;
  rubric: Record<string, unknown>;
};

function buildPayload(draft: FormEditorDraft): EditorSubmission {
  const answerKey: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(draft.answerKey)) {
    const text = value.trim();
    if (text) answerKey[key] = text.includes("\n") ? text.split("\n").map((line) => line.trim()).filter(Boolean) : text;
  }
  for (const extra of draft.extras) {
    const key = extra.key.trim();
    const value = extra.value.trim();
    if (key && value) answerKey[key] = value;
  }
  const anchors: Record<string, string> = {};
  for (const [key, value] of Object.entries(draft.anchors)) {
    if (value.trim()) anchors[key] = value.trim();
  }
  return {
    code: draft.code.trim(),
    title: draft.title.trim(),
    stages: draft.stages.map((stage) => ({
      title: stage.title.trim(),
      clinical_information: stage.clinical_information.trim(),
      question: stage.question.trim(),
    })),
    answer_key: answerKey,
    rubric: {
      rubric_version: draft.rubricVersion.trim() || undefined,
      weights: draft.weights,
      ...(Object.keys(anchors).length ? { anchors } : {}),
      disagreement: {
        total_threshold: draft.totalThreshold,
        dimension_threshold: draft.dimensionThreshold.trim() === "" ? null : Number(draft.dimensionThreshold),
      },
    },
  };
}

function validate(draft: FormEditorDraft, mode: "create" | "version"): string | null {
  if (mode === "create" && draft.code.trim().length < 2) return "请填写题本编号（例如 CASE-A01），至少 2 个字符。";
  if (draft.title.trim().length < 2) return "请填写题本名称，至少 2 个字符。";
  if (draft.stages.some((stage) => !stage.title.trim() || !stage.clinical_information.trim() || !stage.question.trim())) {
    return "五个阶段都必须填写阶段标题、临床资料和考核问题。";
  }
  if (!Object.values(draft.answerKey).some((value) => value.trim())) {
    return "请至少填写一项参考答案（参考诊断），否则评分者没有可比对的医学依据。";
  }
  const weights = Object.values(draft.weights);
  if (weights.some((value) => !Number.isFinite(value) || value < 0)) return "六个维度的权重必须是 0 或正数。";
  const sum = weights.reduce((total, value) => total + value, 0);
  if (Math.abs(sum - 100) > 0.001) return `六个维度权重合计必须为 100，当前为 ${Math.round(sum * 100) / 100}。`;
  return null;
}

export function AssessmentFormEditor({
  draft: initialDraft,
  mode,
  onCancel,
  onSubmit,
  busy,
  error,
}: {
  draft: FormEditorDraft;
  mode: "create" | "version";
  onCancel: () => void;
  onSubmit: (payload: EditorSubmission) => Promise<void>;
  busy: boolean;
  error: string | null;
}) {
  const [draft, setDraft] = useState<FormEditorDraft>(initialDraft);
  const [localError, setLocalError] = useState<string | null>(null);
  const weightSum = Object.values(draft.weights).reduce((total, value) => total + (Number.isFinite(value) ? value : 0), 0);

  function updateStage(index: number, key: keyof StageDraft, value: string) {
    setDraft((current) => ({
      ...current,
      stages: current.stages.map((stage, i) => (i === index ? { ...stage, [key]: value } : stage)),
    }));
  }

  async function handleSubmit() {
    const problem = validate(draft, mode);
    if (problem) {
      setLocalError(problem);
      return;
    }
    setLocalError(null);
    await onSubmit(buildPayload(draft));
  }

  return (
    <div className="space-y-5">
      {error ? (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-alert">
          {error}
        </p>
      ) : null}
      {localError ? (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-alert">
          {localError}
        </p>
      ) : null}

      <div className="rounded-xl border border-slate-200 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="text-slate-600">题本编号</span>
            <input
              aria-label="题本编号"
              value={draft.code}
              disabled={mode === "version"}
              onChange={(event) => setDraft((current) => ({ ...current, code: event.target.value }))}
              className="mt-1 w-full rounded-md border border-slate-300 p-2 disabled:bg-slate-100"
              placeholder="CASE-A01"
            />
            <span className="mt-1 block text-xs text-slate-500">
              {mode === "version" ? "版本号由服务器递增，编号沿用原题本。" : "编号用于研究中指代题本，不重复使用。"}
            </span>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">题本名称</span>
            <input
              aria-label="题本名称"
              value={draft.title}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
              placeholder="未分化多关节炎：五阶段临床推理考核"
            />
          </label>
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="font-semibold text-ink">五个阶段的临床资料与考核问题</h3>
        {draft.stages.map((stage, index) => (
          <div key={index} className="rounded-xl border border-slate-200 p-4">
            <p className="text-xs font-semibold text-clinic">第 {index + 1} 阶段</p>
            <label className="mt-2 block text-sm">
              <span className="text-slate-600">阶段标题</span>
              <input
                aria-label={`第${index + 1}阶段标题`}
                value={stage.title}
                onChange={(event) => updateStage(index, "title", event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 p-2"
              />
            </label>
            <label className="mt-2 block text-sm">
              <span className="text-slate-600">本阶段释放的临床资料</span>
              <textarea
                aria-label={`第${index + 1}阶段临床资料`}
                rows={4}
                value={stage.clinical_information}
                onChange={(event) => updateStage(index, "clinical_information", event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 p-2"
              />
            </label>
            <label className="mt-2 block text-sm">
              <span className="text-slate-600">本阶段考核问题</span>
              <textarea
                aria-label={`第${index + 1}阶段考核问题`}
                rows={2}
                value={stage.question}
                onChange={(event) => updateStage(index, "question", event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 p-2"
              />
            </label>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold text-ink">参考答案（学生端绝不下发）</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {ANSWER_KEY_FIELDS.map(([key, label]) => (
            <label key={key} className="text-sm">
              <span className="text-slate-600">{label}</span>
              <textarea
                aria-label={label}
                rows={2}
                value={draft.answerKey[key] ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, answerKey: { ...current.answerKey, [key]: event.target.value } }))
                }
                className="mt-1 w-full rounded-md border border-slate-300 p-2"
              />
            </label>
          ))}
        </div>
        <div className="mt-3 space-y-2">
          {draft.extras.map((extra, index) => (
            <div key={index} className="flex flex-wrap gap-2">
              <input
                aria-label={`附加条目名称${index + 1}`}
                placeholder="条目名称（如 key_tests）"
                value={extra.key}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    extras: current.extras.map((item, i) => (i === index ? { ...item, key: event.target.value } : item)),
                  }))
                }
                className="w-48 rounded-md border border-slate-300 p-2 text-sm"
              />
              <input
                aria-label={`附加条目内容${index + 1}`}
                placeholder="内容"
                value={extra.value}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    extras: current.extras.map((item, i) => (i === index ? { ...item, value: event.target.value } : item)),
                  }))
                }
                className="min-w-[12rem] flex-1 rounded-md border border-slate-300 p-2 text-sm"
              />
              <Button
                tone="danger"
                onClick={() =>
                  setDraft((current) => ({ ...current, extras: current.extras.filter((_, i) => i !== index) }))
                }
              >
                删除
              </Button>
            </div>
          ))}
          <Button
            tone="secondary"
            onClick={() => setDraft((current) => ({ ...current, extras: [...current.extras, { key: "", value: "" }] }))}
          >
            增加参考答案条目
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-semibold text-ink">六维评分量表</h3>
          <Pill tone={Math.abs(weightSum - 100) < 0.001 ? "clinic" : "alert"}>权重合计 {Math.round(weightSum * 100) / 100} / 100</Pill>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          权重与锚点属于研究量表，仍需两位真实教师在正式研究前确认；审核环节记录的就是这一版内容。
          平台原有形成性评分权重（20/20/20/15/15/10）是另一套工具，不在这里使用。
        </p>
        <label className="mt-3 block text-sm sm:w-1/2">
          <span className="text-slate-600">量表版本号</span>
          <input
            aria-label="量表版本号"
            value={draft.rubricVersion}
            onChange={(event) => setDraft((current) => ({ ...current, rubricVersion: event.target.value }))}
            className="mt-1 w-full rounded-md border border-slate-300 p-2"
          />
        </label>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button tone="secondary" onClick={() => setDraft((current) => ({ ...current, weights: { ...STUDY_DEFAULT_WEIGHTS } }))}>
            填入研究建议权重（10/20/25/15/20/10）
          </Button>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {STUDY_DIMENSIONS.map(([key]) => (
            <label key={key} className="text-sm">
              <span className="text-slate-600">{dimensionLabel(key)}权重（%）</span>
              <input
                type="number"
                min={0}
                aria-label={`${dimensionLabel(key)}权重`}
                value={Number.isFinite(draft.weights[key]) ? draft.weights[key] : ""}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    weights: { ...current.weights, [key]: Number(event.target.value) },
                  }))
                }
                className="mt-1 w-full rounded-md border border-slate-300 p-2"
              />
            </label>
          ))}
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {STUDY_DIMENSIONS.map(([key]) => (
            <label key={key} className="text-sm">
              <span className="text-slate-600">{dimensionLabel(key)}评分锚点</span>
              <textarea
                aria-label={`${dimensionLabel(key)}评分锚点`}
                rows={2}
                value={draft.anchors[key] ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, anchors: { ...current.anchors, [key]: event.target.value } }))
                }
                className="mt-1 w-full rounded-md border border-slate-300 p-2"
              />
            </label>
          ))}
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="text-slate-600">总分差阈值（超过即进入裁决）</span>
            <input
              type="number"
              min={0}
              aria-label="总分差阈值"
              value={draft.totalThreshold}
              onChange={(event) => setDraft((current) => ({ ...current, totalThreshold: Number(event.target.value) }))}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">单维度差阈值（留空表示只在总分差触发）</span>
            <input
              type="number"
              min={0}
              aria-label="单维度差阈值"
              value={draft.dimensionThreshold}
              onChange={(event) => setDraft((current) => ({ ...current, dimensionThreshold: event.target.value }))}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            />
          </label>
        </div>
      </div>

      <div className="rounded-xl bg-slate-50 p-4">
        <p className="text-sm font-semibold text-slate-600">提交前预览（学生端只看得到阶段资料与问题）</p>
        <div className="mt-2 space-y-2 text-sm text-slate-700">
          <p>
            题本：{draft.title || "（未填写）"} · 编号 {draft.code || "（未填写）"} · 阶段数 {draft.stages.length}
          </p>
          <div>
            <p className="text-xs font-semibold text-slate-500">参考答案条目</p>
            <ContentValue value={previewAnswerKey(draft)} />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Button onClick={() => void handleSubmit()} disabled={busy}>
          {busy ? "正在提交…" : mode === "create" ? "创建题本（进入审核流程）" : "创建新版本（进入审核流程）"}
        </Button>
        <Button tone="secondary" onClick={onCancel} disabled={busy}>
          取消
        </Button>
      </div>
    </div>
  );
}

function previewAnswerKey(draft: FormEditorDraft): Record<string, string> {
  const preview: Record<string, string> = {};
  for (const [key, value] of Object.entries(draft.answerKey)) {
    if (value.trim()) preview[key] = value.trim();
  }
  for (const extra of draft.extras) {
    if (extra.key.trim() && extra.value.trim()) preview[extra.key.trim()] = extra.value.trim();
  }
  return preview;
}
