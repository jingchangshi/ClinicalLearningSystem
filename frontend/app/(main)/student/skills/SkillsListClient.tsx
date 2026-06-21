"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardCheck, TriangleAlert } from "lucide-react";

import { ClinicalSkill, getMe, listSkills } from "@/lib/api";

export function SkillsListClient() {
  const [skills, setSkills] = useState<ClinicalSkill[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMe(), listSkills()])
      .then(([user, skillRows]) => {
        if (user.role !== "student" || !user.student_id) {
          throw new Error("请使用学生账号登录后访问技能训练。");
        }
        setSkills(skillRows);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "技能项目加载失败"));
  }, []);

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-alert">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">临床技能训练</p>
          <h1 className="text-2xl font-semibold text-ink">OSCE 操作站练习</h1>
        </div>
        <span className="rounded-full bg-teal-50 px-4 py-2 text-sm font-semibold text-clinic">当前登录学生</span>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {skills.map((skill) => (
          <Link
            key={skill.id}
            href={`/student/skills/${skill.id}`}
            className="rounded-lg border border-slate-200 bg-white p-5 hover:border-clinic"
          >
            <div className="flex items-start justify-between gap-3">
              <ClipboardCheck className="h-7 w-7 text-clinic" />
              <span className="rounded-md bg-clinic-soft px-2 py-1 text-xs text-teal-900">
                {skill.difficulty}
              </span>
            </div>
            <h2 className="mt-4 font-semibold">{skill.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{skill.category}</p>
            <p className="mt-3 text-sm leading-6 text-slate-700">{skill.indication}</p>
            <div className="mt-4 flex items-start gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{skill.common_errors[0] ?? "注意按标准流程完成操作。"}</span>
            </div>
          </Link>
        ))}
      </section>
    </div>
  );
}
