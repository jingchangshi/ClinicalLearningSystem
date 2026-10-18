"use client";

/**
 * R4.4/R4.5: create every enrolled student's T0 and T1 sitting in one action.
 *
 * Forms and windows come from the administrator; group and form order come from
 * the frozen allocation records and are never typed here. The server refuses the
 * whole batch unless every cohort has both windows and the records are frozen.
 */
import { useMemo, useState } from "react";

import { Button, Card, EmptyHint, Feedback, Pill, SyntheticNotice } from "@/components/assessment/AssessmentUi";
import { assessmentErrorMessage, fromLocalInputValue, scheduleStudySittings } from "@/lib/assessmentApi";

import { DATA_ORIGIN_OPTIONS, DateTimeField, PublishedFormSelect, StaffDirectoryNotice, StaffSelect } from "./adminShared";
import type { useAdminDirectory } from "./adminShared";

type Directory = ReturnType<typeof useAdminDirectory>;

type WindowPair = { T0: { start: string; end: string }; T1: { start: string; end: string } };

function emptyWindows(): Record<string, WindowPair> {
  return {};
}

/** Local `datetime-local` strings → the offset-aware instants the API requires. */
function toPayload(windows: Record<string, WindowPair>) {
  const payload: Record<string, { T0: { start: string; end: string }; T1: { start: string; end: string } }> = {};
  for (const [cohort, pair] of Object.entries(windows)) {
    const t0Start = fromLocalInputValue(pair.T0.start);
    const t0End = fromLocalInputValue(pair.T0.end);
    const t1Start = fromLocalInputValue(pair.T1.start);
    const t1End = fromLocalInputValue(pair.T1.end);
    if (!t0Start || !t0End || !t1Start || !t1End) throw new Error(`批次 ${cohort} 的时间窗口没有填完整。`);
    payload[cohort] = {
      T0: { start: t0Start, end: t0End },
      T1: { start: t1Start, end: t1End },
    };
  }
  return payload;
}

