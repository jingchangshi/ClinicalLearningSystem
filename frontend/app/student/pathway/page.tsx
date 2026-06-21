import Link from "next/link";

import { AdaptiveRecommendationEngine } from "@/components/AdaptiveRecommendationEngine";
import { CompetencyRadar } from "@/components/CompetencyRadar";
import { LearningEvidenceCards } from "@/components/LearningEvidenceCards";
import { LearningGapDiagnosisCard } from "@/components/LearningGapDiagnosisCard";
import { RecommendedTaskCard } from "@/components/RecommendedTaskCard";
import { getMe, getPathway } from "@/lib/api";

export default async function PathwayPage() {
  const me = await getMe();
  if (me.role !== "student" || !me.student_id) {
    throw new Error("请使用学生账号登录后访问学习路径。");
  }
  const studentId = me.student_id;
  const pathway = await getPathway(studentId);
  const weakAbilities = pathway.weak_abilities.length
    ? pathway.weak_abilities
    : [...pathway.competency.expanded_chart_data]
        .sort((a, b) => a.score - b.score)
        .slice(0, 2)
        .map((item) => ({ key: dimensionKey(item.dimension), label: item.dimension, score: item.score }));

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Adaptive Learning Pathway</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">AI个性化学习路径</h1>
        <p className="mt-2 text-slate-600">基于能力画像、训练表现与模块完成情况生成下一阶段学习任务。</p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_0.9fr_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">当前学生能力画像</h2>
          <p className="mt-2 text-sm text-slate-500">{pathway.student.name} · {pathway.student.class_name}</p>
          <CompetencyRadar data={pathway.competency.expanded_chart_data} />
          <div className="mt-3 flex flex-wrap gap-2">
            {weakAbilities.map((item) => (
              <span key={item.key} className="rounded-full bg-red-50 px-3 py-1 text-sm font-semibold text-alert">
                {item.label}不足 · {item.score}
              </span>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">当前阶段与下一阶段目标</h2>
          <div className="mt-4 rounded-2xl bg-clinic-soft p-5">
            <p className="text-sm font-semibold text-clinic">当前阶段</p>
            <p className="mt-2 text-xl font-semibold text-ink">{stageTitle(pathway.current_stage, pathway.pathway_stages)}</p>
          </div>
          <p className="mt-4 text-sm leading-7 text-slate-600">{pathway.next_stage_goal}</p>
          <Link
            href={`/student/case/${pathway.recommended_case.id}`}
            className="mt-5 inline-flex rounded-md bg-clinic px-4 py-2 text-white"
          >
            开始推荐病例
          </Link>
        </section>

        <LearningGapDiagnosisCard weakAbilities={weakAbilities} />
      </div>

      <LearningEvidenceCards evidence={pathway.learning_evidence} />

      <AdaptiveRecommendationEngine />

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">下一阶段推荐任务</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {pathway.recommended_tasks.map((task) => (
            <RecommendedTaskCard
              key={`${task.type}-${task.id}`}
              href={taskHref(task.type, task.id, studentId)}
              task={task}
            />
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">路径阶段概览</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          {pathway.pathway_stages.map((stage, index) => (
            <div
              key={stage.key}
              className={`rounded-2xl border p-4 ${
                stage.key === pathway.current_stage ? "border-clinic bg-clinic-soft" : "border-slate-200 bg-slate-50"
              }`}
            >
              <div className="text-sm font-medium text-clinic">阶段 {index + 1}</div>
              <div className="mt-2 font-semibold">{stage.title}</div>
              <p className="mt-2 text-sm text-slate-600">{stage.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">推荐知识单元</h2>
          <Link
            href="/student/knowledge"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:border-clinic"
          >
            查看全部知识
          </Link>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {pathway.knowledge_suggestions.map((item) => (
            <Link
              key={item.unit.id}
              href={`/student/knowledge/${item.unit.id}`}
              className="rounded-md bg-slate-50 p-4 hover:bg-clinic-soft"
            >
              <div className="font-medium">{item.unit.title}</div>
              <div className="mt-1 text-sm text-slate-500">
                {item.unit.category} · {item.unit.level}
              </div>
              <p className="mt-3 text-sm text-slate-700">{item.reason}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
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

function taskHref(type: string, id: number, studentId: number) {
  const paths: Record<string, string> = {
    knowledge_unit: `/student/knowledge/${id}`,
    clinical_skill: `/student/skills/${id}`,
    case: `/student/case/${id}`,
    guideline: `/student/guidelines/${id}`,
    sp_case: `/student/sp/${id}`,
  };
  void studentId;
  return paths[type] ?? "/student/dashboard";
}

function dimensionKey(label: string) {
  const map: Record<string, string> = {
    医学知识: "medical_knowledge",
    技能操作: "skill_operation",
    关键信息提取: "key_information",
    鉴别诊断: "differential_diagnosis",
    证据整合: "evidence_integration",
    循证医学: "evidence_based_medicine",
    医患沟通: "communication",
    人文关怀: "humanistic_care",
  };
  return map[label] ?? label;
}
