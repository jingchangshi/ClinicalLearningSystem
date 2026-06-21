import { AlertTriangle, TrendingUp, UserRound } from "lucide-react";

import { CompetencyRadarLarge } from "./CompetencyRadarLarge";

const radar = [
  { dimension: "医学知识", score: 78 },
  { dimension: "技能操作", score: 72 },
  { dimension: "关键信息提取", score: 68 },
  { dimension: "鉴别诊断", score: 61 },
  { dimension: "证据整合", score: 70 },
  { dimension: "循证决策", score: 58 },
  { dimension: "医患沟通", score: 82 },
  { dimension: "人文关怀", score: 80 },
];

const evidence = [
  ["医学知识", "知识测验 + 病例作答", "78", "高阶知识迁移"],
  ["技能操作", "技能步骤评分", "72", "关节查体训练"],
  ["鉴别诊断", "病例推理", "61", "发热皮疹鉴别病例"],
  ["循证决策", "指南PICO", "58", "EULAR/ACR指南训练"],
  ["医患沟通", "SP问诊", "82", "综合OSCE"],
];

export function CompetencyAssessmentDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Multidimensional Competency Assessment</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">多维度能力评估中心</h2>
        <p className="mt-2 text-slate-600">基于知识测验、病例推理、技能步骤、指南PICO和SP问诊数据形成学生能力画像。</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.8fr_1.35fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 text-clinic">
            <UserRound className="h-6 w-6" />
            <h3 className="font-semibold">学生能力画像</h3>
          </div>
          <div className="mt-6 space-y-4">
            <p className="text-xl font-semibold">临床医学本科生 A</p>
            <p className="text-sm text-slate-600">当前阶段：复杂症状鉴别训练</p>
            <div className="rounded-2xl bg-teal-50 p-5">
              <p className="text-sm text-slate-500">综合胜任力指数</p>
              <p className="mt-2 text-5xl font-semibold text-clinic">76</p>
              <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-emerald-700">
                <TrendingUp className="h-4 w-4" /> 较上次提升：+11%
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold">八维临床胜任力雷达图</h3>
          <CompetencyRadarLarge data={radar} />
        </div>

        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 shadow-sm">
          <div className="flex items-center gap-3 text-amber-700">
            <AlertTriangle className="h-6 w-6" />
            <h3 className="font-semibold">AI Learning Gap Diagnosis</h3>
          </div>
          <p className="mt-5 text-sm leading-7 text-slate-700">
            系统识别该学生当前主要短板为“循证决策”和“鉴别诊断”。建议优先完成指南PICO训练、复杂症状群病例和SP问诊任务。
          </p>
          <div className="mt-5 space-y-3">
            {["循证决策 58", "鉴别诊断 61", "关键信息提取 68"].map((item) => (
              <p key={item} className="rounded-xl bg-white px-4 py-3 text-sm font-semibold text-amber-900 shadow-sm">
                {item}
              </p>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold">形成性评价证据来源表</h3>
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                {["能力维度", "数据来源", "当前分数", "推荐干预"].map((head) => (
                  <th key={head} className="px-4 py-3 font-semibold">{head}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {evidence.map(([ability, source, score, action]) => (
                <tr key={ability}>
                  <td className="px-4 py-3 font-semibold text-ink">{ability}</td>
                  <td className="px-4 py-3 text-slate-600">{source}</td>
                  <td className={`px-4 py-3 font-semibold ${Number(score) < 65 ? "text-rose-600" : "text-clinic"}`}>{score}</td>
                  <td className="px-4 py-3 text-slate-600">{action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
