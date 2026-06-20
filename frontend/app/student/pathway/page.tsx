import Link from "next/link";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { getPathway } from "@/lib/api";

export default async function PathwayPage({
  searchParams,
}: {
  searchParams: Promise<{ studentId?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const studentId = Number(resolvedSearchParams.studentId ?? 1);
  const pathway = await getPathway(studentId);

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm text-slate-500">{pathway.student.name} · 自适应学习路径</p>
        <h1 className="text-2xl font-semibold">当前阶段：{stageTitle(pathway.current_stage, pathway.pathway_stages)}</h1>
        <p className="mt-2 text-slate-600">{pathway.next_stage_goal}</p>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="grid gap-3 md:grid-cols-4">
          {pathway.pathway_stages.map((stage, index) => (
            <div
              key={stage.key}
              className={`rounded-lg border p-4 ${
                stage.key === pathway.current_stage ? "border-clinic bg-clinic-soft" : "border-slate-200 bg-white"
              }`}
            >
              <div className="text-sm font-medium text-clinic">阶段 {index + 1}</div>
              <div className="mt-2 font-semibold">{stage.title}</div>
              <p className="mt-2 text-sm text-slate-600">{stage.description}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">当前能力画像</h2>
          <CompetencyRadar data={pathway.competency.chart_data} />
          <div className="mt-3 flex flex-wrap gap-2">
            {pathway.weak_abilities.map((item) => (
              <span key={item.key} className="rounded-md bg-red-50 px-2 py-1 text-sm text-alert">
                {item.label}不足 · {item.score}
              </span>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">当前推荐病例</h2>
          <div className="mt-4 rounded-md bg-slate-50 p-4">
            <div className="font-medium">{pathway.recommended_case.title}</div>
            <div className="mt-1 text-sm text-slate-500">
              {pathway.recommended_case.disease_category} · {pathway.recommended_case.difficulty}
            </div>
            <p className="mt-3 text-sm text-slate-700">{pathway.recommendation_reason}</p>
            <Link
              href={`/student/case/${pathway.recommended_case.id}?studentId=${studentId}`}
              className="mt-4 inline-flex rounded-md bg-clinic px-4 py-2 text-white"
            >
              开始推荐病例
            </Link>
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">已完成病例</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {pathway.completed_cases.length ? (
            pathway.completed_cases.map((item) => (
              <div key={item.session_id} className="rounded-md bg-slate-50 p-3">
                <div className="font-medium">{item.case.title}</div>
                <div className="mt-1 text-sm text-slate-500">得分：{item.score ?? "待评分"}</div>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">尚未完成病例训练。</p>
          )}
        </div>
      </section>
    </div>
  );
}

function stageTitle(key: string, stages: { key: string; title: string }[]) {
  return stages.find((stage) => stage.key === key)?.title ?? key;
}
