/** Chinese display names for the six core competency dimensions. */
export const CORE_ABILITY_LABELS: Record<string, string> = {
  medical_knowledge: "医学知识",
  key_information: "关键信息提取",
  differential_diagnosis: "鉴别诊断",
  evidence_integration: "证据整合",
  clinical_decision: "临床决策",
  evidence_based_medicine: "循证医学",
};

export const CORE_ABILITY_KEYS = Object.keys(CORE_ABILITY_LABELS);

export function abilityLabel(key: string): string {
  return CORE_ABILITY_LABELS[key] ?? key;
}

/**
 * The evaluation indicator students see. It must never present rule-based
 * scoring as if a model produced it.
 */
export function evaluationModeLabel(mode: string, degraded: boolean): string {
  if (mode === "ai" && !degraded) return "AI 语义评价（真实模型调用）";
  return "规则降级评价（AI 当前不可用）";
}

/** The same distinction in a table cell, where the long form does not fit. */
export function evaluationModeShort(mode: string | null, degraded: boolean | null): string {
  if (mode === "ai" && !degraded) return "AI 语义评价";
  return "规则降级评价";
}
