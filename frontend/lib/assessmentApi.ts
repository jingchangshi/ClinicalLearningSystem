/**
 * Independent online assessment API (`/api/assessments`).
 *
 * Deliberately separate from the formative client in `lib/api.ts`: the
 * assessment domain shares the login cookie but no business model, and it must
 * never be driven through the training routes.
 *
 * The one thing shared is `ApiError`: this module throws the same class so a
 * caller can treat both domains identically. On top of it,
 * `assessmentErrorMessage()` turns the assessment router's
 * `{"detail": {"code", "message"}}` refusal into Chinese text a student or
 * teacher can act on, and never leaks the server's English internals on their
 * own.
 */
import { ApiError } from "./api";

const API_BASE =
  typeof window === "undefined"
    ? process.env.INTERNAL_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8100/api"
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

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
  if (API_BASE.endsWith("/api") && path.startsWith("/api/")) return path.slice(4);
  return path;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const forwardedCookie = await cookieHeader();
  const response = await fetch(`${API_BASE}${normalizeApiPath(path)}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...forwardedCookie,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const rawBody = await response.text();
    let parsedBody: unknown = rawBody;
    try {
      parsedBody = rawBody ? JSON.parse(rawBody) : null;
    } catch {
      parsedBody = rawBody;
    }
    throw new ApiError(response.status, parsedBody);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function jsonBody(value: unknown): RequestInit {
  return { body: JSON.stringify(value) };
}

// --- errors -----------------------------------------------------------------

/** The assessment router's own refusal: a stable machine code plus its message. */
export type AssessmentErrorDetail = { code: string; message: string };

export function assessmentErrorDetail(error: unknown): AssessmentErrorDetail | null {
  if (!(error instanceof ApiError)) return null;
  const detail = (error.body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const code = (detail as { code?: unknown }).code;
    const message = (detail as { message?: unknown }).message;
    if (typeof code === "string") return { code, message: typeof message === "string" ? message : "" };
  }
  return null;
}

/** Every refusal the assessment router can raise, in the words a user needs. */
const CODE_MESSAGES: Record<string, string> = {
  // exam sitting, as the student experiences it
  sitting_not_found: "没有找到这场考核，请刷新页面后重试。",
  window_not_open: "这场考核的开放时间还没到。",
  window_closed: "考核窗口已经关闭，本场不能再提交。如因断网等原因未能完成，请联系研究管理员登记补考。",
  not_started: "请先点击「开始考核」再作答。",
  already_submitted: "这场考核已经提交，答案不能再修改。",
  wrong_stage: "草稿只能保存在当前阶段。",
  stage_skip: "必须按顺序完成：请先提交当前阶段。",
  answer_immutable: "该阶段已提交，答案不能修改。",
  answer_conflict: "该阶段已经提交过，请刷新页面查看最新进度。",
  draft_conflict: "草稿在别处被修改，请刷新后重试。",
  empty_answer: "作答内容不能为空。",
  incomplete: "五个阶段全部提交后才能提交整份答卷。",
  submit_failed: "提交未能记录，请重试；如反复失败请联系研究管理员。",
  // forms, authoring and two-teacher review
  form_not_found: "没有找到该题本（或当前账号无权查看）。",
  form_exists: "该题本编号已存在，请改为创建新版本。",
  form_not_approved: "该题本版本尚未通过双教师审核，不能用于考试。",
  form_frozen: "该题本版本已冻结，如需改动医学内容请创建新版本。",
  form_superseded: "该版本已被新版本取代。",
  no_change: "新版本必须与旧版本内容不同。",
  bad_stages: "题本必须恰好包含五个内容完整的阶段。",
  bad_rubric: "评分量表不合法：六个维度权重必须齐全、非负且合计为 100。",
  bad_decision: "审核结论不合法。",
  not_teachers: "审核人必须是真实教师账号。",
  distinct_reviewers: "至少需要两位不同的教师。",
  author_cannot_review: "题本作者不能同时担任该题本的审核人。",
  already_reviewed: "该教师已经提交过审核意见，不能重复提交。",
  two_approvals_required: "必须由两位不同的真实教师审核通过当前内容后，管理员才能发布。",
  // blinded rating and adjudication
  not_found: "没有找到这份答卷（或未指派给当前账号）。",
  bad_scores: "评分不合法：六个维度都必须填写 0–100 的数字。",
  review_locked: "本次评分已锁定，不能再修改。",
  no_disagreement: "该答卷未触发分歧裁决条件。",
  already_adjudicated: "该答卷已经完成裁决。",
  final_locked: "最终成绩已锁定，不能再裁决。",
  two_raters_required: "需要两位不同的评分者。",
  adjudicator_is_rater: "裁决人不能同时是评分者。",
  // study administration
  not_teacher: "所选人员必须是真实教师账号。",
  admin_required: "该操作需要研究管理员账号。",
  teacher_required: "该页面仅限教师账号使用。",
  student_required: "该页面仅限学生账号使用。",
  author_required: "创建或修改题本需要教师或管理员账号。",
  bad_group_or_timepoint: "研究组别或时点不合法。",
  bad_data_origin: "数据来源必须是 real_study、synthetic_demo 或 pilot_test。",
  bad_window: "时间窗口不合法：结束时间必须晚于开始时间。",
  bad_dates: "日期不合法。",
  bad_forms: "必须分别指定 A01 与 A02 的已发布题本。",
  bad_mode: "分配方式必须是 randomized 或 quasi_experimental。",
  missing_window: "每个批次都必须填写 T0 和 T1 两个时间窗口。",
  cohort_exists: "该批次编号已存在。",
  cohort_not_found: "没有找到该批次。",
  cohort_full: "一个轮转批次最多 7 名学生，不能再加入。",
  cohort_split: "同一批次的组别不可更改：7 名学生必须作为完整教学单元。",
  cohort_incomplete: "批次学生数不足，无法进行分配。",
  not_enrolled: "该学生未纳入本批次的在组名单。",
  already_enrolled: "一名学生只能属于一个批次。",
  enrollment_closed: "名单已冻结，不能再调整。",
  allocation_frozen: "题本顺序已冻结，入组名单不能再调整。",
  already_drawn: "该分配已经登记，不能重新抽签。",
  form_order_first: "必须先冻结题本顺序，再进行教学组随机化。",
  allocation_required: "正式研究必须先完成并冻结整批分配记录。",
  design_required: "尚未冻结分配记录，无法批量排考。",
  group_contradicts_allocation: "研究组别必须与已冻结的分配记录一致。",
  form_order_contradicts_allocation: "题本顺序必须与已冻结记录一致。",
  timepoint_assigned: "该学生的这个时点已经安排过考核。",
  same_form_twice: "T0 与 T1 必须使用不同的题本。",
  longitudinal_mismatch: "同一学生的 T0/T1 必须属于同一批次与同一研究组。",
  form_order_mismatch: "同一学生的 T0/T1 必须使用同一题本顺序。",
  data_origin_mismatch: "考试的数据来源必须与批次一致。",
  data_origin_mixed: "同一批次不能混合不同数据来源。",
  student_not_found: "没有找到该学生。",
  need_seven_cohorts: "必须恰好建立 7 个批次并完成入组，才能进行整批分配。",
  research_error: "研究模块拒绝了该操作，请核对该记录的内容。",
  not_extendable: "已提交或已作废的考试不能延长窗口。",
  already_voided: "该记录已作废。",
  already_scored: "已有评分的考试不能补考；请按数据集版本流程处理。",
  scoring_locked: "评分已锁定（已裁决或已定分），需通过新的数据集版本重新开评。",
  not_submitted: "只有已提交的答卷才能锁定成绩。",
  two_reviews_required: "必须两位评分者都提交后才能锁定成绩。",
  adjudication_required: "两位评分者分歧超过阈值，必须先完成裁决。",
  review_not_found: "没有找到该评分记录。",
  empty_dataset: "该数据来源下没有可冻结的记录。",
  not_final: "存在尚未锁定最终成绩的记录，需先完成评分或勾选允许不完整。",
  version_exists: "该数据集版本号已存在。",
  lock_not_found: "没有找到该数据集版本。",
};

export function assessmentErrorMessage(error: unknown, fallback = "网络连接中断或服务不可用，请稍后重试。"): string {
  const detail = assessmentErrorDetail(error);
  if (detail) {
    const known = CODE_MESSAGES[detail.code];
    if (known) return known;
    return detail.message ? `操作未完成（${detail.code}）：${detail.message}` : `操作未完成（${detail.code}）。`;
  }
  if (error instanceof ApiError) {
    if (error.status === 401) return "登录状态已失效，请重新登录。";
    if (error.status === 403) return "当前账号没有执行该操作的权限。";
    if (error.status === 404) return "接口不可用（HTTP 404）：后端可能尚未部署该功能。";
    if (error.status === 409) return "服务端拒绝了这次操作，请刷新页面确认当前状态。";
    if (error.status === 422) return "提交的内容不完整或格式不正确。";
    if (error.status >= 500) return `考核服务出错（HTTP ${error.status}），请稍后重试。`;
    return `操作未完成（HTTP ${error.status}）。`;
  }
  return fallback;
}

/** A pure network/timeout failure, as opposed to a refusal the server explained. */
export function isNetworkFailure(error: unknown): boolean {
  return !(error instanceof ApiError);
}

// --- shapes -----------------------------------------------------------------

export type SittingStatus = "assigned" | "in_progress" | "ready_to_submit" | "submitted" | "expired";

export type ExamStage = {
  index: number;
  title: string;
  clinical_information: string;
  question: string;
};

/** A stage of the form as it is stored; the blind and authoring views have no index. */
export type FormStage = { title: string; clinical_information: string; question: string };

export type ExamSittingListRow = {
  id: number;
  status: SittingStatus;
  timepoint: string;
  window_start: string;
  window_end: string;
  server_time: string;
};

export type ExamDraft = { answer_text: string; saved_at: string };

/** `GET /my/{id}`: exactly what the student has unlocked, nothing further. */
export type ExamView = {
  sitting_id: number;
  status: SittingStatus;
  timepoint: string;
  total_stages: number;
  server_time: string;
  window_start: string;
  window_end: string;
  instructions: string;
  completed: number;
  can_start?: boolean;
  submitted_at?: string | null;
  history?: (ExamStage & { answer_text: string })[];
  last_saved_at?: string | null;
  stage?: ExamStage;
  draft?: ExamDraft | null;
};

export const STUDY_DIMENSIONS = [
  ["medical_knowledge", "医学知识"],
  ["key_information", "关键信息提取"],
  ["differential_diagnosis", "鉴别诊断"],
  ["evidence_integration", "证据整合"],
  ["clinical_decision", "临床决策"],
  ["evidence_based_medicine", "循证安全"],
] as const;

export type StudyDimensionKey = (typeof STUDY_DIMENSIONS)[number][0];

export type Rubric = {
  weights: Record<string, number>;
  weights_source?: "supplied" | "study_default";
  weights_note?: string;
  rubric_version?: string;
  anchors?: Record<string, unknown>;
  disagreement?: { total_threshold: number; dimension_threshold: number | null; note?: string };
};

export type Disagreement = {
  total_diff: number;
  dimension_diffs: Record<string, number>;
  flagged: boolean;
  reasons: string[];
  total_threshold: number;
  dimension_threshold: number | null;
};

export type ReviewStatus =
  | "PENDING_REAL_REVIEW"
  | "CHANGES_REQUESTED"
  | "APPROVED_FOR_ASSESSMENT"
  | "SUPERSEDED";

export type FormSummary = {
  id: number;
  code: string;
  version: number;
  title: string;
  review_status: ReviewStatus;
  published_at?: string | null;
};

export type FormContent = {
  stages: FormStage[];
  rubric: Rubric;
  answer_key: Record<string, unknown>;
};

export type ReviewableForm = FormSummary & FormContent & {
  reviewed_by_me: boolean;
  my_decision: "approve" | "reject" | null;
};

export type FormReviewRow = {
  teacher_user_id: number;
  decision: string;
  comment: string;
  reviewed_at: string;
  matches_current_content: boolean;
};

export type FormDetail = FormSummary & FormContent & {
  content_sha256: string | null;
  author_user_id: number | null;
  sittings: number;
  assigned_reviewers: number[];
  reviews: FormReviewRow[];
};

export type StaffAccount = {
  user_id: number;
  display_name: string;
  role: "teacher" | "admin";
  teacher_no: string | null;
};

export type BlindQueueItem = { blind_code: string; reviewed: boolean };

export type BlindDetail = {
  blind_code: string;
  stages: FormStage[];
  answers: { index: number; answer_text: string }[];
  identifier_redactions: number;
  rubric: Rubric;
  answer_key: Record<string, unknown>;
  already_reviewed: boolean;
};

export type AdjudicationQueueItem = { blind_code: string; adjudicated: boolean };

export type AdjudicationDetail = BlindDetail & {
  disagreement: Disagreement;
  reviews: { label: string; scores: Record<string, number>; total_score: number; rationale: string | null }[];
  already_adjudicated: boolean;
};

export type SittingRow = {
  id: number;
  study_student_code: string | null;
  student_id: number;
  cohort_code: string;
  study_group: string;
  timepoint: string;
  form_id: number;
  form_order: string | null;
  status: string;
  attempt_no: number;
  data_origin: string;
  window_start: string;
  window_end: string;
  submitted_at: string | null;
  blinding_risk: string;
  blind_code: string;
  reviews: number;
  disagreement: Disagreement | null;
  adjudicated: boolean;
  final_score: number | null;
  scoring_provenance: string | null;
  dataset_lock_id: number | null;
};

export type SittingDetail = SittingRow & {
  events: { type: string; at: string; detail: Record<string, unknown> }[];
};

export type CohortRow = {
  id: number;
  cohort_code: string;
  label: string;
  expected_size: number;
  enrolled: number;
  planned_start: string | null;
  planned_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  teaching_user_ids: number[];
  data_origin: string;
  study_admin_user_id: number | null;
};

export type AllocationRecord = {
  cohort?: string;
  study_group?: string;
  form_order?: string;
  [key: string]: unknown;
};

export type AllocationRow = {
  allocation_version: string;
  kind: string;
  mode: string;
  data_origin: string;
  protocol_version: string;
  content_hash: string;
  executed_at: string;
  executed_by_user_id: number;
  record: AllocationRecord;
};

export type DesignAssignment = {
  student_id: number;
  study_student_code: string | null;
  cohort_code: string;
  enrollment_status: string;
  study_group: string | null;
  form_order: string | null;
};

export type AuditRow = {
  id: number;
  at: string;
  actor_user_id: number | null;
  actor_role: string | null;
  action: string;
  target: string;
  detail: Record<string, unknown>;
};

export type DatasetRecord = {
  study_student_code: string | null;
  cohort_id: string;
  study_group: string;
  randomization_version: string | null;
  randomization_mode: string | null;
  timepoint: string;
  assessment_form_code: string;
  assessment_form_version: number;
  form_order: string | null;
  attempt_no: number;
  blinded_rater_1_score: number | null;
  blinded_rater_2_score: number | null;
  rater_1_dimensions: Record<string, number> | null;
  rater_2_dimensions: Record<string, number> | null;
  absolute_total_diff: number | null;
  adjudicated_score: number | null;
  final_score: number | null;
  scoring_provenance: string | null;
  rubric_version: string | null;
  assessment_completed_at: string | null;
  sitting_status: string;
  missingness: string | null;
  blinding_risk: string;
  dataset_version: string | null;
  data_origin: string;
};

export type ExportPayload = {
  data_origin: string;
  dataset_status: string;
  records: DatasetRecord[];
};

export type AgreementPayload = {
  data_origin: string;
  timepoint: string | null;
  pairs: Partial<DatasetRecord>[];
  icc: Record<string, unknown> | null;
};

export type DatasetLockRow = {
  dataset_version: string;
  data_origin: string;
  records: number;
  sha256: string;
  locked_at: string;
  note: string | null;
};

export type IdentityRow = { study_student_code: string; student_id: number; name: string; student_no: string };

// --- student surface --------------------------------------------------------

export function listMyAssessments() {
  return call<ExamSittingListRow[]>("/api/assessments/my");
}

export function getMyAssessment(sittingId: number) {
  return call<ExamView>(`/api/assessments/my/${sittingId}`);
}

export function startAssessment(sittingId: number) {
  return call<ExamView>(`/api/assessments/my/${sittingId}/start`, { method: "POST" });
}

/** Draft saves are per current stage; the server refuses a draft for any other stage. */
export function saveAssessmentDraft(sittingId: number, stageIndex: number, answerText: string) {
  return call<{ saved_at: string; unchanged: boolean }>(`/api/assessments/my/${sittingId}/draft`, {
    method: "PUT",
    ...jsonBody({ stage_index: stageIndex, answer_text: answerText }),
  });
}

export function submitAssessmentStage(sittingId: number, stageIndex: number, answerText: string) {
  return call<{ completed: number; status: string; idempotent: boolean }>(`/api/assessments/my/${sittingId}/answer`, {
    method: "POST",
    ...jsonBody({ stage_index: stageIndex, answer_text: answerText }),
  });
}

export function submitAssessment(sittingId: number) {
  return call<{ status: string; submitted_at: string; already_submitted: boolean }>(
    `/api/assessments/my/${sittingId}/submit`,
    { method: "POST" },
  );
}

export function reportAssessmentInterruption(sittingId: number, reason: string) {
  return call<{ status: string }>(`/api/assessments/my/${sittingId}/interruption`, {
    method: "POST",
    ...jsonBody({ reason }),
  });
}

// --- authoring and two-teacher review ---------------------------------------

export function createAssessmentForm(payload: {
  code: string;
  title: string;
  stages: FormStage[];
  answer_key: Record<string, unknown>;
  rubric: Record<string, unknown>;
}) {
  return call<{ id: number; code: string; version: number; review_status: ReviewStatus }>("/api/assessments/forms", {
    method: "POST",
    ...jsonBody(payload),
  });
}

/** A new version is the only way to change medical content; published versions stay frozen. */
export function createAssessmentFormVersion(
  formId: number,
  payload: { title?: string; stages?: FormStage[]; answer_key?: Record<string, unknown>; rubric?: Record<string, unknown> },
) {
  return call<{ id: number; code: string; version: number; review_status: ReviewStatus }>(
    `/api/assessments/forms/${formId}/versions`,
    { method: "POST", ...jsonBody(payload) },
  );
}

export function listAllAssessmentForms() {
  return call<FormSummary[]>("/api/assessments/forms/admin/all");
}

export function listMyAssessmentForms() {
  return call<FormSummary[]>("/api/assessments/forms/mine");
}

export function listReviewableAssessmentForms() {
  return call<ReviewableForm[]>("/api/assessments/forms/reviewable");
}

export function getAssessmentFormDetail(formId: number) {
  return call<FormDetail>(`/api/assessments/forms/${formId}/admin`);
}

export function assignAssessmentFormReviewers(formId: number, teacherUserIds: number[]) {
  return call<{ form_id: number; assigned_reviewers: number[] }>(`/api/assessments/forms/${formId}/reviewers`, {
    method: "POST",
    ...jsonBody({ teacher_user_ids: teacherUserIds }),
  });
}

export function recordAssessmentFormReview(formId: number, decision: "approve" | "reject", comment: string) {
  return call<{ status: string }>(`/api/assessments/forms/${formId}/review`, {
    method: "POST",
    ...jsonBody({ decision, comment }),
  });
}

export function publishAssessmentForm(formId: number) {
  return call<{ id: number; review_status: ReviewStatus }>(`/api/assessments/forms/${formId}/approve`, {
    method: "POST",
  });
}

export function listAssessmentStaff() {
  return call<StaffAccount[]>("/api/assessments/admin/staff");
}

// --- blinded rating and adjudication ---------------------------------------

export function getBlindQueue() {
  return call<BlindQueueItem[]>("/api/assessments/blind/queue");
}

export function getBlindDetail(blindCode: string) {
  return call<BlindDetail>(`/api/assessments/blind/${encodeURIComponent(blindCode)}`);
}

export function submitBlindReview(blindCode: string, scores: Record<string, number>, rationale?: string) {
  return call<{ status: string; total_score: number; already_locked: boolean }>(
    `/api/assessments/blind/${encodeURIComponent(blindCode)}/review`,
    { method: "POST", ...jsonBody({ scores, ...(rationale ? { rationale } : {}) }) },
  );
}

export function getAdjudicationQueue() {
  return call<AdjudicationQueueItem[]>("/api/assessments/adjudication/queue");
}

export function getAdjudicationDetail(blindCode: string) {
  return call<AdjudicationDetail>(`/api/assessments/adjudication/${encodeURIComponent(blindCode)}`);
}

export function submitAdjudication(blindCode: string, scores: Record<string, number>, rationale: string) {
  return call<{ status: string; total_score: number }>(
    `/api/assessments/adjudication/${encodeURIComponent(blindCode)}`,
    { method: "POST", ...jsonBody({ scores, rationale }) },
  );
}

// --- study administration ---------------------------------------------------

export function listAssessmentSittings() {
  return call<SittingRow[]>("/api/assessments/admin/sittings");
}

export function getAssessmentSitting(sittingId: number) {
  return call<SittingDetail>(`/api/assessments/admin/sittings/${sittingId}`);
}

export function assignAssessmentSitting(payload: {
  student_id: number;
  form_id: number;
  cohort_code: string;
  study_group: string;
  timepoint: string;
  window_start: string;
  window_end: string;
  rater_a_id: number;
  rater_b_id: number;
  adjudicator_user_id?: number | null;
  data_origin?: string;
  form_order?: string | null;
}) {
  return call<{ id: number; status: string; blinding_risk: string; attempt_no: number }>(
    "/api/assessments/admin/sittings",
    { method: "POST", ...jsonBody(payload) },
  );
}

export function extendAssessmentSitting(sittingId: number, newWindowEnd: string, reason: string) {
  return call<{ id: number; status: string; window_end: string }>(
    `/api/assessments/admin/sittings/${sittingId}/extend`,
    { method: "POST", ...jsonBody({ new_window_end: newWindowEnd, reason }) },
  );
}

export function retakeAssessmentSitting(
  sittingId: number,
  payload: { reason: string; window_start: string; window_end: string; form_id?: number | null },
) {
  return call<{ id: number; status: string; blinding_risk: string; attempt_no: number }>(
    `/api/assessments/admin/sittings/${sittingId}/retake`,
    { method: "POST", ...jsonBody(payload) },
  );
}

export function sweepExpiredSittings() {
  return call<{ expired: number }>("/api/assessments/admin/sweep-expired", { method: "POST" });
}

export function finalizeAssessmentSitting(sittingId: number) {
  return call<{ sitting_id: number; final_score: number; scoring_provenance: string; locked_at: string; already_locked: boolean }>(
    `/api/assessments/admin/sittings/${sittingId}/finalize`,
    { method: "POST" },
  );
}

export function listAssessmentAudit(action?: string, limit = 200) {
  const query = new URLSearchParams();
  if (action) query.set("action", action);
  query.set("limit", String(limit));
  return call<AuditRow[]>(`/api/assessments/admin/audit?${query.toString()}`);
}

export function getAssessmentIdentityMap() {
  return call<IdentityRow[]>("/api/assessments/admin/identity-map");
}

export function listStudyCohorts() {
  return call<CohortRow[]>("/api/assessments/admin/cohorts");
}

export function createStudyCohort(payload: {
  cohort_code: string;
  label: string;
  expected_size?: number;
  planned_start?: string | null;
  planned_end?: string | null;
  teaching_user_ids?: number[];
  data_origin?: string;
}) {
  return call<CohortRow>("/api/assessments/admin/cohorts", { method: "POST", ...jsonBody(payload) });
}

export function setCohortActualDates(cohortCode: string, actualStart: string, actualEnd: string) {
  return call<CohortRow>(`/api/assessments/admin/cohorts/${encodeURIComponent(cohortCode)}/actual-dates`, {
    method: "POST",
    ...jsonBody({ actual_start: actualStart, actual_end: actualEnd }),
  });
}

export function enrollCohortStudents(cohortCode: string, studentIds: number[]) {
  return call<CohortRow>(`/api/assessments/admin/cohorts/${encodeURIComponent(cohortCode)}/enrollments`, {
    method: "POST",
    ...jsonBody({ student_ids: studentIds }),
  });
}

export function freezeFormOrder(payload: { data_origin: string; protocol_version: string; seed?: string }) {
  return call<{ allocation_version: string; content_hash: string; executed_at: string }>(
    "/api/assessments/admin/allocations/form-order",
    { method: "POST", ...jsonBody(payload) },
  );
}

export function drawClusterAllocation(payload: {
  data_origin: string;
  protocol_version: string;
  mode?: string;
  seed?: string;
  clinpath_cohorts?: string[];
}) {
  return call<{
    allocation_version: string;
    mode: string;
    content_hash: string;
    clinpath_cohorts: string[];
    cbl_cohorts: string[];
  }>("/api/assessments/admin/allocations/cluster", { method: "POST", ...jsonBody(payload) });
}

export function listStudyAllocations() {
  return call<AllocationRow[]>("/api/assessments/admin/allocations");
}

export function getDesignAssignments(dataOrigin: string) {
  return call<DesignAssignment[]>(
    `/api/assessments/admin/design/assignments?data_origin=${encodeURIComponent(dataOrigin)}`,
  );
}

export function scheduleStudySittings(payload: {
  data_origin: string;
  forms: Record<string, number>;
  windows: Record<string, { T0: { start: string; end: string }; T1: { start: string; end: string } }>;
  rater_a_id: number;
  rater_b_id: number;
  adjudicator_user_id?: number | null;
}) {
  return call<{ created: number; sitting_ids: number[] }>("/api/assessments/admin/design/schedule", {
    method: "POST",
    ...jsonBody(payload),
  });
}

export function researchAssessmentExport(dataOrigin: string) {
  return call<ExportPayload>(
    `/api/assessments/admin/export?data_origin=${encodeURIComponent(dataOrigin)}`,
  );
}

export function getRaterAgreement(dataOrigin: string, timepoint?: string) {
  const query = new URLSearchParams({ data_origin: dataOrigin });
  if (timepoint) query.set("timepoint", timepoint);
  return call<AgreementPayload>(`/api/assessments/admin/agreement?${query.toString()}`);
}

export function lockAssessmentDataset(payload: {
  dataset_version: string;
  data_origin: string;
  note?: string;
  allow_incomplete?: boolean;
}) {
  return call<{ dataset_version: string; records: number; sha256: string; locked_at: string }>(
    "/api/assessments/admin/dataset-locks",
    { method: "POST", ...jsonBody(payload) },
  );
}

export function listAssessmentDatasetLocks() {
  return call<DatasetLockRow[]>("/api/assessments/admin/dataset-locks");
}

export function getAssessmentDatasetLock(datasetVersion: string) {
  return call<{ sha256: string; integrity_ok: boolean; snapshot: Record<string, unknown> }>(
    `/api/assessments/admin/dataset-locks/${encodeURIComponent(datasetVersion)}`,
  );
}

// --- presentation helpers ---------------------------------------------------

/** The API speaks UTC with a trailing `Z`; every surface shows the viewer's own clock. */
export function formatAssessmentMoment(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatAssessmentClock(secondsRemaining: number): string {
  const clamped = Math.max(0, Math.floor(secondsRemaining));
  const hours = Math.floor(clamped / 3600);
  const minutes = Math.floor((clamped % 3600) / 60);
  const seconds = clamped % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${pad(minutes)}:${pad(seconds)}`;
}

