import { Lock, Route, ShieldCheck } from "lucide-react";

const levels = [
  ["Level 1", "基础知识识别", "已完成", "医学知识", "知识单元"],
  ["Level 2", "标准病例推理", "已完成", "病史采集、体格检查", "病例、技能"],
  ["Level 3", "复杂症状鉴别", "进行中", "鉴别诊断、证据整合", "复杂病例"],
  ["Level 4", "循证决策训练", "待解锁", "循证决策", "指南PICO"],
  ["Level 5", "SP-OSCE 综合考核", "待解锁", "医患沟通", "SP"],
];

const matrix = [
  ["医学知识", "基础知识学习", "知识测验、错因分析"],
  ["病史采集", "临床技能训练", "结构化问诊、信息完整性"],
  ["鉴别诊断", "临床思维训练", "复杂病例、反证推理"],
  ["循证决策", "循证指南学习", "PICO、推荐等级、适用性"],
  ["医患沟通", "SP考核", "问诊对话、OSCE评分"],
];

export function CompetencyGrowthMapDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-clinic">Competency Growth Map</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">Competency Growth Map 医学生胜任力成长地图</h2>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        {levels.map(([level, title, status, abilities, tasks]) => {
          const active = status === "进行中";
          const done = status === "已完成";
          return (
            <div
              key={level}
              className={`rounded-2xl border bg-white p-5 shadow-sm ${active ? "border-clinic ring-2 ring-teal-100" : "border-slate-200"}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-clinic">{level}</span>
                {done ? <ShieldCheck className="h-5 w-5 text-emerald-600" /> : active ? <Route className="h-5 w-5 text-clinic" /> : <Lock className="h-5 w-5 text-slate-400" />}
              </div>
              <h3 className="mt-4 text-lg font-semibold">{title}</h3>
              <p className="mt-3 inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">当前状态：{status}</p>
              <p className="mt-4 text-sm leading-6 text-slate-600">对应能力：{abilities}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">对应任务：{tasks}</p>
            </div>
          );
        })}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold">Competency Matrix</h3>
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-200">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-semibold">能力维度</th>
                <th className="px-4 py-3 font-semibold">训练模块</th>
                <th className="px-4 py-3 font-semibold">证据来源</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {matrix.map(([ability, module, evidence]) => (
                <tr key={ability}>
                  <td className="px-4 py-3 font-medium text-ink">{ability}</td>
                  <td className="px-4 py-3 text-slate-600">{module}</td>
                  <td className="px-4 py-3 text-slate-600">{evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
