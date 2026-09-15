const API_BASE =
  typeof window === "undefined"
    ? process.env.INTERNAL_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8100/api"
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    super(`API request failed: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Submission errors carry the canonical list of unanswered reasoning steps. */
export function missingStepsFrom(error: unknown): string[] {
  if (!(error instanceof ApiError)) return [];
  const detail = (error.body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && Array.isArray((detail as { missing_steps?: unknown }).missing_steps)) {
    return (detail as { missing_steps: unknown[] }).missing_steps.map(String);
  }
  return [];
}

/** `quiet` marks a failure that is an expected outcome rather than a problem. */
type RequestOptions = RequestInit & { quiet?: boolean };

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const forwardedCookie = await cookieHeader();
  const requestUrl = `${API_BASE}${normalizeApiPath(path)}`;
  const response = await fetch(requestUrl, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...forwardedCookie,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const rawBody = await response.text();
    let parsedBody: unknown = rawBody;
    try {
      parsedBody = rawBody ? JSON.parse(rawBody) : null;
    } catch {
      parsedBody = rawBody;
    }
    // Callers can mark a request whose failure is an expected outcome (an
    // anonymous visitor probing /api/auth/me is a 401 by design) so the console
    // stays a signal of real problems. The error is still thrown.
    if (!init?.quiet) {
      console.error("API request failed", {
        url: requestUrl,
        status: response.status,
        body: rawBody,
      });
    }
    throw new ApiError(response.status, parsedBody);
  }
  return response.json();
}

async function cookieHeader(): Promise<Record<string, string>> {
  if (typeof window !== "undefined") return {};
  try {
    const { cookies } = await import("next/headers");
    const token = (await cookies()).get("access_token")?.value;
    return token ? { Cookie: `access_token=${encodeURIComponent(token)}` } : {};
  } catch {
    return {};
  }
}

function normalizeApiPath(path: string): string {
  if (API_BASE.endsWith("/api") && path.startsWith("/api/")) {
    return path.slice(4);
  }
  return path;
}

export type ChartPoint = { dimension: string; score: number };
export type Student = {
  id: number;
  name: string;
  student_no: string;
  class_name: string;
  current_stage: string;
};
export type User = {
  id: number;
  username: string;
  role: "student" | "teacher" | "admin";
  student_id: number | null;
  teacher_id: number | null;
  created_at: string;
};
export type Competency = {
  medical_knowledge: number;
  skill_operation: number;
  key_information: number;
  differential_diagnosis: number;
  evidence_integration: number;
  clinical_decision: number;
  evidence_based_medicine: number;
  communication: number;
  humanistic_care: number;
  learning_engagement: number;
  chart_data: ChartPoint[];
  expanded_chart_data: ChartPoint[];
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
export type StudentCaseDetail = CaseSummary & {
  history: string;
  physical_exam: string;
  lab_results: string;
  imaging: string;
};
export type SessionDetail = {
  id: number;
  student: Student;
  case: StudentCaseDetail;
  status: string;
  started_at: string;
  completed_at: string | null;
  answers: { id: number; step: string; answer_text: string; created_at: string; updated_at?: string }[];
  required_steps?: { key: string; title: string; prompt: string }[];
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
  evaluation_mode: "ai" | "rule_fallback";
  provider: string | null;
  model: string | null;
  rule_score: number | null;
  ai_score: number | null;
  teacher_confirmed_score: number | null;
  teacher_override_reason: string | null;
  degraded: boolean;
  evaluation_detail: {
    mode?: "ai" | "rule_fallback";
    dimensions?: Record<
      string,
      {
        score?: number | null;
        confidence?: number;
        evidence: string[];
        missing_points: string[];
        feedback: string;
        source?: "ai" | "rule";
      }
    >;
    strengths?: string[];
    priority_gaps?: string[];
    overall_feedback?: string;
    safety_flags?: string[];
  };
  safety_flags: string[];
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
  target_abilities: string[];
  source_evidence: string;
  priority_label: string;
  difficulty_label: string;
  next_step_label: string;
};
export type LearningEvidence = {
  module: "knowledge" | "skill" | "case" | "guideline" | "sp";
  label: string;
  completed: number;
  latest_score: number | null;
};

export function login(username: string, password: string) {
  return request<{ token_type: string; user: User }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function register(payload: {
  username: string;
  password: string;
  role: "student";
}) {
  return request<{ token_type: string; user: User }>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMe() {
  // An anonymous visitor is expected to get 401 here; the AuthProvider treats the
  // rejection as "not signed in", so this must not look like an application error.
  return request<User>("/api/auth/me", { quiet: true });
}

export function logout() {
  return request<{ ok: boolean }>("/api/auth/logout", { method: "POST" });
}

export function listStudents() {
  return request<Student[]>("/api/students");
}

export function getStudentDashboard(studentId: number) {
  void studentId;
  return request<{
    student: Student;
    competency: Competency;
    recommended_cases: CaseSummary[];
    recommendation_details: { case: CaseSummary; recommendation_reason: string; pathway_stage: string }[];
    recent_advice: string;
    learning_evidence: LearningEvidence[];
    progress: { completed_cases: number; in_progress_cases: number; average_score: number };
  }>("/api/student/dashboard");
}

export function getCase(caseId: string | number) {
  return request<StudentCaseDetail>(`/api/cases/${caseId}`);
}

export function listCases() {
  return request<CaseSummary[]>("/api/cases");
}

export function startSession(studentId: number | null, caseId: number) {
  return request<{ id: number; session_id: number; status: string }>("/api/sessions/start", {
    method: "POST",
    body: JSON.stringify({ ...(studentId ? { student_id: studentId } : {}), case_id: caseId }),
  });
}

export function getSession(sessionId: number) {
  return request<SessionDetail>(`/api/sessions/${sessionId}`);
}

export function saveAnswer(sessionId: number, step: string, answerText: string) {
  return request<{ id: number; step: string; answer_text: string; updated_at: string }>(
    `/api/sessions/${sessionId}/answers`,
    {
      method: "POST",
      body: JSON.stringify({ step, answer_text: answerText }),
    },
  );
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

export type AiStatus = {
  configured: boolean;
  provider: string | null;
  model: string | null;
  base_url_host: string | null;
  reachable: boolean | null;
  last_probe_at: string | null;
  last_probe_latency_ms: number | null;
  last_error_type: string | null;
  last_call_at: string | null;
  last_call_mode: "ai" | "rule_fallback" | null;
  calls: number;
  failures: number;
  fallbacks: number;
  timeout_seconds: number;
  max_retries: number;
  deprecated_variables_in_use: string[];
};

export function getSystemVersion() {
  return request<{
    app: string;
    environment: string;
    git_sha: string | null;
    git_sha_short: string | null;
    git_dirty: boolean;
    backend_source_fingerprint: string;
    schema_revision: string | null;
    backend_runtime: string;
    ai_configured: boolean;
  }>("/api/system/version");
}

export function getAiStatus() {
  return request<AiStatus>("/api/system/ai-status");
}

export type ReasoningStep = { key: string; title: string; prompt: string };

export function getReasoningSteps() {
  return request<{ steps: ReasoningStep[]; required_keys: string[] }>("/api/system/reasoning-steps");
}

export type TutorState = {
  step: string;
  dimension: string;
  evidence_already_covered: string[];
  missing_reasoning_elements: string[];
  misconceptions: string[];
  safety_gap: string[];
  asked_about: string[];
  turn_count: number;
  student_turn_count: number;
  max_turns: number;
  completion_state: "not_started" | "in_progress" | "coverage_sufficient" | "max_turns_reached";
};

export type TutorTurn = {
  id: number;
  step: string;
  turn_index: number;
  role: "tutor" | "student";
  message: string;
  created_at: string;
};

export type TutorConversation = {
  step: string;
  turns: TutorTurn[];
  state: TutorState;
  tutor_question?: string | null;
  stopped_reason?: string | null;
};

export function getTutorConversation(sessionId: number, step: string) {
  return request<TutorConversation>(
    `/api/sessions/${sessionId}/tutor?step=${encodeURIComponent(step)}`,
  );
}

export function sendTutorTurn(sessionId: number, step: string, message?: string) {
  return request<TutorConversation>(`/api/sessions/${sessionId}/tutor`, {
    method: "POST",
    body: JSON.stringify({ step, ...(message ? { message } : {}) }),
  });
}

export function probeAi() {
  return request<{
    configured: boolean;
    provider: string | null;
    model: string | null;
    reachable: boolean;
    latency_ms: number | null;
    error_type: string | null;
  }>("/api/system/ai-probe", { method: "POST" });
}

export type AiInvocation = {
  id: number;
  task_type: string;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  evidence_ref: string | null;
  session_id: number | null;
  student_id: number | null;
  calls: number;
  failures: number;
  success: boolean;
  fallback_used: boolean;
  latency_ms: number;
  error_type: string | null;
  created_at: string;
};

export function getAiInvocations(limit = 20) {
  return request<{
    recent: AiInvocation[];
    by_task: {
      task_type: string;
      events: number;
      calls: number;
      failures: number;
      fallbacks: number;
      avg_latency_ms: number | null;
      last_seen: string | null;
    }[];
  }>(`/api/system/ai-invocations?limit=${limit}`);
}

export function getPathway(studentId: number) {
  void studentId;
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
    learning_evidence: LearningEvidence[];
    knowledge_suggestions: { unit: KnowledgeUnit; reason: string }[];
    next_stage_goal: string;
  }>("/api/student/pathway");
}

export function listKnowledge() {
  return request<KnowledgeUnit[]>("/api/knowledge");
}

export function getKnowledgeUnit(unitId: string | number) {
  return request<KnowledgeUnit>(`/api/knowledge/${unitId}`);
}

export function getKnowledgeProgress(studentId: number) {
  void studentId;
  return request<KnowledgeProgress[]>("/api/student/knowledge-progress");
}

export function submitKnowledgeQuiz(unitId: number, studentId: number | null, answers: string[]) {
  return request<{
    quiz_score: number;
    mastery_score: number;
    feedback: string;
    updated_progress: KnowledgeProgress;
  }>(`/api/knowledge/${unitId}/quiz`, {
    method: "POST",
    body: JSON.stringify({ ...(studentId ? { student_id: studentId } : {}), answers }),
  });
}

export function listSkills() {
  return request<ClinicalSkill[]>("/api/skills");
}

export function getSkill(skillId: string | number) {
  return request<ClinicalSkill>(`/api/skills/${skillId}`);
}

export function startSkillSession(skillId: number, studentId: number | null) {
  return request<SkillSession>(`/api/skills/${skillId}/sessions/start`, {
    method: "POST",
    body: JSON.stringify(studentId ? { student_id: studentId } : {}),
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
    student_id?: number;
    clinical_question: string;
    pico: string;
    answer: string;
  },
) {
  return request<{
    score: number;
    feedback: string;
    recommended_answer: string;
    scoring_rationale: string;
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

export function startSPSession(studentId: number | null, spCaseId: number) {
  return request<{ session_id: number; opening_statement: string; session: SPSession }>("/api/sp-sessions/start", {
    method: "POST",
    body: JSON.stringify({ ...(studentId ? { student_id: studentId } : {}), sp_case_id: spCaseId }),
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
    training_total_count: number;
    module_counts: { knowledge: number; skill: number; case: number; guideline: number; sp: number };
    class_average_total_score: number;
    average_improvement: number;
    class_competency: { chart_data: ChartPoint[]; expanded_chart_data: ChartPoint[] };
    weak_dimensions: { key: string; label: string; score: number; level: string }[];
    current_common_weakness: string;
    class_heatmap: {
      student_id: number;
      student_name: string;
      medical_knowledge: number;
      skill_operation: number;
      key_information: number;
      differential_diagnosis: number;
      evidence_integration: number;
      clinical_decision: number;
      evidence_based_medicine: number;
      communication: number;
      humanistic_care: number;
    }[];
    teaching_interventions: string[];
    teaching_insight_summary: string;
    teaching_insight_source: "ai" | "rule";
    teaching_insight_generated_at: string | null;
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

export function refreshTeacherInsight() {
  return request<{
    teaching_insight_summary: string | null;
    teaching_insight_source: "ai" | "rule";
    degraded: boolean;
    message?: string;
  }>("/api/teacher/dashboard/refresh-insight", { method: "POST" });
}

export function getTeacherStudentProfile(studentId: string | number) {
  return request<{
    student: Student;
    competency: Competency;
    learning_evidence: LearningEvidence[];
    evidence_events: {
      id: number;
      module_type: string;
      score: number | null;
      competency_updates: Record<string, { before: number; after: number; delta: number; module_score: number }>;
      created_at: string;
    }[];
    recommended_tasks: RecommendedTask[];
    completed_sessions: { session_id: number; case: CaseSummary; score: number | null; completed_at: string | null }[];
    latest_sp: SPSession | null;
    latest_guideline: GuidelineLearningSession | null;
    growth_trend: { event_id: number; module_type: string; score: number | null; average_after: number; created_at: string }[];
  }>(`/api/teacher/students/${studentId}/learning-profile`);
}

export function exportResearchData() {
  return request<{
    format: string;
    anonymous: boolean;
    rows: {
      student_code: string;
      class_name: string;
      module_type: string;
      score: number | null;
      competency_before: Record<string, number>;
      competency_after: Record<string, number>;
      created_at: string;
    }[];
  }>("/api/teacher/export/research-data");
}

export function listTeachingInterventions() {
  return request<
    {
      id: number;
      title: string;
      target_ability: string;
      target_students: number[];
      intervention_type: string;
      description: string;
      created_at: string;
    }[]
  >("/api/teacher/interventions");
}

export function listTeacherScoreReviews() {
  return request<
    {
      id: number;
      evidence_event_id: number;
      ai_score: number;
      teacher_score: number;
      comment: string;
      agreement_delta: number;
      created_at: string;
    }[]
  >("/api/teacher/reviews");
}

export type ReviewableEvidence = {
  evidence_event_id: number;
  student_id: number;
  student_name: string;
  case_session_id: number;
  ai_score: number;
  teacher_confirmed_score: number | null;
  dimensions: Record<string, number>;
  created_at: string;
};

export function listReviewableEvidence() {
  return request<ReviewableEvidence[]>("/api/teacher/reviewable-evidence");
}

export function createTeacherScoreReview(payload: {
  evidence_event_id: number;
  confirmed_dimensions: Record<string, number>;
  comment: string;
}) {
  return request<{ id: number; teacher_score: number }>("/api/teacher/reviews", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function teacherListCases() {
  return request<CaseDetail[]>("/api/teacher/cases");
}

/** Authoring endpoints report identifier-shaped input without echoing the values. */
export type DeidentificationReport = {
  clean: boolean;
  findings: { field: string; label: string; kinds: string[] }[];
  message: string;
};

export function teacherCreateCase(payload: Omit<CaseDetail, "id">) {
  return request<CaseDetail & { deidentification: DeidentificationReport }>("/api/teacher/cases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function teacherUpdateCase(caseId: number, payload: Omit<CaseDetail, "id">) {
  return request<CaseDetail & { deidentification: DeidentificationReport }>(`/api/teacher/cases/${caseId}`, {
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
  return request<{
    draft_id: number;
    generated_payload: Omit<CaseDetail, "id">;
    deidentification: DeidentificationReport;
  }>(
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
