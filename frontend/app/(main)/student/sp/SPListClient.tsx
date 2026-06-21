"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessagesSquare } from "lucide-react";

import { getMe, listSPCases, SPCase } from "@/lib/api";

export function SPListClient() {
  const [cases, setCases] = useState<SPCase[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMe(), listSPCases()])
      .then(([user, caseRows]) => {
        if (user.role !== "student" || !user.student_id) {
          throw new Error("请使用学生账号登录后访问SP训练。");
        }
        setCases(caseRows);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "SP 病例加载失败"));
  }, []);

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
        <span className="rounded-full bg-teal-50 px-4 py-2 text-sm font-semibold text-clinic">当前登录学生</span>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {cases.map((spCase) => (
          <Link
            key={spCase.id}
            href={`/student/sp/${spCase.id}`}
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
