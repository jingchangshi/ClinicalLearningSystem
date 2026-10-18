"use client";

/**
 * Presentation pieces shared by the independent-assessment surfaces.
 *
 * Two rules run through all of them: nothing shows raw JSON or a database id,
 * and anything synthetic or test-only says so out loud. A teacher-authored
 * `answer_key` or rubric is free-form, so it is rendered structurally (labels,
 * paragraphs, lists) rather than dumped.
 */
import { ReactNode } from "react";

import {
  SYNTHETIC_ORIGIN_NOTE,
  STUDY_DIMENSIONS,
  dataOriginLabel,
  dimensionLabel,
  formatAssessmentMoment,
  isSyntheticOrigin,
  type Disagreement,
  type FormStage,
  type Rubric,
} from "@/lib/assessmentApi";

export function Card({
  title,
  description,
  children,
  actions,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-ink">{title}</h2>
          {description ? <div className="mt-1 text-sm text-slate-600">{description}</div> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function Feedback({ error, message }: { error?: string | null; message?: string | null }) {
  return (
    <>
      {error ? (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="rounded-md bg-clinic-soft px-3 py-2 text-sm text-clinic">
          {message}
        </p>
      ) : null}
    </>
  );
}

export function Pill({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: "slate" | "clinic" | "warn" | "alert";
}) {
  const tones = {
    slate: "border-slate-300 bg-slate-50 text-slate-700",
    clinic: "border-clinic bg-clinic-soft text-clinic",
    warn: "border-amber-300 bg-amber-50 text-amber-800",
    alert: "border-red-300 bg-red-50 text-alert",
  } as const;
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${tones[tone]}`}>{children}</span>
  );
}

/** Test-only data must never be mistaken for the 49-student real study. */
export function DataOriginBadge({ dataOrigin }: { dataOrigin: string | null | undefined }) {
  return (
    <Pill tone={isSyntheticOrigin(dataOrigin) ? "warn" : "clinic"}>
      {dataOriginLabel(dataOrigin)}
    </Pill>
  );
}

export function SyntheticNotice({ dataOrigin }: { dataOrigin: string | null | undefined }) {
  if (!isSyntheticOrigin(dataOrigin)) return null;
  return (
    <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      {SYNTHETIC_ORIGIN_NOTE} 本页数据来源为「{dataOriginLabel(dataOrigin)}」，
      不能作为真实教学效果或真实研究结果报告。
    </p>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  tone = "primary",
  type = "button",
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "primary" | "secondary" | "danger";
  type?: "button" | "submit";
  title?: string;
}) {
  const tones = {
    primary: "bg-clinic text-white hover:bg-teal-800",
    secondary: "border border-slate-300 bg-white text-ink hover:border-clinic",
    danger: "border border-red-300 bg-white text-alert hover:bg-red-50",
  } as const;
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50 ${tones[tone]}`}
    >
      {children}
    </button>
  );
}

export function TabBar<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: T; label: string; badge?: number }[];
  active: T;
  onChange: (key: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          aria-current={active === tab.key ? "page" : undefined}
          className={`flex items-center gap-1 rounded-md border px-3 py-2 text-sm ${
            active === tab.key ? "border-clinic bg-clinic-soft font-semibold text-clinic" : "border-slate-300 bg-white"
          }`}
        >
          {tab.label}
          {typeof tab.badge === "number" && tab.badge > 0 ? (
            <span className="rounded-full bg-clinic px-1.5 text-xs text-white">{tab.badge}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

export function EmptyHint({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-500">{children}</p>;
}

/** One released stage: the clinical information the student has unlocked, then its question. */
export function StageBlock({
  stage,
  index,
  total,
  answer,
}: {
  stage: FormStage;
  index: number;
  total?: number;
  answer?: string | null;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold tracking-wide text-clinic">
        第 {index + 1} 阶段{total ? ` / 共 ${total} 阶段` : ""}
      </p>
      <h3 className="mt-1 font-semibold text-ink">{stage.title}</h3>
      <div className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{stage.clinical_information}</div>
      <p className="mt-3 rounded-md bg-white px-3 py-2 text-sm font-medium text-ink">{stage.question}</p>
      {answer != null ? (
        <div className="mt-3 border-t border-slate-200 pt-3">
          <p className="text-xs font-semibold text-slate-500">本阶段作答（已提交，不可修改）</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{answer || "（空）"}</p>
        </div>
      ) : null}
    </div>
  );
}

const ANSWER_KEY_LABELS: Record<string, string> = {
  diagnosis: "参考诊断",
  differential_diagnosis: "参考鉴别诊断",
  plan: "参考处理计划",
  treatment_plan: "参考治疗方案",
  key_tests: "关键检查",
  tests: "关键检查",
  key_points: "关键要点",
  safety: "安全要点",
  anchors: "评分锚点",
};

function humanizeKey(key: string): string {
  return ANSWER_KEY_LABELS[key] ?? key.replace(/_/g, " ");
}

/** Renders teacher-authored free-form content structurally, never as raw JSON. */
export function ContentValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined) return <span className="text-slate-400">—</span>;
  if (typeof value === "string") return <span className="whitespace-pre-wrap">{value}</span>;
  if (typeof value === "number" || typeof value === "boolean") return <span>{String(value)}</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <span className="text-slate-400">—</span>;
    return (
      <ul className="list-disc space-y-1 pl-5">
        {value.map((item, i) => (
          <li key={i}>
            <ContentValue value={item} depth={depth + 1} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length) return <span className="text-slate-400">—</span>;
    return (
      <dl className={`space-y-2 ${depth ? "border-l border-slate-200 pl-3" : ""}`}>
        {entries.map(([key, item]) => (
          <div key={key}>
            <dt className="text-xs font-semibold text-slate-500">{humanizeKey(key)}</dt>
            <dd className="text-sm text-slate-800">
              <ContentValue value={item} depth={depth + 1} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  return null;
}

export function AnswerKeyView({ answerKey }: { answerKey: Record<string, unknown> }) {
  return (
    <div className="rounded-md bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">参考答案（仅教师与评分者可见，学生端绝不下发）</p>
      <div className="mt-2">
        <ContentValue value={answerKey} />
      </div>
    </div>
  );
}

export function RubricView({ rubric }: { rubric: Rubric }) {
  const anchors = rubric.anchors ?? {};
  return (
    <div className="rounded-md bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-semibold text-slate-500">六维评分量表</p>
        {rubric.rubric_version ? <Pill>{rubric.rubric_version}</Pill> : null}
        <Pill tone={rubric.weights_source === "study_default" ? "warn" : "clinic"}>
          {rubric.weights_source === "study_default" ? "研究默认权重（待教师确认）" : "题本指定权重"}
        </Pill>
      </div>
      <table className="mt-2 w-full text-left text-sm">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className="py-1">维度</th>
            <th className="py-1">权重</th>
            <th className="py-1">评分锚点</th>
          </tr>
        </thead>
        <tbody>
          {STUDY_DIMENSIONS.map(([key]) => (
            <tr key={key} className="border-t border-slate-200 align-top">
              <td className="py-2 pr-3 font-medium text-ink">{dimensionLabel(key)}</td>
              <td className="py-2 pr-3 text-slate-700">{rubric.weights?.[key] ?? "—"}%</td>
              <td className="py-2 text-slate-700">
                {anchors[key] !== undefined ? <ContentValue value={anchors[key]} /> : <span className="text-slate-400">未提供</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rubric.weights_note ? <p className="mt-2 text-xs text-amber-800">权重说明：{rubric.weights_note}</p> : null}
      {rubric.disagreement ? (
        <p className="mt-2 text-xs text-slate-500">
          分歧阈值：总分差 &gt; {rubric.disagreement.total_threshold}
          {rubric.disagreement.dimension_threshold !== null
            ? `，或任一维度差 > ${rubric.disagreement.dimension_threshold}`
            : ""}
          （阈值仍需真实教师在正式研究前确认）
        </p>
      ) : null}
    </div>
  );
}

/** The six score boxes, with each dimension's anchor shown next to its weight. */
export function DimensionScoreInputs({
  scores,
  onChange,
  rubric,
  disabled,
  labels,
}: {
  scores: Record<string, number>;
  onChange: (next: Record<string, number>) => void;
  rubric?: Rubric;
  disabled?: boolean;
  labels?: Record<string, string>;
}) {
  const anchors = rubric?.anchors ?? {};
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {STUDY_DIMENSIONS.map(([key]) => (
        <label key={key} className="rounded-md border border-slate-200 p-3 text-sm">
          <span className="flex items-center justify-between">
            <span className="font-medium text-ink">{labels?.[key] ?? dimensionLabel(key)}</span>
            <span className="text-xs text-slate-500">{rubric?.weights?.[key] ?? "—"}%</span>
          </span>
          <input
            type="number"
            min={0}
            max={100}
            required
            disabled={disabled}
            aria-label={`${dimensionLabel(key)}评分`}
            value={scores[key] ?? ""}
            onChange={(event) => {
              const raw = event.target.value;
              onChange({ ...scores, [key]: raw === "" ? Number.NaN : Number(raw) });
            }}
            className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1"
          />
          {anchors[key] !== undefined ? (
            <span className="mt-2 block text-xs text-slate-600">
              <ContentValue value={anchors[key]} />
            </span>
          ) : null}
        </label>
      ))}
    </div>
  );
}

/** Client-side preview of the weighted total; the server recomputes and stores the real one. */
export function weightedTotal(scores: Record<string, number>, rubric?: Rubric): number | null {
  const weights = rubric?.weights;
  if (!weights) return null;
  const sum = STUDY_DIMENSIONS.reduce((total, [key]) => total + (weights[key] ?? 0), 0);
  if (!sum) return null;
  if (STUDY_DIMENSIONS.some(([key]) => !Number.isFinite(scores[key]))) return null;
  const weighted = STUDY_DIMENSIONS.reduce((total, [key]) => total + scores[key] * (weights[key] ?? 0), 0);
  return Math.round((weighted / sum) * 100) / 100;
}

export function DisagreementView({ disagreement }: { disagreement: Disagreement }) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
      <p className="font-semibold">
        触发裁决：总分差 {disagreement.total_diff}（阈值 &gt; {disagreement.total_threshold}）
      </p>
      {disagreement.dimension_threshold !== null ? (
        <p className="mt-1 text-xs">
          维度差阈值 &gt; {disagreement.dimension_threshold}；触发原因：
          {disagreement.reasons.length ? disagreement.reasons.join("、") : "无"}
        </p>
      ) : null}
    </div>
  );
}

export function DimensionComparison({
  reviews,
  disagreement,
}: {
  reviews: { label: string; scores: Record<string, number>; total_score: number }[];
  disagreement?: Disagreement;
}) {
  const [a, b] = reviews;
  return (
    <table className="w-full text-left text-sm">
      <thead className="bg-slate-50 text-xs text-slate-500">
        <tr>
          <th className="px-3 py-2">维度</th>
          <th className="px-3 py-2">评分者 1</th>
          <th className="px-3 py-2">评分者 2</th>
          <th className="px-3 py-2">差值</th>
        </tr>
      </thead>
      <tbody>
        {STUDY_DIMENSIONS.map(([key]) => {
          const left = a?.scores?.[key];
          const right = b?.scores?.[key];
          const delta =
            disagreement?.dimension_diffs?.[key] ??
            (typeof left === "number" && typeof right === "number" ? Math.abs(left - right) : null);
          return (
            <tr key={key} className="border-b border-slate-100">
              <td className="px-3 py-2 font-medium text-ink">{dimensionLabel(key)}</td>
              <td className="px-3 py-2">{left ?? "—"}</td>
              <td className="px-3 py-2">{right ?? "—"}</td>
              <td className="px-3 py-2">{delta ?? "—"}</td>
            </tr>
          );
        })}
        <tr className="bg-slate-50 font-semibold">
          <td className="px-3 py-2">加权总分</td>
          <td className="px-3 py-2">{a?.total_score ?? "—"}</td>
          <td className="px-3 py-2">{b?.total_score ?? "—"}</td>
          <td className="px-3 py-2">
            {disagreement?.total_diff ??
              (a && b ? Math.round(Math.abs(a.total_score - b.total_score) * 100) / 100 : "—")}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

export function Moment({ value }: { value: string | null | undefined }) {
  return <span>{formatAssessmentMoment(value)}</span>;
}

export const IDENTIFIER_REDACTION_NOTE =
  "答卷中的姓名、学号等可识别信息已由系统自动替换为 [已去标识]。这是安全网，不是匿名化保证：学生也被要求不要写入可识别信息。";
