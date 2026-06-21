"use client";

import { useState } from "react";
import Link from "next/link";

import { KnowledgeUnit, submitKnowledgeQuiz } from "@/lib/api";

export function KnowledgeDetailClient({
  unit,
}: {
  unit: KnowledgeUnit;
}) {
  const quizItems = unit.quiz_items ?? [];
  const [answers, setAnswers] = useState<string[]>(quizItems.map(() => ""));
  const [result, setResult] = useState<{
    quiz_score: number;
    mastery_score: number;
    feedback: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    try {
      const response = await submitKnowledgeQuiz(unit.id, null, answers);
      setResult(response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "测验提交失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm text-slate-500">
          {unit.category} · {unit.level}
        </p>
        <h1 className="text-2xl font-semibold text-ink">{unit.title}</h1>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">学习目标</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {unit.learning_objectives.map((item) => (
            <span key={item} className="rounded-md bg-clinic-soft px-2 py-1 text-sm text-teal-900">
              {item}
            </span>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">学习内容</h2>
        <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-700">{unit.content}</p>
        <h3 className="mt-5 font-medium">关键点</h3>
        <ul className="mt-2 list-inside list-disc text-sm leading-7 text-slate-700">
          {unit.key_points.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">知识测验</h2>
        <div className="mt-4 space-y-4">
          {quizItems.map((item, index) => (
            <label key={item.question} className="block">
              <span className="text-sm font-medium">{index + 1}. {item.question}</span>
              <textarea
                value={answers[index] ?? ""}
                onChange={(event) =>
                  setAnswers((value) => value.map((answer, answerIndex) => answerIndex === index ? event.target.value : answer))
                }
                className="mt-2 min-h-24 w-full rounded-md border border-slate-300 p-3 text-sm outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
              />
            </label>
          ))}
        </div>
        <button
          onClick={handleSubmit}
          disabled={busy || !quizItems.length}
          className="mt-4 rounded-md bg-clinic px-4 py-2 text-white disabled:bg-slate-300"
        >
          提交测验
        </button>
        {error ? <p className="mt-3 text-sm text-alert">{error}</p> : null}
        {result ? (
          <div className="mt-4 rounded-md bg-slate-50 p-4 text-sm text-slate-700">
            <div className="font-medium text-ink">测验得分：{result.quiz_score} · 掌握度：{result.mastery_score}</div>
            <p className="mt-2">{result.feedback}</p>
          </div>
        ) : null}
      </section>

      <Link href="/student/knowledge" className="inline-flex rounded-md border border-slate-300 px-4 py-2">
        返回知识列表
      </Link>
    </div>
  );
}
