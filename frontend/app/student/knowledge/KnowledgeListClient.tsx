"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { BookOpen, CheckCircle2 } from "lucide-react";

import {
  getKnowledgeProgress,
  KnowledgeProgress,
  KnowledgeUnit,
  listKnowledge,
  listStudents,
  Student,
} from "@/lib/api";

export function KnowledgeListClient() {
  const searchParams = useSearchParams();
  const [students, setStudents] = useState<Student[]>([]);
  const [studentId, setStudentId] = useState(Number(searchParams.get("studentId") ?? 1));
  const [units, setUnits] = useState<KnowledgeUnit[]>([]);
  const [progress, setProgress] = useState<KnowledgeProgress[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listStudents(), listKnowledge()])
      .then(([studentRows, unitRows]) => {
        setStudents(studentRows);
        setUnits(unitRows);
        if (!studentRows.some((student) => student.id === studentId) && studentRows[0]) {
          setStudentId(studentRows[0].id);
        }
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "知识单元加载失败"));
  }, [studentId]);

  useEffect(() => {
    getKnowledgeProgress(studentId)
      .then(setProgress)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "学习进度加载失败"));
  }, [studentId]);

  const progressByUnit = useMemo(
    () => new Map(progress.map((item) => [item.knowledge_unit_id, item])),
    [progress],
  );

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-alert">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">基础知识学习</p>
          <h1 className="text-2xl font-semibold text-ink">风湿免疫核心知识单元</h1>
        </div>
        <label className="text-sm">
          <span className="mr-2 text-slate-500">选择学生</span>
          <select
            value={studentId}
            onChange={(event) => setStudentId(Number(event.target.value))}
            className="rounded-md border border-slate-300 bg-white px-3 py-2"
          >
            {students.map((student) => (
              <option key={student.id} value={student.id}>
                {student.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {units.map((unit) => {
          const row = progressByUnit.get(unit.id);
          return (
            <Link
              key={unit.id}
              href={`/student/knowledge/${unit.id}?studentId=${studentId}`}
              className="rounded-lg border border-slate-200 bg-white p-5 hover:border-clinic"
            >
              <div className="flex items-start justify-between gap-3">
                <BookOpen className="h-6 w-6 text-clinic" />
                {row?.status === "completed" ? <CheckCircle2 className="h-5 w-5 text-clinic" /> : null}
              </div>
              <h2 className="mt-4 font-semibold">{unit.title}</h2>
              <p className="mt-1 text-sm text-slate-500">
                {unit.category} · {unit.level}
              </p>
              <div className="mt-3 text-sm text-slate-600">
                掌握度：{row ? row.mastery_score : 0} · 状态：{statusLabel(row?.status)}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {unit.key_points.slice(0, 3).map((point) => (
                  <span key={point} className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
                    {point}
                  </span>
                ))}
              </div>
            </Link>
          );
        })}
      </section>
    </div>
  );
}

function statusLabel(status?: string) {
  if (status === "completed") return "已完成";
  if (status === "in_progress") return "学习中";
  return "未开始";
}
