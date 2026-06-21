import { ClipboardCheck, MessageCircle, SearchCheck } from "lucide-react";

const clues = ["发热", "日晒后皮疹", "口腔溃疡", "泡沫尿", "关节痛"];
const missing = ["用药史", "感染线索", "妊娠情况", "肾功能和尿蛋白"];
const scores = [
  ["病史采集", 84],
  ["沟通表达", 88],
  ["临床推理", 76],
  ["人文关怀", 90],
  ["总分", 84.5],
];

export function SPOSCEDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">SP-OSCE Assessment</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">SP-OSCE标准化病人综合考核</h2>
        <p className="mt-2 text-slate-600">评估问诊、沟通、临床推理与人文关怀，突出 SP 不只是聊天，而是 OSCE 能力评价。</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.85fr_0.75fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 text-clinic">
            <MessageCircle className="h-5 w-5" />
            <h3 className="font-semibold">SP问诊对话</h3>
          </div>
          <div className="mt-5 space-y-4 text-sm leading-7">
            <div className="max-w-[88%] rounded-2xl bg-slate-100 p-4 text-slate-700">
              <p className="font-semibold text-slate-900">患者</p>
              <p>医生，我最近反复发热，还有皮疹和关节痛，很担心是不是严重疾病。</p>
            </div>
            <div className="ml-auto max-w-[88%] rounded-2xl bg-teal-700 p-4 text-white">
              <p className="font-semibold">学生</p>
              <p>我理解您的担心。请问发热持续多久？皮疹是否与日晒有关？有没有口腔溃疡或尿液异常？</p>
            </div>
            <div className="max-w-[88%] rounded-2xl bg-slate-100 p-4 text-slate-700">
              <p className="font-semibold text-slate-900">患者</p>
              <p>大概一个月了，晒太阳后脸上的红斑会加重，也有口腔溃疡，最近尿里泡沫多。</p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 text-clinic">
            <SearchCheck className="h-5 w-5" />
            <h3 className="font-semibold">实时信息提取面板</h3>
          </div>
          <h4 className="mt-5 text-sm font-semibold text-slate-700">已识别关键线索</h4>
          <div className="mt-3 flex flex-wrap gap-2">
            {clues.map((item) => (
              <span key={item} className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-800">
                {item}
              </span>
            ))}
          </div>
          <h4 className="mt-6 text-sm font-semibold text-slate-700">待补充信息</h4>
          <div className="mt-3 space-y-2">
            {missing.map((item) => (
              <p key={item} className="rounded-xl bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-900">
                {item}
              </p>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 text-clinic">
            <ClipboardCheck className="h-5 w-5" />
            <h3 className="font-semibold">OSCE评分卡</h3>
          </div>
          <div className="mt-5 space-y-3">
            {scores.map(([label, score]) => (
              <div key={label} className="rounded-xl bg-slate-50 px-4 py-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-600">{label}</span>
                  <span className="font-semibold text-clinic">{score}</span>
                </div>
                <div className="mt-2 h-2 rounded-full bg-slate-200">
                  <div className="h-2 rounded-full bg-clinic" style={{ width: `${Number(score)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-cyan-100 bg-cyan-50 p-6 shadow-sm">
        <h3 className="font-semibold text-ink">AI形成性反馈</h3>
        <p className="mt-3 text-sm leading-7 text-slate-700">
          本次问诊能较好体现共情表达和核心症状采集，但对感染鉴别、用药史和危险因素询问仍不足。建议进入“发热皮疹鉴别诊断病例”和“指南PICO训练”。
        </p>
      </div>
    </section>
  );
}