/** The `datetime-local` value for an ISO instant, in the viewer's zone. */
export function toLocalInputValue(iso: string | null | undefined): string {
  if (!iso) return "";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

/** A `datetime-local` value is local time; the API only accepts an offset-aware instant. */
export function fromLocalInputValue(value: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

export function dimensionLabel(key: string): string {
  const found = STUDY_DIMENSIONS.find(([candidate]) => candidate === key);
  return found ? found[1] : key;
}

export const SYNTHETIC_ORIGINS = ["synthetic_demo", "pilot_test"];

/** The label every surface showing test data must carry; it is never optional. */
export const SYNTHETIC_ORIGIN_NOTE = "SYNTHETIC / SIMULATED_NOT_HUMAN：这是用于软件验收的测试数据，不是真实学生。";

export function isSyntheticOrigin(dataOrigin: string | null | undefined): boolean {
  return Boolean(dataOrigin) && SYNTHETIC_ORIGINS.includes(String(dataOrigin));
}

export function dataOriginLabel(dataOrigin: string | null | undefined): string {
  switch (dataOrigin) {
    case "real_study":
      return "真实研究数据";
    case "synthetic_demo":
      return "SYNTHETIC / SIMULATED_NOT_HUMAN · 合成演示";
    case "pilot_test":
      return "SYNTHETIC / SIMULATED_NOT_HUMAN · 软件验收测试";
    default:
      return dataOrigin ? String(dataOrigin) : "数据来源未知";
  }
}

export function sittingStatusLabel(status: string): string {
  switch (status) {
    case "assigned":
      return "待开始";
    case "in_progress":
      return "作答中";
    case "ready_to_submit":
      return "待提交";
    case "submitted":
      return "已提交";
    case "expired":
      return "窗口关闭未提交";
    case "voided":
      return "已作废（补考）";
    default:
      return status;
  }
}

export function formReviewStatusLabel(status: string): string {
  switch (status) {
    case "PENDING_REAL_REVIEW":
      return "待真实教师审核";
    case "CHANGES_REQUESTED":
      return "已驳回待修改";
    case "APPROVED_FOR_ASSESSMENT":
      return "已发布（双教师审核通过）";
    case "SUPERSEDED":
      return "已被新版本取代";
    default:
      return status;
  }
}

export function blindingRiskLabel(risk: string): string {
  switch (risk) {
    case "TEACHES_COHORT":
      return "盲法风险：该评分者同时承担本批教学任务";
    case "NO_CONFLICT_RECORDED":
      return "无在册利益冲突（不等于已验证盲法）";
    default:
      return "盲法状态未验证：缺少批次教师名单";
  }
}

export function missingnessLabel(value: string | null): string {
  switch (value) {
    case null:
      return "完整";
    case "expired_unsubmitted":
      return "窗口关闭未提交";
    case "not_submitted":
      return "未提交";
    case "not_scored":
      return "未完成双评";
    case "not_finalized":
      return "未锁定最终成绩";
    default:
      return value;
  }
}

export function scoringProvenanceLabel(provenance: string | null): string {
  switch (provenance) {
    case "dual_mean":
      return "双评均分";
    case "adjudicated":
      return "裁决结果";
    default:
      return provenance ?? "未定分";
  }
}
