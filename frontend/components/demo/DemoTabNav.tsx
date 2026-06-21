"use client";

import type { DemoView } from "./DemoShell";

const tabs: Array<{ key: DemoView; label: string; usage: string }> = [
  { key: "overview", label: "系统总览", usage: "技术路线 / 研究内容 / 系统功能 / 评价体系 / 教学应用场景" },
  { key: "competency", label: "能力评价", usage: "技术路线 / 研究内容 / 系统功能 / 评价体系 / 教学应用场景" },
  { key: "pathway", label: "个性化路径", usage: "技术路线 / 研究内容 / 系统功能 / 评价体系 / 教学应用场景" },
  { key: "multimodal", label: "多模态训练", usage: "技术路线 / 研究内容 / 系统功能 / 评价体系 / 教学应用场景" },
  { key: "osce", label: "SP考核", usage: "技术路线 / 研究内容 / 系统功能 / 评价体系 / 教学应用场景" },
  { key: "teacher", label: "教师驾驶舱", usage: "技术路线 / 研究内容 / 系统功能 / 评价体系 / 教学应用场景" },
];

export function DemoTabNav({ activeView, onSelect }: { activeView: DemoView; onSelect: (view: DemoView) => void }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="grid gap-2 lg:grid-cols-6">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => onSelect(tab.key)}
            className={`rounded-xl px-4 py-3 text-left transition ${
              activeView === tab.key ? "bg-clinic text-white shadow-sm" : "bg-slate-50 text-slate-700 hover:bg-cyan-50 hover:text-clinic"
            }`}
          >
            <span className="block text-sm font-semibold">{tab.label}</span>
            <span className={`mt-1 block text-xs leading-5 ${activeView === tab.key ? "text-teal-50" : "text-slate-500"}`}>
              本页适合用于申请书：{tab.usage}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
