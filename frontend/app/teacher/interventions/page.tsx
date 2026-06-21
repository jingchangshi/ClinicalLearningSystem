import Link from "next/link";

import { listTeachingInterventions } from "@/lib/api";

export default async function InterventionsPage() {
  const interventions = await listTeachingInterventions();

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Teaching Interventions</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">教学干预记录</h1>
          <p className="mt-2 text-slate-600">记录教师基于班级短板采取的教学调整，用于教学质量改进闭环。</p>
        </div>
        <Link href="/teacher/dashboard" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
          返回教师驾驶舱
        </Link>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {interventions.length ? (
          interventions.map((item) => (
            <div key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-semibold text-ink">{item.title}</h2>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold text-clinic">{item.intervention_type}</span>
              </div>
              <p className="mt-3 text-sm text-slate-600">目标能力：{item.target_ability}</p>
              <p className="mt-3 text-sm leading-6 text-slate-700">{item.description}</p>
              <p className="mt-3 text-xs text-slate-400">{String(item.created_at).slice(0, 10)}</p>
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-500">暂无教学干预记录，可通过 API 创建干预记录。</p>
        )}
      </section>
    </div>
  );
}
