import Link from "next/link";
import { ArrowRight } from "lucide-react";

import type { RecommendedTask } from "@/lib/api";

const typeLabels: Record<RecommendedTask["type"], string> = {
  knowledge_unit: "基础知识",
  clinical_skill: "临床技能",
  case: "病例训练",
  guideline: "循证指南",
  sp_case: "SP问诊",
};

export function RecommendedTaskCard({ task, href }: { task: RecommendedTask; href: string }) {
  const target = task.target_abilities.join(" / ");
  return (
    <Link href={href} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:border-clinic">
      <div className="flex items-center justify-between gap-3">
        <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold text-clinic">{typeLabels[task.type]}</span>
        <span className="text-xs text-slate-400">优先级 {task.priority}</span>
      </div>
      <h3 className="mt-4 font-semibold text-ink">{task.title}</h3>
      <p className="mt-2 text-xs font-semibold text-slate-500">{task.difficulty_label}</p>
      <p className="mt-3 text-sm leading-6 text-slate-600">推荐原因：{task.reason}</p>
      <p className="mt-2 text-sm text-slate-600">目标能力：{target}</p>
      <p className="mt-2 text-sm text-slate-600">证据来源：{task.source_evidence}</p>
      <div className="mt-4 flex items-center justify-between">
        <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-700">预计提升：{task.expected_lift}</span>
        <span className="text-sm font-semibold text-clinic">{task.next_step_label}</span>
        <ArrowRight className="h-4 w-4 text-clinic" />
      </div>
    </Link>
  );
}
