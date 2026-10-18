"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getDemoResearchStudents } from "@/lib/api";
import type { DemoResearchStudent } from "@/lib/api";

import { DemoStudentDetail } from "./DemoStudentDetail";

const GROUP_FILTERS = [
  { key: "all", label: "全部虚拟学生" },
  { key: "CLINPATH", label: "ClinPath辅助教学" },
  { key: "CBL", label: "常规CBL" },
] as const;

export function DemoStudentExplorer({ initial }: { initial: DemoResearchStudent[] }) {
  const [students, setStudents] = useState(initial);
  const [group, setGroup] = useState<(typeof GROUP_FILTERS)[number]["key"]>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(initial[0]?.study_id ?? "");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => {
      getDemoResearchStudents({
        group: group === "all" ? undefined : group,
        q: query.trim() || undefined,
      })
        .then((payload) => {
          if (!active) return;
          setStudents(payload.students);
          if (!payload.students.some((student) => student.study_id === selected)) {
            setSelected(payload.students[0]?.study_id ?? "");
          }
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
    // `selected` is read inside to keep a valid selection, but it must not
    // retrigger the fetch when the user clicks a different student.
  }, [group, query]);

  const gainData = useMemo(
    () =>
      students.map((student) => ({
        study_id: student.study_id,
        gain: student.gain_score ?? 0,
        group: student.group,
      })),
    [students],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-500">分组</span>
          <select
            aria-label="筛选分组"
            className="rounded-md border border-slate-300 px-3 py-2"
            value={group}
            onChange={(event) => setGroup(event.target.value as (typeof GROUP_FILTERS)[number]["key"])}
          >
            {GROUP_FILTERS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-500">研究编号</span>
          <input
            aria-label="搜索研究编号"
            className="rounded-md border border-slate-300 px-3 py-2"
            placeholder="例如 SYN-01"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <p className="pb-2 text-sm text-slate-500">
          {loading ? "正在筛选…" : `当前显示 ${students.length} 名虚拟学生`}
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold">虚拟学生提升分布（T1 − T0）</h3>
        <p className="mt-1 text-xs text-slate-500">
          每根柱是一名虚拟学生的模拟提升；颜色区分组别。排序按研究编号。
        </p>
        <div className="mt-2 h-56 w-full">
          <ResponsiveContainer>
            <BarChart data={gainData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="study_id" tick={{ fontSize: 9 }} interval={0} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(value) => Number(value).toFixed(2)} />
              <Bar dataKey="gain" radius={[2, 2, 0, 0]}>
                {gainData.map((entry) => (
                  <Cell key={entry.study_id} fill={entry.group === "CLINPATH" ? "#0f766e" : "#94a3b8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
        <div className="max-h-[560px] overflow-y-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2">研究编号</th>
                <th className="px-3 py-2">组别</th>
                <th className="px-3 py-2">提升</th>
              </tr>
            </thead>
            <tbody>
              {students.map((student) => (
                <tr
                  key={student.study_id}
                  className={`cursor-pointer border-b border-slate-100 hover:bg-clinic-soft ${
                    student.study_id === selected ? "bg-clinic-soft font-semibold" : ""
                  }`}
                  onClick={() => setSelected(student.study_id)}
                >
                  <td className="px-3 py-2">{student.study_id}</td>
                  <td className="px-3 py-2 text-xs">{student.group_label}</td>
                  <td className="px-3 py-2">{student.gain_score === null ? "—" : student.gain_score.toFixed(1)}</td>
                </tr>
              ))}
              {!students.length ? (
                <tr>
                  <td className="px-3 py-6 text-slate-500" colSpan={3}>
                    当前筛选条件下没有虚拟学生。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="rounded-xl border border-slate-200 p-4">
          <h3 className="font-semibold">虚拟学生详情</h3>
          {selected ? (
            <DemoStudentDetail studyId={selected} />
          ) : (
            <p className="mt-3 text-sm text-slate-500">请选择左侧的虚拟学生。</p>
          )}
        </div>
      </div>
    </div>
  );
}
