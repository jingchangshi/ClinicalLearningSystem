import { Bot, CheckCircle2, UserRound } from "lucide-react";

import { DemoRadar } from "./DemoRadar";

const radarData = [
  { dimension: "医学知识", score: 76 },
  { dimension: "病史采集", score: 82 },
  { dimension: "体格检查", score: 69 },
  { dimension: "鉴别诊断", score: 57 },
  { dimension: "循证决策", score: 55 },
  { dimension: "医患沟通", score: 84 },
];

const actions = [
  "完成“成人Still病与感染鉴别”病例",
  "完成“免疫抑制治疗安全监测”知识单元",
  "完成“发热皮疹患者SP问诊”",
];

const timeline = ["知识测验", "病例推理", "指南PICO", "SP考核", "能力画像更新"];

export function LearnerDigitalTwinDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-clinic">Learner Digital Twin</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">Learner Digital Twin 学习者数字画像</h2>
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-teal-100 to-cyan-100 text-clinic">
            <UserRound className="h-12 w-12" />
          </div>
          <div className="mt-5 text-center">
            <h3 className="text-xl font-semibold">王佳</h3>
            <p className="mt-1 text-sm text-slate-500">学习阶段：复杂症状鉴别</p>
          </div>
          <div className="mt-6 space-y-3 text-sm">
            {["知识掌握：Level B", "临床推理：Level C", "循证能力：Level C", "沟通能力：Level B+"].map((item) => (
              <div key={item} className="rounded-xl bg-slate-50 px-4 py-3 text-slate-700">
                {item}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold">Six-Dimension Competency Model</h3>
          <DemoRadar data={radarData} height={360} />
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-2 text-clinic">
              <Bot className="h-5 w-5" />
              <h3 className="font-semibold">AI Diagnostic Summary</h3>
            </div>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              系统识别该学生在“鉴别诊断”和“循证医学”维度存在短板，建议优先完成复杂症状群病例、指南PICO训练和SP问诊任务。
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="font-semibold">Next Best Action</h3>
            <div className="mt-4 space-y-3">
              {actions.map((action) => (
                <div key={action} className="flex gap-3 rounded-xl bg-teal-50 px-4 py-3 text-sm text-slate-700">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-clinic" />
                  <span>{action}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold">Learning Evidence Timeline</h3>
        <div className="mt-5 grid gap-3 md:grid-cols-5">
          {timeline.map((item, index) => (
            <div key={item} className="relative rounded-xl border border-cyan-100 bg-cyan-50 p-4 text-center text-sm font-medium text-slate-700">
              <span className="absolute -top-3 left-1/2 flex h-7 w-7 -translate-x-1/2 items-center justify-center rounded-full bg-clinic text-xs text-white">
                {index + 1}
              </span>
              <p className="pt-2">{item}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
