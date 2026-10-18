"use client";

/** Pieces the study-admin panels share: pickers that show names, never ids. */
import { useCallback, useEffect, useState } from "react";

import { Pill } from "@/components/assessment/AssessmentUi";
import { listStudents, type Student } from "@/lib/api";
import {
  assessmentErrorMessage,
  listAllAssessmentForms,
  listAssessmentStaff,
  listStudyCohorts,
  type CohortRow,
  type FormSummary,
  type StaffAccount,
} from "@/lib/assessmentApi";

export const DATA_ORIGIN_OPTIONS = [
  { value: "pilot_test", label: "SYNTHETIC / SIMULATED_NOT_HUMAN · 软件验收测试" },
  { value: "synthetic_demo", label: "SYNTHETIC / SIMULATED_NOT_HUMAN · 合成演示" },
  { value: "real_study", label: "真实研究数据（49 名本科见习生）" },
] as const;

export function useAdminDirectory() {
  const [staff, setStaff] = useState<StaffAccount[]>([]);
  const [staffUnavailable, setStaffUnavailable] = useState(false);
  const [students, setStudents] = useState<Student[]>([]);
  const [cohorts, setCohorts] = useState<CohortRow[]>([]);
  const [forms, setForms] = useState<FormSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    listStudyCohorts()
      .then(setCohorts)
      .catch((reason) => setError(assessmentErrorMessage(reason)));
    listAllAssessmentForms()
      .then(setForms)
      .catch(() => setForms([]));
    listStudents()
      .then(setStudents)
      .catch(() => setStudents([]));
    try {
      setStaff(await listAssessmentStaff());
      setStaffUnavailable(false);
    } catch {
      setStaffUnavailable(true);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { staff, staffUnavailable, students, cohorts, forms, error, setError, reload };
}

/** Two different raters, by name; the API requires two distinct teacher accounts. */
export function StaffSelect({
  label,
  value,
  onChange,
  staff,
  teachersOnly = true,
  exclude = [],
  allowEmpty = false,
  disabled,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  staff: StaffAccount[];
  teachersOnly?: boolean;
  exclude?: number[];
  allowEmpty?: boolean;
  disabled?: boolean;
}) {
  const options = staff.filter(
    (account) => (!teachersOnly || account.role === "teacher") && !exclude.includes(account.user_id),
  );
  return (
    <label className="text-sm">
      <span className="text-slate-600">{label}</span>
      <select
        aria-label={label}
        value={value === null ? "" : String(value)}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
        className="mt-1 w-full rounded-md border border-slate-300 p-2"
      >
        <option value="">{allowEmpty ? "（不指定）" : "请选择教师账号"}</option>
        {options.map((account) => (
          <option key={account.user_id} value={account.user_id}>
            {account.display_name}
            {account.teacher_no ? `（${account.teacher_no}）` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

export function StudentSelect({
  label,
  value,
  onChange,
  students,
  disabled,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  students: Student[];
  disabled?: boolean;
}) {
  return (
    <label className="text-sm">
      <span className="text-slate-600">{label}</span>
      <select
        aria-label={label}
        value={value === null ? "" : String(value)}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
        className="mt-1 w-full rounded-md border border-slate-300 p-2"
      >
        <option value="">请选择学生</option>
        {students.map((student) => (
          <option key={student.id} value={student.id}>
            {student.name} · {student.student_no}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Only published versions may be scheduled into an exam. */
export function PublishedFormSelect({
  label,
  value,
  onChange,
  forms,
  code,
  disabled,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  forms: FormSummary[];
  code?: string;
  disabled?: boolean;
}) {
  const options = forms.filter(
    (form) => form.review_status === "APPROVED_FOR_ASSESSMENT" && (!code || form.code === code),
  );
  return (
    <label className="text-sm">
      <span className="text-slate-600">{label}</span>
      <select
        aria-label={label}
        value={value === null ? "" : String(value)}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
        className="mt-1 w-full rounded-md border border-slate-300 p-2"
      >
        <option value="">请选择已发布题本</option>
        {options.map((form) => (
          <option key={form.id} value={form.id}>
            {form.code} v{form.version} · {form.title}
          </option>
        ))}
      </select>
    </label>
  );
}

export function StaffDirectoryNotice({ unavailable }: { unavailable: boolean }) {
  if (!unavailable) return null;
  return (
    <p className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      人员目录接口（/api/assessments/admin/staff）当前不可用，无法按姓名选择评分者、审核人与裁决人。
      为避免在界面上暴露数据库 ID，这些选择框会保持为空；其余管理功能不受影响。
    </p>
  );
}

export function DateTimeField({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="text-sm">
      <span className="text-slate-600">{label}</span>
      <input
        type="datetime-local"
        aria-label={label}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-slate-300 p-2"
      />
      <span className="mt-1 block text-xs text-slate-500">按你所在时区填写，提交时自动转换为 UTC。</span>
    </label>
  );
}

export function OriginBadgeCell({ dataOrigin }: { dataOrigin: string }) {
  return <Pill tone={dataOrigin === "real_study" ? "clinic" : "warn"}>{dataOrigin === "real_study" ? "真实研究" : "测试/合成"}</Pill>;
}
