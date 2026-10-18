"use client";

/** Every administrator action that matters is in this log; it is read-only here. */
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button, Card, EmptyHint, Feedback, Moment, Pill } from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  listAssessmentAudit,
  listAssessmentStaff,
  type AuditRow,
  type StaffAccount,
} from "@/lib/assessmentApi";

const ROLE_LABELS: Record<string, string> = { admin: "研究管理员", teacher: "教师", student: "学生" };

export function AuditPanel() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [staff, setStaff] = useState<StaffAccount[]>([]);
  const [actionFilter, setActionFilter] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await listAssessmentAudit(undefined, 500));
      setError(null);
    } catch (why) {
      setError(assessmentErrorMessage(why));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
    listAssessmentStaff()
      .then(setStaff)
      .catch(() => setStaff([]));
  }, [load]);

  const staffById = useMemo(() => new Map(staff.map((account) => [account.user_id, account])), [staff]);
  const actions = useMemo(() => [...new Set(rows.map((row) => row.action))].sort(), [rows]);
  const visible = actionFilter === "all" ? rows : rows.filter((row) => row.action === actionFilter);

  function actorLabel(actorUserId: number | null): string {
    if (actorUserId === null) return "系统";
    const account = staffById.get(actorUserId);
    return account ? account.display_name : `账号 #${actorUserId}`;
  }

  function targetLabel(target: string): string {
    // The audit endpoint sends "type:id"; read it as a record reference, not a raw id.
    const [type, ...rest] = target.split(":");
    const id = rest.join(":");
    const typeLabel =
      { form: "题本", sitting: "考试", review: "评分记录", cohort: "批次", allocation: "分配记录",
        dataset: "数据集", research_codes: "研究编码", design: "研究设计" }[type] ?? type;
    return id ? `${typeLabel} · ${id}` : typeLabel;
  }

  return (
    <div className="space-y-4">
      <Feedback error={error} />

      <Card
        title="考核审计日志"
        description="创建、指派、发布、延长、补考、锁定成绩、读取身份映射等操作都会留痕。日志只读，不能在界面上修改或删除。"
        actions={
          <>
            <label className="text-sm">
              <span className="sr-only">操作类型筛选</span>
              <select
                aria-label="操作类型筛选"
                value={actionFilter}
                onChange={(event) => setActionFilter(event.target.value)}
                className="rounded-md border border-slate-300 p-2"
              >
                <option value="all">全部操作（{rows.length}）</option>
                {actions.map((action) => (
                  <option key={action} value={action}>
                    {action}
                  </option>
                ))}
              </select>
            </label>
            <Button tone="secondary" onClick={() => void load()} disabled={busy}>
              刷新
            </Button>
          </>
        }
      >
        {visible.length === 0 ? (
          <EmptyHint>没有符合条件的审计记录。</EmptyHint>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-3 py-2">时间</th>
                  <th className="px-3 py-2">操作</th>
                  <th className="px-3 py-2">执行人</th>
                  <th className="px-3 py-2">对象</th>
                  <th className="px-3 py-2">详情</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.id} className="border-b border-slate-100 align-top">
                    <td className="px-3 py-2 whitespace-nowrap text-slate-600">
                      <Moment value={row.at} />
                    </td>
                    <td className="px-3 py-2">
                      <Pill>{row.action}</Pill>
                    </td>
                    <td className="px-3 py-2">
                      {actorLabel(row.actor_user_id)}
                      {row.actor_role ? (
                        <p className="text-xs text-slate-500">
                          {ROLE_LABELS[row.actor_role] ?? row.actor_role}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 text-xs">{targetLabel(row.target)}</td>
                    <td className="px-3 py-2 text-xs text-slate-600">
                      {Object.keys(row.detail).length
                        ? Object.entries(row.detail)
                            .map(([key, value]) => `${key}=${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
                            .join("；")
                        : "—"}
                    </td>
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
