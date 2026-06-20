"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { StatCard } from "@/components/StatCard";
import { getStudentDashboard, listStudents, startSession, Student } from "@/lib/api";

type Dashboard = Awaited<ReturnType<typeof getStudentDashboard>>;

export function StudentDashboardClient() {
  const router = useRouter();
  const [students, setStudents] = useState<Student[]>([]);
  const [studentId, setStudentId] = useState(1);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [busyCaseId, setBusyCaseId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listStudents()
      .then((items) => {
        setStudents(items);
        if (items[0]) setStudentId(items[0].id);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "学生列表加载失败"));
  }, []);

  useEffect(() => {
    setError(null);
    getStudentDashboard(studentId)
      .then(setDashboard)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "学生首页加载失败"));
  }, [studentId]);

  async function enterCase(caseId: number) {
    setBusyCaseId(caseId);
    try {
      const session = await startSession(studentId, caseId);
      router.push(`/student/case/${caseId}?sessionId=${session.session_id}&studentId=${studentId}`);
    } finally {
      setBusyCaseId(null);
    }
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-alert">
        学生数据加载失败：{error}
      </div>
    );
  }

  if (!dashboard) {
    return <div className="rounded-lg border border-slate-200 bg-white p-5">正在加载学生数据...</div>;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{dashboard.student.class_name}</p>
          <h1 className="text-2xl font-semibold text-ink">{dashboard.student.name}的临床推理训练</h1>
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

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="已完成病例" value={dashboard.progress.completed_cases} />
        <StatCard label="进行中病例" value={dashboard.progress.in_progress_cases} />
        <StatCard label="平均得分" value={dashboard.progress.average_score || "待评分"} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">当前能力画像</h2>
          <CompetencyRadar data={dashboard.competency.chart_data} />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">推荐病例</h2>
            <button
              onClick={() => router.push(`/student/pathway?studentId=${studentId}`)}
              className="text-sm text-clinic hover:underline"
            >
              查看学习路径
            </button>
          </div>
          <p className="mt-3 rounded-md bg-clinic-soft p-3 text-sm text-teal-900">{dashboard.recent_advice}</p>
          <div className="mt-4 divide-y divide-slate-100">
            {dashboard.recommended_cases.map((item) => (
              <button
                key={item.id}
                onClick={() => enterCase(item.id)}
                className="flex w-full items-center justify-between gap-4 py-4 text-left hover:bg-slate-50 disabled:opacity-60"
                disabled={busyCaseId === item.id}
              >
                <div>
                  <div className="font-medium">{item.title}</div>
                  <div className="mt-1 text-sm text-slate-500">
                    {item.disease_category} · {item.difficulty} · {item.chief_complaint}
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" />
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
