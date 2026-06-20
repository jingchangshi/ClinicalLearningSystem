import { BarChart3, Bot, ClipboardList, FileText, MessageCircle, Network } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const cards: Array<[string, string, LucideIcon]> = [
  ["系统总架构", "知识 → 技能 → 病例 → 指南 → SP → 能力画像 → AI推荐", Network],
  ["学生首页", "展示能力画像与推荐任务", BarChart3],
  ["临床推理训练", "展示病例分步推理与AI追问", Bot],
  ["循证指南学习", "展示PICO、推荐等级、临床适用性", FileText],
  ["SP标准化病人考核", "展示问诊对话和OSCE评分", MessageCircle],
  ["教师驾驶舱", "展示班级短板、教学重点、训练记录", ClipboardList],
];

function MiniChart() {
  return (
    <div className="mt-4 flex h-20 items-end gap-2 rounded-xl bg-slate-50 p-3">
      {[42, 64, 52, 78, 70, 86].map((height, index) => (
        <span key={index} className="flex-1 rounded-t bg-gradient-to-t from-teal-600 to-cyan-400" style={{ height: `${height}%` }} />
      ))}
    </div>
  );
}

export function GrantStoryboardDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-clinic">Grant Screenshot Storyboard</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">ClinPath Grant Screenshot Storyboard</h2>
        <p className="mt-2 text-slate-600">用于课题申报书的系统原型展示图组</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {cards.map(([title, description, Icon]) => (
          <div key={title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <p className="text-sm font-semibold text-ink">{title}</p>
                <p className="mt-1 text-xs text-slate-500">ClinPath Prototype</p>
              </div>
              <Icon className="h-5 w-5 text-clinic" />
            </div>
            <div className="mt-4 rounded-2xl border border-slate-100 bg-gradient-to-br from-white to-slate-50 p-4">
              <div className="h-2 w-28 rounded-full bg-teal-100" />
              <div className="mt-3 h-2 w-40 rounded-full bg-slate-200" />
              <MiniChart />
              <div className="mt-4 grid grid-cols-3 gap-2">
                <span className="h-10 rounded-lg bg-cyan-50" />
                <span className="h-10 rounded-lg bg-emerald-50" />
                <span className="h-10 rounded-lg bg-blue-50" />
              </div>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">{description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
