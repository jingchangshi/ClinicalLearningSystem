"use client";

/**
 * R4.2/R4.5: freeze the two form orders, then draw the whole-batch allocation.
 *
 * The order is deliberate — a batch's form order is frozen before the group draw,
 * so the 35 equally likely whole-batch allocations really are the reference space
 * of the analysis. Neither draw can be repeated; the records are immutable.
 */
import { useCallback, useEffect, useState } from "react";

import { Button, Card, EmptyHint, Feedback, Moment, Pill, SyntheticNotice } from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  drawClusterAllocation,
  freezeFormOrder,
  getDesignAssignments,
  listStudyAllocations,
  type AllocationRow,
  type DesignAssignment,
} from "@/lib/assessmentApi";

import { DATA_ORIGIN_OPTIONS } from "./adminShared";
import type { useAdminDirectory } from "./adminShared";

type Directory = ReturnType<typeof useAdminDirectory>;

export function AllocationPanel({ directory }: { directory: Directory }) {
  const { cohorts, error, setError, reload } = directory;
  const [allocations, setAllocations] = useState<AllocationRow[]>([]);
  const [assignments, setAssignments] = useState<DesignAssignment[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [formOrder, setFormOrder] = useState({ data_origin: "pilot_test", protocol_version: "SAP-2026-10", seed: "" });
  const [cluster, setCluster] = useState({
    data_origin: "pilot_test",
    protocol_version: "SAP-2026-10",
    mode: "randomized",
    seed: "",
    clinpath_cohorts: [] as string[],
  });

  const load = useCallback(async () => {
    try {
      setAllocations(await listStudyAllocations());
    } catch (reason) {
      setAllocations([]);
      setError(assessmentErrorMessage(reason));
    }
  }, [setError]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    getDesignAssignments(cluster.data_origin)
      .then(setAssignments)
      .catch(() => setAssignments([]));
  }, [cluster.data_origin, allocations]);

  const frozenOrder = allocations.find(
    (row) => row.kind === "form_order" && row.data_origin === formOrder.data_origin,
  );
  const frozenCluster = allocations.find(
    (row) => row.kind === "cluster_group" && row.data_origin === cluster.data_origin,
  );

  async function doFreezeOrder() {
    setBusy(true);
    setError(null);
    try {
      const result = await freezeFormOrder({
        data_origin: formOrder.data_origin,
        protocol_version: formOrder.protocol_version,
        ...(formOrder.seed.trim() ? { seed: formOrder.seed.trim() } : {}),
      });
      setMessage(
        `题本顺序已冻结（记录版本 ${result.allocation_version}，指纹 ${result.content_hash.slice(0, 12)}…）。` +
          "冻结后不能重新抽签，入组名单也不能再调整。",
      );
      await load();
      await reload();
    } catch (reason) {
      setError(assessmentErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function doDrawCluster() {
    setBusy(true);
    setError(null);
    try {
      const result = await drawClusterAllocation({
        data_origin: cluster.data_origin,
        protocol_version: cluster.protocol_version,
        mode: cluster.mode,
        ...(cluster.seed.trim() ? { seed: cluster.seed.trim() } : {}),
        ...(cluster.mode === "quasi_experimental" ? { clinpath_cohorts: cluster.clinpath_cohorts } : {}),
      });
      setMessage(
        `教学组分配已登记（方式 ${result.mode === "randomized" ? "整批随机化" : "整群准实验"}）。` +
          `ClinPath 组：${result.clinpath_cohorts.join("、") || "—"}；CBL 组：${result.cbl_cohorts.join("、") || "—"}。` +
          "记录已冻结，不能为了取得更好结果重新抽签。",
      );
      await load();
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
        title="① 冻结题本顺序（先做这一步）"
        description="X：T0 用 A01、T1 用 A02；Y：T0 用 A02、T1 用 A01。每批 7 人内部按约 4/3 分配 X/Y。"
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">
            <span className="text-slate-600">数据来源</span>
            <select
              aria-label="题本顺序数据来源"
              value={formOrder.data_origin}
              onChange={(event) => setFormOrder({ ...formOrder, data_origin: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              {DATA_ORIGIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">研究方案版本</span>
            <input
              aria-label="研究方案版本"
              value={formOrder.protocol_version}
              onChange={(event) => setFormOrder({ ...formOrder, protocol_version: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">随机种子（留空由服务器生成并记录）</span>
            <input
              aria-label="题本顺序随机种子"
              value={formOrder.seed}
              onChange={(event) => setFormOrder({ ...formOrder, seed: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
              placeholder="至少 8 个字符"
            />
          </label>
        </div>
        <p className="mt-3 text-sm text-slate-600">
          需要 7 个已完成入组的批次。执行人、时间、算法、种子与研究方案版本都会写入分配记录。
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={() => void doFreezeOrder()} disabled={busy || Boolean(frozenOrder)}>
            {frozenOrder ? "题本顺序已冻结" : "冻结题本顺序"}
          </Button>
          {frozenOrder ? <Pill tone="clinic">已冻结 · {frozenOrder.content_hash.slice(0, 12)}…</Pill> : null}
        </div>
        <SyntheticNotice dataOrigin={formOrder.data_origin} />
      </Card>

      <Card
        title="② 整批教学组分配"
        description="随机化单位是完整批次：一批 7 人只能在同一研究臂。预设 3 批 ClinPath、4 批 CBL，35 种合法整批分配等概率。"
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">
            <span className="text-slate-600">数据来源</span>
            <select
              aria-label="分配数据来源"
              value={cluster.data_origin}
              onChange={(event) => setCluster({ ...cluster, data_origin: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              {DATA_ORIGIN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">分配方式</span>
            <select
              aria-label="分配方式"
              value={cluster.mode}
              onChange={(event) => setCluster({ ...cluster, mode: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              <option value="randomized">整批随机化（randomized）</option>
              <option value="quasi_experimental">整群准实验（quasi_experimental，无法随机化时）</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">随机种子（留空由服务器生成并记录）</span>
            <input
              aria-label="分配随机种子"
              value={cluster.seed}
              onChange={(event) => setCluster({ ...cluster, seed: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
              placeholder="至少 8 个字符"
            />
          </label>
        </div>

        {cluster.mode === "quasi_experimental" ? (
          <div className="mt-3 rounded-lg bg-slate-50 p-3">
            <p className="text-sm text-slate-600">
              准实验模式下需要指定进入 ClinPath 组的批次。系统会如实记录 quasi_experimental，
              不会据此生成随机化检验结论。
            </p>
            <div className="mt-2 grid gap-1 sm:grid-cols-4">
              {cohorts.map((cohort) => (
                <label key={cohort.cohort_code} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={cluster.clinpath_cohorts.includes(cohort.cohort_code)}
                    onChange={(event) =>
                      setCluster((current) => ({
                        ...current,
                        clinpath_cohorts: event.target.checked
                          ? [...current.clinpath_cohorts, cohort.cohort_code]
                          : current.clinpath_cohorts.filter((code) => code !== cohort.cohort_code),
                      }))
                    }
                  />
                  <span>{cohort.cohort_code}</span>
                </label>
              ))}
            </div>
          </div>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={() => void doDrawCluster()} disabled={busy || !frozenOrder || Boolean(frozenCluster)}>
            {frozenCluster ? "分配已登记" : "执行整批分配"}
          </Button>
          {!frozenOrder ? <span className="text-xs text-amber-800">必须先冻结题本顺序。</span> : null}
          {frozenCluster ? <Pill tone="clinic">已登记 · {frozenCluster.content_hash.slice(0, 12)}…</Pill> : null}
        </div>
        <SyntheticNotice dataOrigin={cluster.data_origin} />
      </Card>

      <Card title="分配记录（不可变）" description="已冻结的记录不会因为结果不理想而重新抽签。">
        {allocations.length === 0 ? (
          <EmptyHint>还没有分配记录。</EmptyHint>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-3 py-2">类型</th>
                  <th className="px-3 py-2">方式</th>
                  <th className="px-3 py-2">数据来源</th>
                  <th className="px-3 py-2">方案版本</th>
                  <th className="px-3 py-2">结果</th>
                  <th className="px-3 py-2">指纹</th>
                  <th className="px-3 py-2">执行时间</th>
                </tr>
              </thead>
              <tbody>
                {allocations.map((row) => (
                  <tr key={row.allocation_version} className="border-b border-slate-100 align-top">
                    <td className="px-3 py-2">{row.kind === "form_order" ? "题本顺序" : "教学组分配"}</td>
                    <td className="px-3 py-2">{row.mode}</td>
                    <td className="px-3 py-2">
                      <Pill tone={row.data_origin === "real_study" ? "clinic" : "warn"}>
                        {row.data_origin === "real_study" ? "真实研究" : "测试/合成"}
                      </Pill>
                    </td>
                    <td className="px-3 py-2">{row.protocol_version}</td>
                    <td className="px-3 py-2 text-xs">
                      {row.kind === "cluster_group" ? (
                        <ul>
                          <li>ClinPath：{(row.record.clinpath_cohorts as string[] | undefined)?.join("、") ?? "—"}</li>
                          <li>CBL：{(row.record.cbl_cohorts as string[] | undefined)?.join("、") ?? "—"}</li>
                        </ul>
                      ) : (
                        <span>{(row.record.cohorts as string[] | undefined)?.join("、") ?? "—"}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{row.content_hash.slice(0, 12)}…</td>
                    <td className="px-3 py-2 text-slate-600">
                      <Moment value={row.executed_at} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="批次与学生的组别、题本顺序" description="这张表是排考的依据：学生的组别与题本顺序来自冻结记录，不能手工指定。">
        {assignments.length === 0 ? (
          <EmptyHint>还没有可显示的分配结果（需要先冻结记录）。</EmptyHint>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-3 py-2">研究编码</th>
                  <th className="px-3 py-2">批次</th>
                  <th className="px-3 py-2">组别</th>
                  <th className="px-3 py-2">题本顺序</th>
                  <th className="px-3 py-2">状态</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((row) => (
                  <tr key={`${row.cohort_code}-${row.student_id}`} className="border-b border-slate-100">
                    <td className="px-3 py-2 font-mono text-xs">{row.study_student_code ?? "—"}</td>
                    <td className="px-3 py-2">{row.cohort_code}</td>
                    <td className="px-3 py-2">{row.study_group ?? "—"}</td>
                    <td className="px-3 py-2">{row.form_order ?? "—"}</td>
                    <td className="px-3 py-2">{row.enrollment_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
