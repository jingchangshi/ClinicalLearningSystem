"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { refreshTeacherInsight } from "@/lib/api";

/**
 * The dashboard insight is cached, not generated on page load: reloading the
 * dashboard is not a reason to spend a model call. Asking for a new one is an
 * explicit action, and the badge shows which source the text currently has.
 */
export function TeacherInsightPanel({ summary, source }: { summary: string; source: "ai" | "rule" }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setPending(true);
    setError(null);
    try {
      const result = await refreshTeacherInsight();
      if (result.degraded) {
        setError(result.message ?? "AI 洞察暂不可用，已保留规则化教学建议。");
        return;
      }
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "刷新 AI 洞察失败");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">教学洞察</h2>
        <div className="flex items-center gap-2">
          <span
            className={
              source === "ai"
                ? "rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700"
                : "rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
            }
          >
            {source === "ai" ? "AI 生成" : "规则生成"}
          </span>
          <button
            type="button"
            onClick={refresh}
            disabled={pending}
            className="rounded-md border border-clinic px-3 py-1 text-sm text-clinic disabled:opacity-60"
          >
            {pending ? "生成中…" : "刷新 AI 洞察"}
          </button>
        </div>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-700">{summary}</p>
      {error ? <p className="mt-2 text-sm text-amber-700">{error}</p> : null}
      <p className="mt-2 text-xs text-slate-400">
        AI 洞察仅用于教学参考；班级能力画像与评分始终由结构化证据计算。
      </p>
    </section>
  );
}
