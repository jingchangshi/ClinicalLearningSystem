"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileText } from "lucide-react";

import { getMe, GuidelineDocument, listGuidelines } from "@/lib/api";

export function GuidelinesListClient() {
  const [guidelines, setGuidelines] = useState<GuidelineDocument[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMe(), listGuidelines()])
      .then(([user, guidelineRows]) => {
        if (user.role !== "student" || !user.student_id) {
          throw new Error("请使用学生账号登录后访问指南学习。");
        }
        setGuidelines(guidelineRows);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "指南加载失败"));
  }, []);

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
        <span className="rounded-full bg-teal-50 px-4 py-2 text-sm font-semibold text-clinic">当前登录学生</span>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {guidelines.map((guideline) => (
          <Link
            key={guideline.id}
            href={`/student/guidelines/${guideline.id}`}
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
