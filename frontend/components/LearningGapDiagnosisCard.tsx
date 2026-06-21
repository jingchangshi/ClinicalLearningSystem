type WeakAbility = { key: string; label: string; score: number };

const moduleMap: Record<string, string> = {
  medical_knowledge: "基础知识学习",
  skill_operation: "临床技能训练",
  key_information: "SP问诊与病例信息提取",
  differential_diagnosis: "复杂病例鉴别诊断",
  evidence_integration: "病例证据整合训练",
  clinical_decision: "治疗决策与安全监测",
  evidence_based_medicine: "循证指南PICO训练",
  communication: "标准化病人沟通训练",
  humanistic_care: "SP人文关怀反馈",
};

export function LearningGapDiagnosisCard({ weakAbilities }: { weakAbilities: WeakAbility[] }) {
  const rows = weakAbilities.slice(0, 2);
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
      <h3 className="font-semibold text-amber-900">AI Learning Gap Diagnosis</h3>
      <p className="mt-2 text-sm leading-6 text-slate-700">系统根据能力画像识别当前最低维度，并匹配下一阶段训练模块。</p>
      <div className="mt-4 space-y-3">
        {rows.map((item) => (
          <div key={item.key} className="rounded-xl bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="font-semibold text-ink">{item.label}</span>
              <span className="rounded-full bg-rose-50 px-3 py-1 text-sm font-semibold text-rose-700">{item.score}</span>
            </div>
            <p className="mt-2 text-sm text-slate-600">推荐模块：{moduleMap[item.key] ?? "个性化综合训练"}</p>
            <p className="mt-1 text-sm text-slate-600">推荐理由：该能力低于当前画像其他维度，适合优先干预。</p>
          </div>
        ))}
      </div>
    </div>
  );
}
