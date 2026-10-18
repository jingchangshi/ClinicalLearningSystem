"use client";

/**
 * R2.3/R3.3/R4.6: the sitting list an administrator actually works from.
 *
 * Students appear by research code. Real names come only from the audited
 * identity-map call, which is an explicit action and writes its own audit entry.
 * Every row says which origin it belongs to, so test data is never mistaken for
 * the 49-student study.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Button,
  Card,
  EmptyHint,
  Feedback,
  Moment,
  Pill,
  SyntheticNotice,
} from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  assignAssessmentSitting,
  blindingRiskLabel,
  dataOriginLabel,
  extendAssessmentSitting,
  finalizeAssessmentSitting,
  fromLocalInputValue,
  getAssessmentIdentityMap,
  getAssessmentSitting,
  listAssessmentSittings,
  retakeAssessmentSitting,
  scoringProvenanceLabel,
  sittingStatusLabel,
  sweepExpiredSittings,
  type IdentityRow,
  type SittingDetail,
  type SittingRow,
} from "@/lib/assessmentApi";

import {
  DATA_ORIGIN_OPTIONS,
  DateTimeField,
  OriginBadgeCell,
  PublishedFormSelect,
  StaffDirectoryNotice,
  StaffSelect,
  StudentSelect,
} from "./adminShared";
import type { useAdminDirectory } from "./adminShared";

type Directory = ReturnType<typeof useAdminDirectory>;

const STATUS_OPTIONS = ["assigned", "in_progress", "submitted", "expired", "voided"];

export function SittingPanel({ directory }: { directory: Directory }) {
  const { students, cohorts, forms, staff, staffUnavailable, error, setError, reload } = directory;
  const [sittings, setSittings] = useState<SittingRow[]>([]);
  const [originFilter, setOriginFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [expanded, setExpanded] = useState<SittingDetail | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [identity, setIdentity] = useState<IdentityRow[] | null>(null);
  const [action, setAction] = useState<{ kind: "extend" | "retake"; sitting: SittingRow } | null>(null);
  const [extendEnd, setExtendEnd] = useState("");
  const [retakeStart, setRetakeStart] = useState("");
  const [retakeEnd, setRetakeEnd] = useState("");
  const [reason, setReason] = useState("");
  const [assign, setAssign] = useState({
    student_id: null as number | null,
    form_id: null as number | null,
    cohort_code: "",
    study_group: "CLINPATH",
    timepoint: "T0",
    data_origin: "pilot_test",
    window_start: "",
    window_end: "",
    rater_a_id: null as number | null,
    rater_b_id: null as number | null,
    adjudicator_user_id: null as number | null,
  });

  const load = useCallback(async () => {
    try {
      setSittings(await listAssessmentSittings());
    } catch (why) {
      setSittings([]);
      setError(assessmentErrorMessage(why));
    }
  }, [setError]);

  useEffect(() => {
    void load();
  }, [load]);

  const nameByStudent = useMemo(() => {
    const map = new Map<number, string>();
    for (const row of identity ?? []) map.set(row.student_id, `${row.name}（${row.student_no}）`);
    return map;
  }, [identity]);

  const rows = sittings.filter(
    (row) =>
      (originFilter === "all" || row.data_origin === originFilter) &&
      (statusFilter === "all" || row.status === statusFilter),
  );

  const summary = useMemo(() => {
    const realRows = rows.filter((row) => row.data_origin === "real_study");
    return {
      total: rows.length,
      submitted: rows.filter((row) => row.status === "submitted").length,
      expired: rows.filter((row) => row.status === "expired").length,
      dualRated: rows.filter((row) => row.reviews === 2).length,
      flagged: rows.filter((row) => row.disagreement?.flagged).length,
      finalized: rows.filter((row) => row.final_score !== null).length,
      realStudy: realRows.length,
    };
  }, [rows]);

  async function openDetail(sitting: SittingRow) {
    setBusy(true);
    try {
      const detail = await getAssessmentSitting(sitting.id);
      setExpanded(expanded?.id === detail.id ? null : detail);
      setError(null);
    } catch (why) {
      setError(assessmentErrorMessage(why));
    } finally {
      setBusy(false);
    }
  }

  async function runAction(run: () => Promise<string>) {
    setBusy(true);
    setError(null);
    try {
      setMessage(await run());
      setAction(null);
      setReason("");
      setExpanded(null);
      await load();
      await reload();
    } catch (why) {
      setError(assessmentErrorMessage(why));
    } finally {
      setBusy(false);
    }
  }

  async function doExtend(sitting: SittingRow) {
    const end = fromLocalInputValue(extendEnd);
    if (!end || reason.trim().length < 5) {
      setError("请填写新的结束时间与延长原因（至少 5 个字）。");
      return;
    }
    await runAction(async () => {
      const result = await extendAssessmentSitting(sitting.id, end, reason.trim());
      return `已延长窗口，当前结束时间 ${result.window_end}。延长操作已写入审计日志。`;
    });
  }

  async function doRetake(sitting: SittingRow) {
    const start = fromLocalInputValue(retakeStart);
    const end = fromLocalInputValue(retakeEnd);
    if (!start || !end || reason.trim().length < 5) {
      setError("请填写补考窗口的开始/结束时间与补考原因（至少 5 个字）。");
      return;
    }
    await runAction(async () => {
      await retakeAssessmentSitting(sitting.id, { reason: reason.trim(), window_start: start, window_end: end });
      return "原考试已作废并登记补考机会；研究数据集中只会保留一条有效记录。";
    });
  }

  async function doFinalize(sitting: SittingRow) {
    await runAction(async () => {
      const result = await finalizeAssessmentSitting(sitting.id);
      return `最终成绩已锁定：${result.final_score}（来源：${scoringProvenanceLabel(result.scoring_provenance)}）${
        result.already_locked ? "（此前已锁定）" : ""
      }。`;
    });
  }

  async function doSweep() {
    await runAction(async () => {
      const result = await sweepExpiredSittings();
      return `已扫描并关闭 ${result.expired} 场超出窗口且未提交的考试。`;
    });
  }

  async function doAssign() {
    const start = fromLocalInputValue(assign.window_start);
    const end = fromLocalInputValue(assign.window_end);
    if (!assign.student_id || !assign.form_id || !assign.cohort_code) {
      setError("请选择学生、已发布题本与批次。");
      return;
    }
    if (!start || !end) {
      setError("请填写考试窗口的开始与结束时间。");
      return;
    }
    if (!assign.rater_a_id || !assign.rater_b_id || assign.rater_a_id === assign.rater_b_id) {
      setError("请选择两位不同的评分者。");
      return;
    }
    await runAction(async () => {
      const result = await assignAssessmentSitting({
        student_id: assign.student_id as number,
        form_id: assign.form_id as number,
        cohort_code: assign.cohort_code,
        study_group: assign.study_group,
        timepoint: assign.timepoint,
        window_start: start,
        window_end: end,
        rater_a_id: assign.rater_a_id as number,
        rater_b_id: assign.rater_b_id as number,
        ...(assign.adjudicator_user_id ? { adjudicator_user_id: assign.adjudicator_user_id } : {}),
        data_origin: assign.data_origin,
      });
      return `已分配考试。盲法状态：${blindingRiskLabel(result.blinding_risk)}。`;
    });
  }

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      <Card
        title="考试与评分总览"
        description="按数据来源分开统计：测试/合成数据不会被计入真实研究。"
        actions={
          <>
            <Button tone="secondary" onClick={() => void load()} disabled={busy}>
              刷新
            </Button>
            <Button tone="secondary" onClick={() => void doSweep()} disabled={busy}>
              扫描过期窗口
            </Button>
            <Button
              tone="secondary"
              onClick={() =>
                void (async () => {
                  try {
                    setIdentity(await getAssessmentIdentityMap());
                    setMessage("已读取身份映射（本次读取已写入审计日志）。表内将同时显示学生姓名。");
                  } catch (why) {
                    setError(assessmentErrorMessage(why));
                  }
                })()
              }
              disabled={busy}
            >
              查看身份映射（写入审计日志）
            </Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-7">
          {[
            ["考试总数", summary.total],
            ["已提交", summary.submitted],
            ["过期未交", summary.expired],
            ["完成双评", summary.dualRated],
            ["进入裁决", summary.flagged],
            ["已锁定成绩", summary.finalized],
            ["真实研究记录", summary.realStudy],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs text-slate-500">{label}</p>
              <p className="text-xl font-semibold text-ink">{value}</p>
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <label className="text-sm">
            <span className="text-slate-600">数据来源筛选</span>
            <select
              aria-label="数据来源筛选"
              value={originFilter}
              onChange={(event) => setOriginFilter(event.target.value)}
              className="mt-1 block rounded-md border border-slate-300 p-2"
            >
              <option value="all">全部</option>
              {DATA_ORIGIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.value}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">状态筛选</span>
            <select
              aria-label="状态筛选"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="mt-1 block rounded-md border border-slate-300 p-2"
            >
              <option value="all">全部</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {sittingStatusLabel(status)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {originFilter !== "all" ? <SyntheticNotice dataOrigin={originFilter} /> : null}
      </Card>

      <Card title="考试清单" description="评分进度、分歧与最终成绩来源一目了然；管理员只能锁定，不能改写评分。">
        {rows.length === 0 ? (
          <EmptyHint>没有符合条件的考试记录。</EmptyHint>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1040px] text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-3 py-2">研究编码</th>
                  {identity ? <th className="px-3 py-2">姓名</th> : null}
                  <th className="px-3 py-2">批次/组别/时点</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">窗口</th>
                  <th className="px-3 py-2">评分</th>
                  <th className="px-3 py-2">最终成绩</th>
                  <th className="px-3 py-2">数据来源</th>
                  <th className="px-3 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-slate-100 align-top">
                    <td className="px-3 py-2 font-mono text-xs">{row.study_student_code ?? "—"}</td>
                    {identity ? <td className="px-3 py-2">{nameByStudent.get(row.student_id) ?? "—"}</td> : null}
                    <td className="px-3 py-2">
                      <p>
                        {row.cohort_code} · {row.study_group}
                      </p>
                      <p className="text-xs text-slate-500">
                        {row.timepoint} · 第 {row.attempt_no} 次
                        {row.form_order ? ` · 题本顺序 ${row.form_order}` : ""}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">{blindingRiskLabel(row.blinding_risk)}</p>
                    </td>
                    <td className="px-3 py-2">
                      <Pill
                        tone={
                          row.status === "submitted"
                            ? "clinic"
                            : row.status === "expired"
                              ? "alert"
                              : row.status === "voided"
                                ? "slate"
                                : "warn"
                        }
                      >
                        {sittingStatusLabel(row.status)}
                      </Pill>
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-600">
                      <Moment value={row.window_start} />
                      <br />
                      <Moment value={row.window_end} />
                    </td>
                    <td className="px-3 py-2">
                      <p>{row.reviews} / 2 位评分者已提交</p>
                      {row.disagreement?.flagged ? (
                        <p className="mt-1 text-xs text-amber-800">
                          分歧：总分差 {row.disagreement.total_diff}
                          {row.adjudicated ? " · 已裁决" : " · 待裁决"}
                        </p>
                      ) : row.disagreement ? (
                        <p className="mt-1 text-xs text-slate-500">分歧在阈值内</p>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">
                      {row.final_score === null ? (
                        <span className="text-slate-500">未锁定</span>
                      ) : (
                        <>
                          <p className="font-semibold text-ink">{row.final_score}</p>
                          <p className="text-xs text-slate-500">{scoringProvenanceLabel(row.scoring_provenance)}</p>
                          {row.dataset_lock_id ? <Pill tone="clinic">已入数据集</Pill> : null}
                        </>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <OriginBadgeCell dataOrigin={row.data_origin} />
                      <p className="mt-1 text-xs text-slate-500">{dataOriginLabel(row.data_origin)}</p>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        <Button tone="secondary" onClick={() => void openDetail(row)} disabled={busy}>
                          明细
                        </Button>
                        <Button
                          tone="secondary"
                          onClick={() => {
                            setAction({ kind: "extend", sitting: row });
                            setExtendEnd("");
                            setReason("");
                          }}
                          disabled={busy || row.status === "submitted" || row.status === "voided"}
                        >
                          延长窗口
                        </Button>
                        <Button
                          tone="secondary"
                          onClick={() => {
                            setAction({ kind: "retake", sitting: row });
                            setRetakeStart("");
                            setRetakeEnd("");
                            setReason("");
                          }}
                          disabled={busy || row.status === "voided" || row.final_score !== null}
                        >
                          补考
                        </Button>
                        <Button
                          onClick={() => void doFinalize(row)}
                          disabled={busy || row.final_score !== null || row.status !== "submitted"}
                          title={row.status !== "submitted" ? "只有已提交的答卷可以锁定成绩" : undefined}
                        >
                          锁定成绩
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {expanded ? (
          <div className="mt-4 rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-ink">
                考试明细 {expanded.study_student_code ?? ""} · {expanded.cohort_code} · {expanded.timepoint}
              </h3>
              <Button tone="secondary" onClick={() => setExpanded(null)}>
                收起
              </Button>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              盲评编码 {expanded.blind_code.slice(0, 10)}… · 数据来源 {dataOriginLabel(expanded.data_origin)} · 提交时间{" "}
              <Moment value={expanded.submitted_at} />
            </p>
            <ol className="mt-3 space-y-1 text-sm text-slate-700">
              {expanded.events.map((event, index) => (
                <li key={index} className="flex flex-wrap items-baseline gap-2 border-b border-slate-100 py-1">
                  <span className="text-xs text-slate-500">
                    <Moment value={event.at} />
                  </span>
                  <span className="font-medium">{event.type}</span>
                  {Object.keys(event.detail).length ? (
                    <span className="text-xs text-slate-600">
                      {Object.entries(event.detail)
                        .map(([key, value]) => `${key}=${String(value)}`)
                        .join("，")}
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>
            {expanded.events.length === 0 ? <p className="text-sm text-slate-500">还没有作答事件记录。</p> : null}
          </div>
        ) : null}
      </Card>

      {action ? (
        <Card
          title={action.kind === "extend" ? "延长考试窗口" : "登记补考"}
          description={
            action.kind === "extend"
              ? "用于已记录的中断或故障。延长只改变这一名学生的窗口，并写入审计日志。"
              : "补考会作废当前这次考试并新开一场；已评分或已锁定成绩的考试不能补考。"
          }
          actions={
            <Button tone="secondary" onClick={() => setAction(null)} disabled={busy}>
              取消
            </Button>
          }
        >
          <p className="text-sm text-slate-600">
            对象：{action.sitting.study_student_code ?? "（无编码）"} · {action.sitting.cohort_code} ·{" "}
            {action.sitting.timepoint} · 当前窗口结束 <Moment value={action.sitting.window_end} />
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {action.kind === "extend" ? (
              <DateTimeField label="新的窗口结束时间" value={extendEnd} onChange={setExtendEnd} disabled={busy} />
            ) : (
              <>
                <DateTimeField label="补考窗口开始" value={retakeStart} onChange={setRetakeStart} disabled={busy} />
                <DateTimeField label="补考窗口结束" value={retakeEnd} onChange={setRetakeEnd} disabled={busy} />
              </>
            )}
            <label className="text-sm sm:col-span-2">
              <span className="text-slate-600">原因（至少 5 个字，会进入审计日志）</span>
              <textarea
                rows={2}
                aria-label="操作原因"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 p-2"
                placeholder="例如：学生报告 10:35 校园网中断约 4 分钟，经教研室确认同意延长 15 分钟。"
              />
            </label>
          </div>
          <div className="mt-3">
            <Button
              onClick={() => void (action.kind === "extend" ? doExtend(action.sitting) : doRetake(action.sitting))}
              disabled={busy || reason.trim().length < 5}
            >
              {action.kind === "extend" ? "确认延长窗口" : "确认作废并补考"}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card title="单场分配（补排 / 特殊安排）" description="批量排考之外的个案安排。组别必须与已冻结的批次分配一致。">
        <StaffDirectoryNotice unavailable={staffUnavailable} />
        <div className="grid gap-3 sm:grid-cols-3">
          <StudentSelect
            label="学生"
            value={assign.student_id}
            onChange={(value) => setAssign({ ...assign, student_id: value })}
            students={students}
            disabled={busy}
          />
          <PublishedFormSelect
            label="题本（已发布）"
            value={assign.form_id}
            onChange={(value) => setAssign({ ...assign, form_id: value })}
            forms={forms}
            disabled={busy}
          />
          <label className="text-sm">
            <span className="text-slate-600">批次</span>
            <select
              aria-label="批次"
              value={assign.cohort_code}
              onChange={(event) => setAssign({ ...assign, cohort_code: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              <option value="">请选择批次</option>
              {cohorts.map((cohort) => (
                <option key={cohort.cohort_code} value={cohort.cohort_code}>
                  {cohort.cohort_code} · {cohort.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">研究组别</span>
            <select
              aria-label="研究组别"
              value={assign.study_group}
              onChange={(event) => setAssign({ ...assign, study_group: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              <option value="CLINPATH">ClinPath 组</option>
              <option value="CBL">常规 CBL 组</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">时点</span>
            <select
              aria-label="时点"
              value={assign.timepoint}
              onChange={(event) => setAssign({ ...assign, timepoint: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              <option value="T0">T0（D1 基线）</option>
              <option value="T1">T1（D6 后测）</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">数据来源</span>
            <select
              aria-label="分配数据来源"
              value={assign.data_origin}
              onChange={(event) => setAssign({ ...assign, data_origin: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              {DATA_ORIGIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <DateTimeField
            label="窗口开始"
            value={assign.window_start}
            onChange={(value) => setAssign({ ...assign, window_start: value })}
            disabled={busy}
          />
          <DateTimeField
            label="窗口结束"
            value={assign.window_end}
            onChange={(value) => setAssign({ ...assign, window_end: value })}
            disabled={busy}
          />
          <StaffSelect
            label="评分者 A"
            value={assign.rater_a_id}
            onChange={(value) => setAssign({ ...assign, rater_a_id: value })}
            staff={staff}
            disabled={busy}
          />
          <StaffSelect
            label="评分者 B"
            value={assign.rater_b_id}
            onChange={(value) => setAssign({ ...assign, rater_b_id: value })}
            staff={staff}
            exclude={assign.rater_a_id ? [assign.rater_a_id] : []}
            disabled={busy}
          />
          <StaffSelect
            label="裁决人（可选）"
            value={assign.adjudicator_user_id}
            onChange={(value) => setAssign({ ...assign, adjudicator_user_id: value })}
            staff={staff}
            exclude={[assign.rater_a_id, assign.rater_b_id].filter((value): value is number => typeof value === "number")}
            allowEmpty
            disabled={busy}
          />
        </div>
        <p className="mt-3 text-sm text-slate-600">
          正式研究（real_study）的考试必须已有批次登记与冻结的分配记录，系统会拒绝不一致的组别或时点。
        </p>
        <div className="mt-3">
          <Button onClick={() => void doAssign()} disabled={busy}>
            分配考试
          </Button>
        </div>
        <SyntheticNotice dataOrigin={assign.data_origin} />
      </Card>
    </div>
  );
}
