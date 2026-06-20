import { ArrowRight, BrainCircuit } from "lucide-react";

const traditional = ["同样课程", "同样病例", "同样考试", "反馈滞后"];
const pathA = ["基础知识单元", "SLE基础病例", "结构化问诊SP", "标准病例", "阶段反馈"];
const pathB = ["复杂病例", "鉴别诊断训练", "指南PICO", "高阶SP考核", "科研文献训练"];
const loop = ["Assessment", "Diagnosis of Learning Gap", "Adaptive Task", "AI Feedback", "Competency Update"];

function FlowRow({ title, label, items }: { title: string; label: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold">{title}</h3>
        <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold text-clinic">{label}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {items.map((item, index) => (
          <div key={item} className="flex items-center gap-2">
            <span className="rounded-xl border border-cyan-100 bg-cyan-50 px-4 py-3 text-sm font-medium text-slate-700">{item}</span>
            {index < items.length - 1 ? <ArrowRight className="h-4 w-4 text-clinic" /> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

export function BloomPathwayDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-clinic">Adaptive Pathway</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">Bloom 2-Sigma Inspired AI Tutor</h2>
        <p className="mt-2 text-slate-600">从统一教学走向一对一个性化临床能力训练</p>
      </div>

      <div className="grid items-stretch gap-5 lg:grid-cols-[0.8fr_0.55fr_1.65fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="font-semibold">传统教学模式</h3>
          <div className="mt-5 space-y-3">
            {traditional.map((item) => (
              <div key={item} className="rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-600">
                {item}
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col items-center justify-center rounded-2xl border border-teal-100 bg-gradient-to-br from-teal-700 to-cyan-700 p-6 text-center text-white shadow-sm">
          <BrainCircuit className="h-10 w-10" />
          <p className="mt-4 text-lg font-semibold">AI Adaptive Engine</p>
          <p className="mt-2 text-sm text-cyan-50">诊断短板并动态编排任务</p>
        </div>

        <div className="space-y-5">
          <FlowRow title="学生A：基础薄弱" label="Remediation Path" items={pathA} />
          <FlowRow title="学生B：基础较好" label="Advanced Path" items={pathB} />
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold">One-to-One Learning Loop</h3>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          {loop.map((item, index) => (
            <div key={item} className="flex items-center gap-3">
              <span className="rounded-full bg-emerald-50 px-5 py-3 text-sm font-semibold text-emerald-800">{item}</span>
              {index < loop.length - 1 ? <ArrowRight className="h-5 w-5 text-clinic" /> : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
