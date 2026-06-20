"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FileText } from "lucide-react";

import { GuidelineDocument, listGuidelines, listStudents, Student } from "@/lib/api";

export function GuidelinesListClient() {
  const searchParams = useSearchParams();
  const [students, setStudents] = useState<Student[]>([]);
  const [studentId, setStudentId] = useState(Number(searchParams.get("studentId") ?? 1));
  const [guidelines, setGuidelines] = useState<GuidelineDocument[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listStudents(), listGuidelines()])
      .then(([studentRows, guidelineRows]) => {
        setStudents(studentRows);
        setGuidelines(guidelineRows);
        if (!studentRows.some((student) => student.id === studentId) && studentRows[0]) {
          setStudentId(studentRows[0].id);
        }
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "指南加载失败"));
  }, [studentId]);

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-alert">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">循证指南学习</p>
          <h1 className="text-2xl font-semibold text-ink">指南推荐与 PICO 训练</h1>
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
        {guidelines.map((guideline) => (
          <Link
            key={guideline.id}
            href={`/student/guidelines/${guideline.id}?studentId=${studentId}`}
            className="rounded-lg border border-slate-200 bg-white p-5 hover:border-clinic"
          >
            <div className="flex items-start justify-between gap-3">
              <FileText className="h-7 w-7 text-clinic" />
              <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
                {guideline.organization} · {guideline.year}
              </span>
            </div>
            <h2 className="mt-4 font-semibold">{guideline.title}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {guideline.disease_category} · {guideline.source_type}
            </p>
            <p className="mt-3 text-sm leading-6 text-slate-700">{guideline.summary}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
