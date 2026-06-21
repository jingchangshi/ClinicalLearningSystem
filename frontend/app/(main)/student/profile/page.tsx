import Link from "next/link";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { getMe, getStudentDashboard } from "@/lib/api";

export default async function StudentProfilePage() {
  const user = await getMe();
  const data = await getStudentDashboard(user.student_id ?? 0);

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Student Profile</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">{data.student.name} 学习档案</h1>
          <p className="mt-2 text-slate-600">
            学号 {data.student.student_no} · {data.student.class_name} · 当前阶段 {data.student.current_stage}
          </p>
        </div>
        <Link href="/student/pathway" className="rounded-md bg-clinic px-4 py-2 text-white">
          查看学习路径
        </Link>
      </section>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">账户信息</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <ProfileRow label="用户名" value={user.username} />
            <ProfileRow label="角色" value={user.role} />
            <ProfileRow label="学生ID" value={String(user.student_id ?? "-")} />
          </dl>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">能力画像</h2>
          <CompetencyRadar data={data.competency.expanded_chart_data ?? data.competency.chart_data} />
        </section>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">学习进度</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <ProgressCard title="已完成病例" value={String(data.progress.completed_cases)} />
          <ProgressCard title="进行中病例" value={String(data.progress.in_progress_cases)} />
          <ProgressCard title="平均得分" value={String(data.progress.average_score ?? "待评分")} />
        </div>
      </section>
    </div>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium text-ink">{value}</dd>
    </div>
  );
}

function ProgressCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}