export function SchedulePanel({ directory }: { directory: Directory }) {
  const { cohorts, forms, staff, staffUnavailable, error, setError, reload } = directory;
  const [dataOrigin, setDataOrigin] = useState("pilot_test");
  const [formA01, setFormA01] = useState<number | null>(null);
  const [formA02, setFormA02] = useState<number | null>(null);
  const [raterA, setRaterA] = useState<number | null>(null);
  const [raterB, setRaterB] = useState<number | null>(null);
  const [adjudicator, setAdjudicator] = useState<number | null>(null);
  const [windows, setWindows] = useState<Record<string, WindowPair>>(emptyWindows);
  const [bulkT0, setBulkT0] = useState("");
  const [bulkT1, setBulkT1] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const originCohorts = useMemo(
    () => cohorts.filter((cohort) => cohort.data_origin === dataOrigin),
    [cohorts, dataOrigin],
  );
  const complete = originCohorts.filter((cohort) => cohort.enrolled === cohort.expected_size).length;

  function setWindow(cohortCode: string, timepoint: "T0" | "T1", key: "start" | "end", value: string) {
    setWindows((current) => {
      const pair = current[cohortCode] ?? { T0: { start: "", end: "" }, T1: { start: "", end: "" } };
      return { ...current, [cohortCode]: { ...pair, [timepoint]: { ...pair[timepoint], [key]: value } } };
    });
  }

  /** The common case: every batch runs D1 and D6 at the same hour on its own dates. */
  function applyBulk() {
    if (!bulkT0 || !bulkT1) {
      setError("请先填写要统一套用的 T0 与 T1 起始时间。");
      return;
    }
    const plusTwoHours = (value: string) => {
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return "";
      parsed.setHours(parsed.getHours() + 2);
      const pad = (n: number) => String(n).padStart(2, "0");
      return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
    };
    setWindows((current) => {
      const next = { ...current };
      for (const cohort of originCohorts) {
        next[cohort.cohort_code] = {
          T0: { start: bulkT0, end: plusTwoHours(bulkT0) },
          T1: { start: bulkT1, end: plusTwoHours(bulkT1) },
        };
      }
      return next;
    });
    setError(null);
  }

  async function submit() {
    if (!formA01 || !formA02) {
      setError("请选择 A01 与 A02 的已发布题本。");
      return;
    }
    if (formA01 === formA02) {
      setError("A01 与 A02 必须是两个不同的已发布题本。");
      return;
    }
    if (!raterA || !raterB || raterA === raterB) {
      setError("请选择两位不同的评分者。");
      return;
    }
    if (originCohorts.length === 0) {
      setError("该数据来源下没有批次记录。");
      return;
    }
    let payload;
    const pairs: Record<string, WindowPair> = {};
    for (const cohort of originCohorts) {
      pairs[cohort.cohort_code] = windows[cohort.cohort_code] ?? { T0: { start: "", end: "" }, T1: { start: "", end: "" } };
    }
    try {
      payload = toPayload(pairs);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "时间窗口不完整。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await scheduleStudySittings({
        data_origin: dataOrigin,
        forms: { A01: formA01, A02: formA02 },
        windows: payload,
        rater_a_id: raterA,
        rater_b_id: raterB,
        ...(adjudicator ? { adjudicator_user_id: adjudicator } : {}),
      });
      setMessage(
        `已为 ${originCohorts.length} 个批次建立 ${result.created} 场考试（每人 T0 与 T1 各一场，题本按冻结的 X/Y 顺序分配）。`,
      );
      await reload();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      <Card
        title="批量排考（7 批 × 7 人 × T0/T1）"
        description="按 R4 设计：每个人的 T0/T1 题本由冻结的题本顺序决定，组别来自冻结的整批分配记录。"
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">
            <span className="text-slate-600">数据来源</span>
            <select
              aria-label="排考数据来源"
              value={dataOrigin}
              onChange={(event) => {
                setDataOrigin(event.target.value);
                setWindows(emptyWindows());
              }}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              {DATA_ORIGIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <PublishedFormSelect
            label="A01 题本（已发布）"
            value={formA01}
            onChange={setFormA01}
            forms={forms}
            code="A01"
            disabled={busy}
          />
          <PublishedFormSelect
            label="A02 题本（已发布）"
            value={formA02}
            onChange={setFormA02}
            forms={forms}
            code="A02"
            disabled={busy}
          />
        </div>
        {forms.filter((form) => form.review_status === "APPROVED_FOR_ASSESSMENT").length < 2 ? (
          <p className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            目前已发布的题本不足两套。必须先在「题本审核状态与发布」中由两位教师审核并发布 A01 与 A02，才能批量排考。
          </p>
        ) : null}

        <StaffDirectoryNotice unavailable={staffUnavailable} />
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <StaffSelect label="评分者 A" value={raterA} onChange={setRaterA} staff={staff} disabled={busy} />
          <StaffSelect
            label="评分者 B"
            value={raterB}
            onChange={setRaterB}
            staff={staff}
            exclude={raterA ? [raterA] : []}
            disabled={busy}
          />
          <StaffSelect
            label="裁决人（可选，不能是评分者）"
            value={adjudicator}
            onChange={setAdjudicator}
            staff={staff}
            exclude={[raterA, raterB].filter((value): value is number => typeof value === "number")}
            allowEmpty
            disabled={busy}
          />
        </div>
        <p className="mt-2 text-xs text-slate-500">
          若评分者本人承担该批次教学任务，系统会在考试记录上标注盲法风险；真正盲法需由研究负责人安排独立评分人。
        </p>

        <div className="mt-4 rounded-xl bg-slate-50 p-3">
          <p className="text-sm font-medium text-ink">统一套用时间（可选）</p>
          <p className="mt-1 text-xs text-slate-500">
            常用于所有批次在同一钟点考试；填写后点击套用，再按各批次实际日期微调。窗口默认 2 小时。
          </p>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            <DateTimeField label="T0 起始时间（统一套用）" value={bulkT0} onChange={setBulkT0} disabled={busy} />
            <DateTimeField label="T1 起始时间（统一套用）" value={bulkT1} onChange={setBulkT1} disabled={busy} />
            <div className="flex items-end">
              <Button tone="secondary" onClick={applyBulk} disabled={busy || originCohorts.length === 0}>
                应用到 {originCohorts.length} 个批次
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {originCohorts.length === 0 ? (
            <EmptyHint>该数据来源下还没有批次。</EmptyHint>
          ) : (
            originCohorts.map((cohort) => (
              <div key={cohort.cohort_code} className="rounded-xl border border-slate-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-ink">
                    {cohort.cohort_code} · {cohort.label}
                  </p>
                  <Pill tone={cohort.enrolled === cohort.expected_size ? "clinic" : "alert"}>
                    已入组 {cohort.enrolled} / {cohort.expected_size}
                  </Pill>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <DateTimeField
                    label={`${cohort.cohort_code} T0 开始`}
                    value={windows[cohort.cohort_code]?.T0.start ?? ""}
                    onChange={(value) => setWindow(cohort.cohort_code, "T0", "start", value)}
                    disabled={busy}
                  />
                  <DateTimeField
                    label={`${cohort.cohort_code} T0 结束`}
                    value={windows[cohort.cohort_code]?.T0.end ?? ""}
                    onChange={(value) => setWindow(cohort.cohort_code, "T0", "end", value)}
                    disabled={busy}
                  />
                  <DateTimeField
                    label={`${cohort.cohort_code} T1 开始`}
                    value={windows[cohort.cohort_code]?.T1.start ?? ""}
                    onChange={(value) => setWindow(cohort.cohort_code, "T1", "start", value)}
                    disabled={busy}
                  />
                  <DateTimeField
                    label={`${cohort.cohort_code} T1 结束`}
                    value={windows[cohort.cohort_code]?.T1.end ?? ""}
                    onChange={(value) => setWindow(cohort.cohort_code, "T1", "end", value)}
                    disabled={busy}
                  />
                </div>
              </div>
            ))
          )}
        </div>

        <p className="mt-3 text-sm text-slate-600">
          名单完整的批次：{complete} / {originCohorts.length}。全部批次名单完整且已冻结分配记录后，批量排考才会成功。
        </p>

        <div className="mt-3">
          <Button onClick={() => void submit()} disabled={busy || originCohorts.length === 0}>
            {busy ? "正在排考…" : "批量排考（整批全有或全无）"}
          </Button>
        </div>
        <SyntheticNotice dataOrigin={dataOrigin} />
      </Card>
    </div>
  );
}
