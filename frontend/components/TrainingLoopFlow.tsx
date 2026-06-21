import { ArrowRight } from "lucide-react";

const steps = ["学生训练数据", "班级短板识别", "教师教学调整", "再训练", "效果评价"];

export function TrainingLoopFlow() {
  return (
    <div className="rounded-2xl border border-teal-100 bg-teal-50 p-6 shadow-sm">
      <h3 className="text-lg font-semibold">教学闭环</h3>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        {steps.map((step, index) => (
          <div key={step} className="flex items-center gap-3">
            <span className="rounded-full bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm">{step}</span>
            {index < steps.length - 1 ? <ArrowRight className="h-5 w-5 text-clinic" /> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
