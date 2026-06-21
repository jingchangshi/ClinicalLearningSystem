"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { GuidelineDocument, submitGuidelinePico } from "@/lib/api";

type PicoResult = Awaited<ReturnType<typeof submitGuidelinePico>>;

export function GuidelineDetailClient({
  guideline,
}: {
  guideline: GuidelineDocument;
}) {
  const example = guideline.pico_examples?.[0];
  const [clinicalQuestion, setClinicalQuestion] = useState(
    example ? `${example.p}使用${example.i}相较${example.c}能否改善${example.o}？` : "",
  );
  const [pico, setPico] = useState(example ? formatPico(example) : "");
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<PicoResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scoreItems = useMemo(
    () =>
      result
        ? [
            ["PICO 完整性", result.detail.pico_completeness],
            ["指南推荐匹配", result.detail.guideline_match],
            ["推荐等级理解", result.detail.grade_understanding],
            ["临床适用性", result.detail.clinical_applicability],
            ["风险与个体化", result.detail.risk_individualization],
          ]
        : [],
    [result],
  );

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    try {
      const response = await submitGuidelinePico(guideline.id, {
        student_id: undefined,
        clinical_question: clinicalQuestion,
        pico,
        answer,
      });
      setResult(response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "PICO 练习提交失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm text-slate-500">
          {guideline.organization} · {guideline.year} · {guideline.disease_category}
        </p>
        <h1 className="text-2xl font-semibold text-ink">{guideline.title}</h1>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">指南摘要</h2>
        <p className="mt-3 text-sm leading-7 text-slate-700">{guideline.summary}</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {(guideline.recommendations ?? []).map((item) => (
          <div key={item.text} className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="text-sm font-medium text-clinic">{item.grade}</div>
            <p className="mt-3 text-sm leading-7 text-slate-700">{item.text}</p>
          </div>
        ))}
      </section>

      {example ? (
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">PICO 示例</h2>
          <div className="mt-3 grid gap-3 text-sm md:grid-cols-4">
            <PicoBox label="P" value={example.p} />
            <PicoBox label="I" value={example.i} />
            <PicoBox label="C" value={example.c} />
            <PicoBox label="O" value={example.o} />
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">PICO 练习</h2>
        <div className="mt-4 space-y-4">
          <label className="block">
            <span className="text-sm font-medium">临床问题</span>
            <textarea
              value={clinicalQuestion}
              onChange={(event) => setClinicalQuestion(event.target.value)}
              className="mt-2 min-h-20 w-full rounded-md border border-slate-300 p-3 text-sm outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">PICO 拆解</span>
            <textarea
              value={pico}
              onChange={(event) => setPico(event.target.value)}
              className="mt-2 min-h-28 w-full rounded-md border border-slate-300 p-3 text-sm outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">循证回答</span>
            <textarea
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              className="mt-2 min-h-32 w-full rounded-md border border-slate-300 p-3 text-sm outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
            />
          </label>
        </div>
        <button
          onClick={handleSubmit}
          disabled={busy}
          className="mt-4 rounded-md bg-clinic px-4 py-2 text-white disabled:bg-slate-300"
        >
          提交循证反馈
        </button>
        {error ? <p className="mt-3 text-sm text-alert">{error}</p> : null}
      </section>

      {result ? (
        <section className="rounded-lg border border-clinic bg-clinic-soft p-5">
          <h2 className="font-semibold text-teal-950">循证反馈：{result.score} 分</h2>
          <p className="mt-3 text-sm leading-7 text-teal-950">{result.feedback}</p>
          <div className="mt-4 grid gap-3 md:grid-cols-5">
            {scoreItems.map(([label, value]) => (
              <div key={label} className="rounded-md bg-white p-3">
                <div className="text-xs text-slate-500">{label}</div>
                <div className="mt-1 text-xl font-semibold text-ink">{value}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-md bg-white p-4 text-sm leading-7 text-slate-700">
            <div className="font-medium text-ink">推荐答案</div>
            <p className="mt-2">{result.recommended_answer}</p>
          </div>
        </section>
      ) : null}

      <Link href="/student/guidelines" className="inline-flex rounded-md border border-slate-300 px-4 py-2">
        返回指南列表
      </Link>
    </div>
  );
}

function PicoBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 p-3">
      <div className="text-sm font-semibold text-clinic">{label}</div>
      <div className="mt-1 text-slate-700">{value}</div>
    </div>
  );
}

function formatPico(example: { p: string; i: string; c: string; o: string }) {
  return `P：${example.p}\nI：${example.i}\nC：${example.c}\nO：${example.o}`;
}
