"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Plus, Trash2 } from "lucide-react";

import { ClinicalSkill, startSkillSession, submitSkillSession } from "@/lib/api";

type SubmitResult = Awaited<ReturnType<typeof submitSkillSession>>;

export function SkillDetailClient({
  skill,
  initialStudentId,
}: {
  skill: ClinicalSkill;
  initialStudentId: number;
}) {
  const expectedSteps = useMemo(() => skill.steps ?? [], [skill.steps]);
  const [submittedSteps, setSubmittedSteps] = useState<string[]>(
    expectedSteps.length ? expectedSteps.map(() => "") : [""],
  );
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateStep(index: number, value: string) {
    setSubmittedSteps((current) => current.map((step, stepIndex) => (stepIndex === index ? value : step)));
  }

  function removeStep(index: number) {
    setSubmittedSteps((current) => current.filter((_, stepIndex) => stepIndex !== index));
  }

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    try {
      const session = await startSkillSession(skill.id, initialStudentId);
      const response = await submitSkillSession(
        session.id,
        submittedSteps.map((step) => step.trim()).filter(Boolean),
      );
      setResult(response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "技能训练提交失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm text-slate-500">
          {skill.category} · {skill.difficulty}
        </p>
        <h1 className="text-2xl font-semibold text-ink">{skill.title}</h1>
      </section>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="font-semibold">适应证</h2>
            <p className="mt-3 text-sm leading-7 text-slate-700">{skill.indication}</p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="font-semibold">禁忌证</h2>
            <p className="mt-3 text-sm leading-7 text-slate-700">{skill.contraindication}</p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="font-semibold">常见错误</h2>
            <ul className="mt-3 list-inside list-disc text-sm leading-7 text-slate-700">
              {skill.common_errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold">提交操作步骤</h2>
            <button
              onClick={() => setSubmittedSteps(expectedSteps)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:border-clinic"
            >
              填入标准步骤
            </button>
          </div>

          <div className="mt-4 space-y-3">
            {submittedSteps.map((step, index) => (
              <div key={index} className="flex items-start gap-2">
                <span className="mt-2 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-100 text-sm">
                  {index + 1}
                </span>
                <textarea
                  value={step}
                  onChange={(event) => updateStep(index, event.target.value)}
                  className="min-h-16 flex-1 rounded-md border border-slate-300 p-3 text-sm outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
                />
                <button
                  onClick={() => removeStep(index)}
                  className="mt-2 rounded-md border border-slate-300 p-2 hover:border-alert hover:text-alert"
                  aria-label="删除步骤"
                  disabled={submittedSteps.length === 1}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              onClick={() => setSubmittedSteps((current) => [...current, ""])}
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 text-sm hover:border-clinic"
            >
              <Plus className="h-4 w-4" />
              添加步骤
            </button>
            <button
              onClick={handleSubmit}
              disabled={busy}
              className="rounded-md bg-clinic px-4 py-2 text-sm text-white disabled:bg-slate-300"
            >
              提交评分
            </button>
          </div>
          {error ? <p className="mt-3 text-sm text-alert">{error}</p> : null}
        </section>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">标准步骤</h2>
        <ol className="mt-3 space-y-2 text-sm text-slate-700">
          {expectedSteps.map((step, index) => (
            <li key={step} className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-clinic" />
              <span>
                {index + 1}. {step}
              </span>
            </li>
          ))}
        </ol>
      </section>

      {result ? (
        <section className="rounded-lg border border-clinic bg-clinic-soft p-5">
          <h2 className="font-semibold text-teal-950">训练反馈：{result.score} 分</h2>
          <p className="mt-3 text-sm leading-7 text-teal-950">{result.feedback}</p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <ScoreItem label="步骤完整性" value={result.detail.completeness_score} />
            <ScoreItem label="顺序合理性" value={result.detail.order_score} />
            <ScoreItem label="安全性关键词" value={result.detail.safety_score} />
          </div>
          {result.missed_steps.length ? (
            <div className="mt-4 text-sm text-teal-950">
              <div className="font-medium">遗漏步骤</div>
              <p className="mt-1">{result.missed_steps.join("；")}</p>
            </div>
          ) : null}
        </section>
      ) : null}

      <Link href={`/student/skills?studentId=${initialStudentId}`} className="inline-flex rounded-md border border-slate-300 px-4 py-2">
        返回技能列表
      </Link>
    </div>
  );
}

function ScoreItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-white p-3">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-ink">{value}</div>
    </div>
  );
}
