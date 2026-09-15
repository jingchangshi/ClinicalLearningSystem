"use client";

import { useMemo, useState } from "react";

import type { ResearchDataRow } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

/**
 * The page doubles as a research-data view and as a demo screen, so the table is
 * a *preview*: newest first, filtered, and it says out loud how much of the
 * dataset it is showing. The complete dataset is the CSV download, which keeps
 * every record.
 */
export function ResearchDataPreview({
  rows,
  previewLimit,
}: {
  rows: ResearchDataRow[];
  previewLimit: number;
}) {
  const [studentCode, setStudentCode] = useState("all");
  const [moduleLabel, setModuleLabel] = useState("all");
  const [expanded, setExpanded] = useState(false);

  const studentCodes = useMemo(
    () => Array.from(new Set(rows.map((row) => row.student_code))).sort(),
    [rows],
  );
  const moduleLabels = useMemo(() => Array.from(new Set(rows.map((row) => row.module_label))), [rows]);

  const filtered = useMemo(
    () =>
      rows
        .filter((row) => studentCode === "all" || row.student_code === studentCode)
        .filter((row) => moduleLabel === "all" || row.module_label === moduleLabel)
        .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))),
    [rows, studentCode, moduleLabel],
  );
  const visible = expanded ? filtered : filtered.slice(0, previewLimit);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-semibold">匿名化研究数据预览</h2>
          <p className="mt-1 text-sm text-slate-600">
            当前显示 {visible.length} / 筛选后 {filtered.length} 条 · 完整研究数据共 {rows.length} 条（下载 CSV 获取全部记录）
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-slate-500">筛选学生</span>
            <select
              aria-label="筛选学生"
              className="rounded-md border border-slate-300 px-3 py-2"
              value={studentCode}
              onChange={(event) => setStudentCode(event.target.value)}
            >
              <option value="all">全部学生</option>
              {studentCodes.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-slate-500">筛选模块</span>
            <select
              aria-label="筛选模块"
              className="rounded-md border border-slate-300 px-3 py-2"
              value={moduleLabel}
              onChange={(event) => setModuleLabel(event.target.value)}
            >
              <option value="all">全部模块</option>
              {moduleLabels.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {filtered.length > previewLimit ? (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic"
            >
              {expanded ? "收起" : "查看全部"}
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-3 py-2">匿名学生编号</th>
              <th className="px-3 py-2">班级</th>
              <th className="px-3 py-2">学习模块</th>
              <th className="px-3 py-2">训练得分</th>
              <th className="px-3 py-2">记录时间</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row, index) => (
              <tr key={`${row.student_code}-${row.module_type}-${row.created_at}-${index}`} className="border-b border-slate-100">
                <td className="px-3 py-3 font-medium text-ink">{row.student_code}</td>
                <td className="px-3 py-3">{row.class_name}</td>
                <td className="px-3 py-3">{row.module_label}</td>
                <td className="px-3 py-3 font-semibold text-clinic">{row.score ?? "待评分"}</td>
                <td className="px-3 py-3 text-slate-600">{formatDateTime(row.created_at)}</td>
              </tr>
            ))}
            {!visible.length ? (
              <tr>
                <td className="px-3 py-6 text-slate-500" colSpan={5}>
                  当前筛选条件下没有记录。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
