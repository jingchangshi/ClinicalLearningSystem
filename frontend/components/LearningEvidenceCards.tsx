import { BookOpen, BrainCircuit, ClipboardCheck, FileText, MessageSquareText } from "lucide-react";

import type { LearningEvidence } from "@/lib/api";

const icons = {
  knowledge: BookOpen,
  skill: ClipboardCheck,
  case: BrainCircuit,
  guideline: FileText,
  sp: MessageSquareText,
};

export function LearningEvidenceCards({ evidence }: { evidence: LearningEvidence[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-5">
      {evidence.map((item) => {
        const Icon = icons[item.module];
        return (
          <div key={item.module} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <Icon className="h-5 w-5 text-clinic" />
              <span className="rounded-full bg-teal-50 px-2 py-1 text-xs font-semibold text-clinic">
                {item.latest_score ?? "待评分"}
              </span>
            </div>
            <p className="mt-3 font-semibold text-ink">{item.label}</p>
            <p className="mt-1 text-sm text-slate-500">已完成 {item.completed} 次</p>
          </div>
        );
      })}
    </div>
  );
}
