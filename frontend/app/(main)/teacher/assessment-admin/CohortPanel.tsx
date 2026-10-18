"use client";

/**
 * R4.1: the seven clerkship batches, their dates and their seven students each.
 *
 * A batch is one indivisible teaching unit, so there is no per-student group
 * selection anywhere here — only whole-batch records.
 */
import { useState } from "react";

import { Button, Card, EmptyHint, Feedback, Pill, SyntheticNotice } from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  createStudyCohort,
  enrollCohortStudents,
  setCohortActualDates,
  type CohortRow,
} from "@/lib/assessmentApi";

import { DATA_ORIGIN_OPTIONS, DateTimeField, StaffDirectoryNotice } from "./adminShared";
import type { useAdminDirectory } from "./adminShared";

type Directory = ReturnType<typeof useAdminDirectory>;

export function CohortPanel({ directory }: { directory: Directory }) {
  const { cohorts, students, error, setError, reload } = directory;
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({
    cohort_code: "",
    label: "",
    expected_size: 7,
    planned_start: "",
    planned_end: "",
    data_origin: "pilot_test",
  });
  const [enrolTarget, setEnrolTarget] = useState<string | null>(null);
  const [enrolPicks, setEnrolPicks] = useState<number[]>([]);
  const [actualTarget, setActualTarget] = useState<string | null>(null);
  const [actualStart, setActualStart] = useState("");
  const [actualEnd, setActualEnd] = useState("");

  async function create() {
    if (draft.cohort_code.trim().length < 1 || draft.label.trim().length < 1) {
      setError("请填写批次编号与名称。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createStudyCohort({
        cohort_code: draft.cohort_code.trim(),
        label: draft.label.trim(),
        expected_size: draft.expected_size,
        planned_start: draft.planned_start || null,
        planned_end: draft.planned_end || null,
        data_origin: draft.data_origin,
      });
      setMessage(`已建立批次 ${draft.cohort_code.trim()}。一个批次最多 ${draft.expected_size} 名学生，7 名学生必须作为完整教学单元。`);
      setDraft({ ...draft, cohort_code: "", label: "" });
      await reload();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function enroll(cohort: CohortRow) {
    if (!enrolPicks.length) {
      setError("请选择要纳入本批次的学生。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await enrollCohortStudents(cohort.cohort_code, enrolPicks);
      setMessage(`已把 ${enrolPicks.length} 名学生纳入批次 ${cohort.cohort_code}。`);
      setEnrolPicks([]);
      setEnrolTarget(null);
      await reload();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveActualDates(cohort: CohortRow) {
    if (!actualStart || !actualEnd) {
      setError("请填写批次的实际开始与结束日期。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await setCohortActualDates(cohort.cohort_code, actualStart, actualEnd);
      setMessage(`已登记批次 ${cohort.cohort_code} 的实际起止日期。`);
      setActualTarget(null);
      await reload();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  const remaining = (cohort: CohortRow) => Math.max(0, cohort.expected_size - cohort.enrolled);

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      <Card
        title="建立轮转批次"
        description="正式研究为 7 个批次、每批 7 名本科见习生。批次建立后即可纳入学生；题本顺序一旦冻结，名单就不能再调整。"
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">
            <span className="text-slate-600">批次编号</span>
            <input
              aria-label="批次编号"
              value={draft.cohort_code}
              onChange={(event) => setDraft({ ...draft, cohort_code: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
              placeholder="B1"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">批次名称</span>
            <input
              aria-label="批次名称"
              value={draft.label}
              onChange={(event) => setDraft({ ...draft, label: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
              placeholder="2026 年第 1 轮风湿免疫科见习"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">计划人数</span>
            <input
              type="number"
              min={1}
              max={7}
              aria-label="计划人数"
              value={draft.expected_size}
              onChange={(event) => setDraft({ ...draft, expected_size: Number(event.target.value) })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">计划开始日期</span>
            <input
              type="date"
              aria-label="计划开始日期"
              value={draft.planned_start}
              onChange={(event) => setDraft({ ...draft, planned_start: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">计划结束日期</span>
            <input
              type="date"
              aria-label="计划结束日期"
              value={draft.planned_end}
              onChange={(event) => setDraft({ ...draft, planned_end: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">数据来源</span>
            <select
              aria-label="数据来源"
              value={draft.data_origin}
              onChange={(event) => setDraft({ ...draft, data_origin: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              {DATA_ORIGIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-3">
          <Button onClick={() => void create()} disabled={busy}>
            {busy ? "正在建立…" : "建立批次"}
          </Button>
        </div>
        <SyntheticNotice dataOrigin={draft.data_origin} />
      </Card>

      <Card title="批次清单" description="入组人数必须等于计划人数，才能进行整批随机化。">
        {cohorts.length === 0 ? (
          <EmptyHint>还没有批次记录。</EmptyHint>
        ) : (
          <ul className="space-y-3">
            {cohorts.map((cohort) => (
              <li key={cohort.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-ink">
                      {cohort.cohort_code} · {cohort.label}
                    </p>
                    <p className="text-sm text-slate-600">
                      已入组 {cohort.enrolled} / {cohort.expected_size} 人 · 计划 {cohort.planned_start ?? "—"} 至{" "}
                      {cohort.planned_end ?? "—"}
                      {cohort.actual_start ? ` · 实际 ${cohort.actual_start} 至 ${cohort.actual_end}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill tone={cohort.data_origin === "real_study" ? "clinic" : "warn"}>
                      {cohort.data_origin === "real_study" ? "真实研究" : "测试/合成"}
                    </Pill>
                    <Pill tone={cohort.enrolled === cohort.expected_size ? "clinic" : "warn"}>
                      {cohort.enrolled === cohort.expected_size ? "名单完整" : `还缺 ${remaining(cohort)} 人`}
                    </Pill>
                    <Button
                      tone="secondary"
                      onClick={() => {
                        setEnrolTarget(enrolTarget === cohort.cohort_code ? null : cohort.cohort_code);
                        setEnrolPicks([]);
                      }}
                      disabled={busy || remaining(cohort) === 0}
                    >
                      纳入学生
                    </Button>
                    <Button
                      tone="secondary"
                      onClick={() => {
                        setActualTarget(actualTarget === cohort.cohort_code ? null : cohort.cohort_code);
                        setActualStart(cohort.actual_start ?? "");
                        setActualEnd(cohort.actual_end ?? "");
                      }}
                      disabled={busy}
                    >
                      登记实际日期
                    </Button>
                  </div>
                </div>

                {enrolTarget === cohort.cohort_code ? (
                  <div className="mt-3 rounded-lg bg-slate-50 p-3">
                    <p className="text-sm text-slate-600">
                      还可纳入 {remaining(cohort)} 人。一名学生只能属于一个批次；7 名学生必须分在同一研究组。
                    </p>
                    <div className="mt-2 max-h-56 overflow-auto">
                      {students.map((student) => (
                        <label key={student.id} className="flex items-center gap-2 py-1 text-sm">
                          <input
                            type="checkbox"
                            checked={enrolPicks.includes(student.id)}
                            disabled={!enrolPicks.includes(student.id) && enrolPicks.length >= remaining(cohort)}
                            onChange={(event) =>
                              setEnrolPicks((current) =>
                                event.target.checked
                                  ? [...current, student.id]
                                  : current.filter((id) => id !== student.id),
                              )
                            }
                          />
                          <span>
                            {student.name} · {student.student_no}
                            {student.class_name ? ` · ${student.class_name}` : ""}
                          </span>
                        </label>
                      ))}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button onClick={() => void enroll(cohort)} disabled={busy || !enrolPicks.length}>
                        确认纳入 {enrolPicks.length} 名学生
                      </Button>
                      <Button tone="secondary" onClick={() => setEnrolTarget(null)} disabled={busy}>
                        取消
                      </Button>
                    </div>
                  </div>
                ) : null}

                {actualTarget === cohort.cohort_code ? (
                  <div className="mt-3 rounded-xl bg-slate-50 p-3">
                    <DateTimeField label="实际开始日期" value={actualStart} onChange={setActualStart} disabled={busy} />
                    <div className="mt-2" />
                    <DateTimeField label="实际结束日期" value={actualEnd} onChange={setActualEnd} disabled={busy} />
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button onClick={() => void saveActualDates(cohort)} disabled={busy}>
                        保存实际日期
                      </Button>
                      <Button tone="secondary" onClick={() => setActualTarget(null)} disabled={busy}>
                        取消
                      </Button>
                    </div>
                  </div>
                ) : null}

                <p className="mt-2 text-xs text-slate-500">
                  入库与分配记录均以服务器时间为准；教学教师名单：
                  {cohort.teaching_user_ids.length ? `${cohort.teaching_user_ids.length} 人（用于盲法风险核对）` : "未登记"}
                  {" · "}
                  计划起止日期 {cohort.planned_start ?? "—"} 至 {cohort.planned_end ?? "—"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <StaffDirectoryNotice unavailable={directory.staffUnavailable} />
    </div>
  );
}
