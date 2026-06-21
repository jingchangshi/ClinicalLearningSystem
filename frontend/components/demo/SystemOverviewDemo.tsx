import { BookOpen, BrainCircuit, ClipboardCheck, Database, GraduationCap, MessageCircle, Stethoscope, Target } from "lucide-react";

import { FlowArrow } from "./FlowArrow";

const inputs = ["学生基础水平", "学习行为数据", "病例作答数据", "SP问诊数据", "指南PICO作答"];
const modules = [
  ["基础知识学习", BookOpen],
  ["临床技能训练", Stethoscope],
  ["临床思维训练", BrainCircuit],
  ["循证指南学习", ClipboardCheck],
  ["标准化病人考核", MessageCircle],
] as const;
const competencies = ["医学知识", "关键信息提取", "鉴别诊断", "证据整合", "临床决策", "医患沟通"];
const outputs = ["个性化学习路径", "教师精准干预", "胜任力成长曲线", "教学质量改进"];
const innovations = ["从单次考试转向全过程形成性评价", "从统一教学转向个性化路径", "从单一病例训练转向多模块综合训练", "从经验反馈转向数据驱动反馈"];

export function SystemOverviewDemo() {
  return (
    <section className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Research Overview</p>
          <h2 className="mt-2 text-3xl font-semibold text-ink">ClinPath 系统研究总览</h2>
          <p className="mt-2 text-slate-600">AI辅助临床能力形成性评价与个性化学习路径构建</p>
        </div>
        <div className="rounded-2xl border border-teal-100 bg-teal-50 p-5">
          <h3 className="font-semibold text-teal-950">研究创新点</h3>
          <div className="mt-3 space-y-2">
            {innovations.map((item) => (
              <p key={item} className="rounded-xl bg-white px-3 py-2 text-sm text-slate-700 shadow-sm">
                {item}
              </p>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid items-center gap-5 lg:grid-cols-[0.9fr_1.2fr_0.9fr]">
          <div className="rounded-2xl bg-slate-50 p-5">
            <div className="flex items-center gap-2 text-clinic">
              <Database className="h-5 w-5" />
              <h3 className="font-semibold">输入层：学习证据采集</h3>
            </div>
            <div className="mt-4 grid gap-2">
              {inputs.map((item) => (
                <span key={item} className="rounded-xl bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div className="relative rounded-[2rem] border border-cyan-100 bg-gradient-to-br from-cyan-50 to-teal-50 p-6">
            <div className="mx-auto flex h-32 w-32 flex-col items-center justify-center rounded-full bg-clinic text-center text-white shadow-lg">
              <BrainCircuit className="h-9 w-9" />
              <p className="mt-2 text-sm font-semibold">AI Engine</p>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
              {["短板识别", "难度分层", "下一任务推荐", "形成性反馈"].map((item) => (
                <div key={item} className="rounded-xl bg-white px-4 py-3 text-center font-semibold text-clinic shadow-sm">
                  {item}
                </div>
              ))}
            </div>
            <div className="mt-5">
              <h3 className="text-center font-semibold">训练层：五模块临床能力训练</h3>
              <div className="mt-4 grid gap-3 md:grid-cols-5">
                {modules.map(([item, Icon]) => (
                  <div key={item} className="rounded-2xl border border-teal-100 bg-white p-3 text-center shadow-sm">
                    <Icon className="mx-auto h-6 w-6 text-clinic" />
                    <p className="mt-2 text-xs font-semibold text-slate-700">{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-2xl bg-slate-50 p-5">
            <div className="flex items-center gap-2 text-clinic">
              <Target className="h-5 w-5" />
              <h3 className="font-semibold">输出层：教学闭环改进</h3>
            </div>
            <div className="mt-4 grid gap-2">
              {outputs.map((item) => (
                <span key={item} className="rounded-xl bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                  {item}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 text-clinic">
            <GraduationCap className="h-5 w-5" />
            <h3 className="font-semibold">评价层：六维能力画像</h3>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {competencies.map((item, index) => (
              <div key={item} className="flex items-center gap-3">
                <span className="rounded-full bg-cyan-50 px-5 py-3 text-sm font-semibold text-slate-700">{item}</span>
                {index < competencies.length - 1 ? <FlowArrow /> : null}
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="rounded-2xl bg-teal-900 px-6 py-4 text-center text-lg font-semibold text-white">
        形成“学生训练数据 → AI形成性评价 → 个性化任务推荐 → 教师精准干预 → 再训练评价”的医学教育闭环。
      </p>
    </section>
  );
}
