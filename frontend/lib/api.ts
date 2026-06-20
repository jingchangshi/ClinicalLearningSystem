const API_BASE =
  typeof window === "undefined"
    ? process.env.INTERNAL_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8100"
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

export type ChartPoint = { dimension: string; score: number };
export type Student = {
  id: number;
  name: string;
  student_no: string;
  class_name: string;
  current_stage: string;
};
export type Competency = {
  medical_knowledge: number;
  key_information: number;
  differential_diagnosis: number;
  evidence_integration: number;
  clinical_decision: number;
  evidence_based_medicine: number;
  learning_engagement: number;
  chart_data: ChartPoint[];
};
export type CaseSummary = {
  id: number;
  title: string;
  disease_category: string;
  difficulty: string;
  chief_complaint: string;
  learning_objectives: string[];
};
export type CaseDetail = CaseSummary & {
  history: string;
  physical_exam: string;
  lab_results: string;
  imaging: string;
  standard_diagnosis: string;
  differential_diagnosis: string[];
  treatment_plan: string;
  rubric: Record<string, string>;
};
export type SessionDetail = {
  id: number;
  student: Student;
  case: CaseDetail;
  status: string;
  started_at: string;
  completed_at: string | null;
  answers: { id: number; step: string; answer_text: string; created_at: string }[];
  ai_messages: {
    id: number;
    role: string;
    message: string;
    reasoning_step: string;
    created_at: string;
  }[];
};
export type Score = {
  id: number;
  total_score: number;
  medical_knowledge: number;
  key_information: number;
  differential_diagnosis: number;
  evidence_integration: number;
  clinical_decision: number;
  evidence_based_medicine: number;
  feedback: string;
  strengths: string;
  weaknesses: string;
  chart_data: ChartPoint[];
};
export type KnowledgeUnit = {
  id: number;
  title: string;
  category: string;
  level: string;
  learning_objectives: string[];
  content?: string;
  key_points: string[];
  quiz_items?: { question: string; answer_keywords: string[] }[];
  related_case_ids: number[];
  created_at?: string;
};
export type KnowledgeProgress = {
  id: number;
  student_id: number;
  knowledge_unit_id: number;
  status: string;
  quiz_score: number;
  mastery_score: number;
  updated_at: string;
  knowledge_unit: KnowledgeUnit;
};
export type ClinicalSkill = {
  id: number;
  title: string;
  category: string;
  difficulty: string;
  indication: string;
  contraindication?: string;
  steps?: string[];
  common_errors: string[];
  scoring_rubric?: Record<string, string>;
  created_at?: string;
};
export type SkillSession = {
  id: number;
  student_id: number;
  skill_id: number;
  status: string;
  submitted_steps: string[];
  score: number | null;
  feedback: string | null;
  created_at: string;
  completed_at: string | null;
  skill: ClinicalSkill;
};
export type GuidelineDocument = {
  id: number;
  title: string;
  organization: string;
  year: number;
  disease_category: string;
  source_type: string;
  summary: string;
  recommendations?: { text: string; grade: string }[];
  pico_examples?: { p: string; i: string; c: string; o: string }[];
  created_at?: string;
};
export type GuidelineLearningSession = {
  id: number;
  student_id: number;
  guideline_id: number;
  clinical_question: string;
  pico: string;
  answer: string;
  score: number | null;
  feedback: string | null;
  created_at: string;
  guideline: GuidelineDocument;
};
export type SPCase = {
  id: number;
  title: string;
  disease_category: string;
  difficulty: string;
  patient_profile: Record<string, string | number>;
  opening_statement: string;
  hidden_history?: Record<string, string>;
  emotional_style: string;
  expected_tasks: string[];
  scoring_rubric?: Record<string, string>;
  created_at?: string;
};
export type SPSession = {
  id: number;
  student_id: number;
  sp_case_id: number;
  status: string;
  transcript: { role: "student" | "patient"; message: string }[];
  diagnosis_summary: string | null;
  communication_score: number | null;
  history_taking_score: number | null;
  reasoning_score: number | null;
  humanistic_care_score: number | null;
  total_score: number | null;
  feedback: string | null;
  started_at: string;
  completed_at: string | null;
  sp_case: SPCase;
};
export type RecommendedTask = {
  type: "knowledge_unit" | "clinical_skill" | "case" | "guideline" | "sp_case";
  id: number;
  title: string;
  reason: string;
  priority: number;
};

