import { Activity, Brain, ClipboardCheck, MessageSquareText } from "lucide-react";

import { DemoRadar } from "./DemoRadar";
import { MetricCard } from "./MetricCard";

const radarData = [
  { dimension: "医学知识", score: 72 },
  { dimension: "关键信息提取", score: 68 },
  { dimension: "鉴别诊断", score: 61 },
  { dimension: "证据整合", score: 70 },
  { dimension: "临床决策", score: 66 },
  { dimension: "循证医学", score: 58 },
];

const profile = [
  ["知识掌握", "Level B"],
  ["临床推理", "Level C+"],
  ["循证决策", "Level C"],
  ["沟通问诊", "Level B+"],
];

const recommendations = [
  ["SLE与感染鉴别病例", "鉴别诊断能力低于同年级均值", "+12%"],
  ["EULAR风湿免疫指南PICO训练", "循证医学能力为当前最低维度", "+10%"],
  ["标准化病人问诊训练", "需加强病史采集与共情表达", "+9%"],
];

export function AcademicDashboardDemo() {
  return (
    <section className="space-y-6">
      <div className="flex items-end justify-between gap-6">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-clinic">Academic Medicine Dashboard</p>
          <h2 className="mt-2 text-3xl font-semibold text-ink">ClinPath 学生学习驾驶舱</h2>
        </div>
        <div className="rounded-2xl border border-teal-100 bg-teal-50 px-5 py-4 text-sm text-teal-900">
          <p className="font-semibold">学生：李明</p>
          <p>临床医学本科三年级</p>
          <p>基础疾病识别 → 复杂症状鉴别</p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard title="Clinical Reasoning Index" value="78" delta="+12%" icon={Brain} />
        <MetricCard title="Evidence-Based Decision" value="72" delta="+8%" icon={ClipboardCheck} />
        <MetricCard title="History Taking" value="81" delta="+15%" icon={MessageSquareText} />
        <MetricCard title="Learning Maturity" value="74" delta="+10%" icon={Activity} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold">Competency Radar</h3>
          <DemoRadar data={radarData} />
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold">AI Learning Profile</h3>
          <div className="mt-5 space-y-4">
            {profile.map(([label, level]) => (
              <div key={label} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3">
                <span className="text-sm text-slate-600">{label}</span>
                <span className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-clinic shadow-sm">{level}</span>
              </div>
            ))}
          </div>
          <div className="mt-6 rounded-xl bg-cyan-50 p-4 text-sm leading-6 text-slate-700">
            AI 识别当前短板集中在鉴别诊断与循证医学，建议优先进入复杂症状群训练。
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold">AI Adaptive Learning Recommendation</h3>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {recommendations.map(([title, reason, lift]) => (
            <div key={title} className="rounded-2xl border border-teal-100 bg-gradient-to-br from-white to-teal-50 p-5">
              <p className="font-semibold text-ink">{title}</p>
              <p className="mt-3 text-sm leading-6 text-slate-600">原因：{reason}</p>
              <p className="mt-4 inline-flex rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-700">
                预计提升：{lift}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
