import { BrainCircuit, GitBranch, Target } from "lucide-react";

import { FlowArrow } from "./FlowArrow";

const students = [
  {
    name: "学生A：基础薄弱型",
    traits: ["医学知识 58", "关键信息提取 62", "鉴别诊断 55"],
    path: ["基础知识单元", "SLE基础病例", "结构化问诊SP", "标准病例", "形成性反馈"],
  },
  {
    name: "学生B：高阶提升型",
    traits: ["医学知识 82", "临床推理 78", "循证决策 60"],
    path: ["复杂病例", "鉴别诊断训练", "指南PICO", "高阶SP考核", "文献阅读任务"],
  },
];

const engine = ["采集学习数据", "计算能力画像", "识别最低能力维度", "匹配训练模块", "生成下一阶段任务"];
const tasks = [
  ["指南PICO训练", "循证医学得分低于70", "循证决策", "+10%"],
  ["发热皮疹鉴别病例", "鉴别诊断连续两次低于班级均值", "临床推理", "+12%"],
  ["结构化问诊SP", "信息采集维度波动较大", "问诊沟通", "+8%"],
];

export function AdaptivePathwayDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Personalized Adaptive Learning Pathway</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">AI个性化学习路径</h2>
        <p className="mt-2 text-slate-600">基于能力短板的动态任务推荐与分层训练，展示“不同学生不是同一条路径”。</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {students.map((student) => (
          <div key={student.name} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3 text-clinic">
              <GitBranch className="h-6 w-6" />
              <h3 className="text-lg font-semibold">{student.name}</h3>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {student.traits.map((trait) => (
                <span key={trait} className="rounded-full bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700">
                  {trait}
                </span>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              {student.path.map((step, index) => (
                <div key={step} className="flex items-center gap-3">
                  <span className="rounded-xl bg-cyan-50 px-4 py-3 text-sm font-semibold text-slate-700">{step}</span>
                  {index < student.path.length - 1 ? <FlowArrow /> : null}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-teal-100 bg-gradient-to-br from-teal-700 to-cyan-700 p-6 text-white shadow-sm">
        <div className="flex items-center gap-3">
          <BrainCircuit className="h-7 w-7" />
          <h3 className="text-xl font-semibold">Adaptive Recommendation Engine</h3>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          {engine.map((step, index) => (
            <div key={step} className="flex items-center gap-3">
              <span className="rounded-full bg-white/15 px-5 py-3 text-sm font-semibold">{step}</span>
              {index < engine.length - 1 ? <FlowArrow /> : null}
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {tasks.map(([type, reason, target, lift]) => (
          <div key={type} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-clinic">
              <Target className="h-5 w-5" />
              <h3 className="font-semibold">{type}</h3>
            </div>
            <p className="mt-4 text-sm text-slate-600">推荐原因：{reason}</p>
            <p className="mt-2 text-sm text-slate-600">目标能力：{target}</p>
            <p className="mt-4 inline-flex rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-700">预计提升：{lift}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