export function listStudents() {
  return request<Student[]>("/api/students");
}

export function getStudentDashboard(studentId: number) {
  return request<{
    student: Student;
    competency: Competency;
    recommended_cases: CaseSummary[];
    recent_advice: string;
    progress: { completed_cases: number; in_progress_cases: number; average_score: number };
  }>(`/api/students/${studentId}/dashboard`);
}

export function getCase(caseId: string | number) {
  return request<CaseDetail>(`/api/cases/${caseId}`);
}

export function listCases() {
  return request<CaseSummary[]>("/api/cases");
}

export function startSession(studentId: number, caseId: number) {
  return request<{ id: number; session_id: number; status: string }>("/api/sessions/start", {
    method: "POST",
    body: JSON.stringify({ student_id: studentId, case_id: caseId }),
  });
}

export function getSession(sessionId: number) {
  return request<SessionDetail>(`/api/sessions/${sessionId}`);
}

export function saveAnswer(sessionId: number, step: string, answerText: string) {
  return request<{ id: number; step: string; answer_text: string }>(`/api/sessions/${sessionId}/answers`, {
    method: "POST",
    body: JSON.stringify({ step, answer_text: answerText }),
  });
}

export function getCoachQuestion(sessionId: number, step: string, answerText: string) {
  return request<{ id: number; message: string; reasoning_step: string }>(`/api/sessions/${sessionId}/coach`, {
    method: "POST",
    body: JSON.stringify({ step, answer_text: answerText }),
  });
}

export function submitSession(sessionId: number) {
  return request<{ score_id: number; session_id: number; summary: Record<string, unknown> }>(
    `/api/sessions/${sessionId}/submit`,
    { method: "POST" },
  );
}

export function getResult(sessionId: string | number) {
  return request<{
    session: SessionDetail;
    case: CaseSummary;
    answers: { id: number; step: string; answer_text: string; created_at: string }[];
    score: Score;
    competency: Competency;
    recommendation: { case: CaseSummary; recommendation_reason: string; pathway_stage: string } | null;
  }>(`/api/sessions/${sessionId}/result`);
}

export function getPathway(studentId: number) {
  return request<{
    student: Student;
    competency: Competency;
    pathway_stages: { key: string; title: string; description: string }[];
    current_stage: string;
    completed_cases: { session_id: number; case: CaseSummary; score: number | null }[];
    recommended_case: CaseSummary;
    recommendation_reason: string;
    weak_abilities: { key: string; label: string; score: number }[];
    recommended_tasks: RecommendedTask[];
    knowledge_suggestions: { unit: KnowledgeUnit; reason: string }[];
    next_stage_goal: string;
  }>(`/api/students/${studentId}/pathway`);
}

export function listKnowledge() {
  return request<KnowledgeUnit[]>("/api/knowledge");
}

export function getKnowledgeUnit(unitId: string | number) {
  return request<KnowledgeUnit>(`/api/knowledge/${unitId}`);
}

export function getKnowledgeProgress(studentId: number) {
  return request<KnowledgeProgress[]>(`/api/students/${studentId}/knowledge-progress`);
}

export function submitKnowledgeQuiz(unitId: number, studentId: number, answers: string[]) {
  return request<{
    quiz_score: number;
    mastery_score: number;
    feedback: string;
    updated_progress: KnowledgeProgress;
  }>(`/api/knowledge/${unitId}/quiz`, {
    method: "POST",
    body: JSON.stringify({ student_id: studentId, answers }),
  });
}

export function listSkills() {
  return request<ClinicalSkill[]>("/api/skills");
}

export function getSkill(skillId: string | number) {
  return request<ClinicalSkill>(`/api/skills/${skillId}`);
}

export function startSkillSession(skillId: number, studentId: number) {
  return request<SkillSession>(`/api/skills/${skillId}/sessions/start`, {
    method: "POST",
    body: JSON.stringify({ student_id: studentId }),
  });
}

