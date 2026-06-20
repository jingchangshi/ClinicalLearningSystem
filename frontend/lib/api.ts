const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
    next_stage_goal: string;
  }>(`/api/students/${studentId}/pathway`);
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
