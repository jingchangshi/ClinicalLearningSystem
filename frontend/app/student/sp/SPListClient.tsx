"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { MessagesSquare } from "lucide-react";

import { listSPCases, listStudents, SPCase, Student } from "@/lib/api";

export function SPListClient() {
  const searchParams = useSearchParams();
  const [students, setStudents] = useState<Student[]>([]);
  const [studentId, setStudentId] = useState(Number(searchParams.get("studentId") ?? 1));
  const [cases, setCases] = useState<SPCase[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listStudents(), listSPCases()])
      .then(([studentRows, caseRows]) => {
        setStudents(studentRows);
        setCases(caseRows);
        if (!studentRows.some((student) => student.id === studentId) && studentRows[0]) {
          setStudentId(studentRows[0].id);
        }
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "SP 病例加载失败"));
  }, [studentId]);

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-alert">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">标准化病人 SP</p>
          <h1 className="text-2xl font-semibold text-ink">问诊与沟通考核</h1>
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

      <section className="grid gap-4 md:grid-cols-2">
        {cases.map((spCase) => (
          <Link
            key={spCase.id}
            href={`/student/sp/${spCase.id}?studentId=${studentId}`}
            className="rounded-lg border border-slate-200 bg-white p-5 hover:border-clinic"
          >
            <div className="flex items-start justify-between gap-3">
              <MessagesSquare className="h-7 w-7 text-clinic" />
              <span className="rounded-md bg-clinic-soft px-2 py-1 text-xs text-teal-900">
                {spCase.difficulty}
              </span>
            </div>
            <h2 className="mt-4 font-semibold">{spCase.title}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {spCase.disease_category} · {spCase.emotional_style}
            </p>
            <p className="mt-3 rounded-md bg-slate-50 p-3 text-sm leading-6 text-slate-700">
              {spCase.opening_statement}
            </p>
          </Link>
        ))}
      </section>
    </div>
  );
}
