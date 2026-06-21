import { ArrowRight, BrainCircuit } from "lucide-react";

const steps = ["采集学习数据", "计算能力画像", "识别最低能力维度", "匹配训练模块", "生成下一阶段任务"];

export function AdaptiveRecommendationEngine() {
  return (
    <div className="rounded-2xl border border-teal-100 bg-gradient-to-br from-teal-700 to-cyan-700 p-6 text-white shadow-sm">
      <div className="flex items-center gap-3">
        <BrainCircuit className="h-7 w-7" />
        <h3 className="text-xl font-semibold">Adaptive Recommendation Engine</h3>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        {steps.map((step, index) => (
          <div key={step} className="flex items-center gap-3">
            <span className="rounded-full bg-white/15 px-5 py-3 text-sm font-semibold">{step}</span>
            {index < steps.length - 1 ? <ArrowRight className="h-5 w-5 text-teal-50" /> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