export function submitSkillSession(sessionId: number, submittedSteps: string[]) {
  return request<{
    score: number;
    feedback: string;
    missed_steps: string[];
    common_errors: string[];
    detail: {
      completeness_score: number;
      order_score: number;
      safety_score: number;
    };
    session: SkillSession;
  }>(`/api/skill-sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ submitted_steps: submittedSteps }),
  });
}

export function listGuidelines() {
  return request<GuidelineDocument[]>("/api/guidelines");
}

export function getGuideline(guidelineId: string | number) {
  return request<GuidelineDocument>(`/api/guidelines/${guidelineId}`);
}

export function submitGuidelinePico(
  guidelineId: number,
  payload: {
    student_id: number;
    clinical_question: string;
    pico: string;
    answer: string;
  },
) {
  return request<{
    score: number;
    feedback: string;
    recommended_answer: string;
    detail: {
      pico_completeness: number;
      guideline_match: number;
      grade_understanding: number;
      clinical_applicability: number;
      risk_individualization: number;
    };
    session: GuidelineLearningSession;
  }>(`/api/guidelines/${guidelineId}/pico`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listSPCases() {
  return request<SPCase[]>("/api/sp-cases");
}

export function getSPCase(spCaseId: string | number) {
  return request<SPCase>(`/api/sp-cases/${spCaseId}`);
}

export function startSPSession(studentId: number, spCaseId: number) {
  return request<{ session_id: number; opening_statement: string; session: SPSession }>("/api/sp-sessions/start", {
    method: "POST",
    body: JSON.stringify({ student_id: studentId, sp_case_id: spCaseId }),
  });
}

export function sendSPMessage(sessionId: number, message: string) {
  return request<{ patient_reply: string; transcript: SPSession["transcript"] }>(
    `/api/sp-sessions/${sessionId}/message`,
    {
      method: "POST",
      body: JSON.stringify({ message }),
    },
  );
}

export function submitSPSession(sessionId: number, diagnosisSummary: string) {
  return request<{
    total_score: number;
    communication_score: number;
    history_taking_score: number;
    reasoning_score: number;
    humanistic_care_score: number;
    feedback: string;
    session: SPSession;
  }>(`/api/sp-sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ diagnosis_summary: diagnosisSummary }),
  });
}

export function getSPResult(sessionId: string | number) {
  return request<SPSession>(`/api/sp-sessions/${sessionId}/result`);
}

export function getTeacherDashboard() {
  return request<{
    student_count: number;
    completed_session_count: number;
    class_average_total_score: number;
    average_improvement: number;
    class_competency: { chart_data: ChartPoint[] };
    weak_dimensions: { key: string; label: string; score: number; level: string }[];
    teaching_focus: string[];
    students: {
      id: number;
      name: string;
      current_stage: string;
      recent_score: number | null;
      weakest_ability: string;
      recommended_training: string;
    }[];
    recent_sessions: {
      session_id: number;
      student_name: string;
      case_title: string;
      score: number | null;
      completed_at: string | null;
    }[];
  }>("/api/teacher/dashboard");
}

export function teacherListCases() {
  return request<CaseDetail[]>("/api/teacher/cases");
}

export function teacherCreateCase(payload: Omit<CaseDetail, "id">) {
  return request<CaseDetail>("/api/teacher/cases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function teacherUpdateCase(caseId: number, payload: Omit<CaseDetail, "id">) {
  return request<CaseDetail>(`/api/teacher/cases/${caseId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function teacherDeleteCase(caseId: number) {
  return request<{ ok: boolean }>(`/api/teacher/cases/${caseId}`, { method: "DELETE" });
}

export type CaseGenerateRequest = {
  disease_category: string;
  difficulty: string;
  teaching_goal: string;
  required_elements: string[];
  target_abilities: string[];
};

export function generateTeacherCase(payload: CaseGenerateRequest) {
  return request<{ draft_id: number; generated_payload: Omit<CaseDetail, "id"> }>(
    "/api/teacher/case-generator/generate",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function approveGeneratedCase(draftId: number, generatedPayload?: Omit<CaseDetail, "id">) {
  return request<{ draft_id: number; status: string; case: CaseDetail }>(
    `/api/teacher/case-generator/${draftId}/approve`,
    {
      method: "POST",
      body: JSON.stringify(generatedPayload ? { generated_payload: generatedPayload } : {}),
    },
  );
}
