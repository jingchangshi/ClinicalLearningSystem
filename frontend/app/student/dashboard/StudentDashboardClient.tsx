"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, BrainCircuit, ClipboardCheck, FileText, MessagesSquare, Route, Target, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { LearningEvidenceCards } from "@/components/LearningEvidenceCards";
import { LearningGapDiagnosisCard } from "@/components/LearningGapDiagnosisCard";
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

  const competencyAverage = Math.round(
    dashboard.competency.expanded_chart_data.reduce((sum, item) => sum + item.score, 0) /
      dashboard.competency.expanded_chart_data.length,
  );
  const weakAbilities = [...dashboard.competency.expanded_chart_data]
    .sort((a, b) => a.score - b.score)
    .slice(0, 2)
    .map((item) => ({ key: dimensionKey(item.dimension), label: item.dimension, score: item.score }));
  const completedTraining = dashboard.learning_evidence.reduce((sum, item) => sum + item.completed, 0);
  const nextTask = dashboard.recommendation_details[0]?.case.title ?? dashboard.recommended_cases[0]?.title ?? "完成推荐病例训练";
  const recommendationReason = dashboard.recommendation_details[0]?.recommendation_reason ?? dashboard.recent_advice;

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{dashboard.student.class_name}</p>
          <h1 className="text-3xl font-semibold text-ink">ClinPath 学生临床能力成长中心</h1>
          <p className="mt-2 text-slate-600">基于多模块训练数据形成能力画像与个性化学习路径。</p>
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

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard title="综合胜任力指数" value={String(competencyAverage)} note="八维能力画像均值" icon={TrendingUp} />
        <MetricCard title="已完成训练" value={String(completedTraining || dashboard.progress.completed_cases)} note={completedTraining ? "五模块训练总计" : "病例训练"} icon={ClipboardCheck} />
        <MetricCard title="当前主要短板" value={weakAbilities[0]?.label ?? "暂无"} note={`当前分数 ${weakAbilities[0]?.score ?? "-"}`} icon={Target} />
        <MetricCard title="AI推荐下一任务" value={nextTask} note="基于最近训练表现生成" icon={Route} />
      </div>

      <LearningEvidenceCards evidence={dashboard.learning_evidence} />

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">五模块训练入口矩阵</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {trainingModules(studentId).map((module) => (
            <button
              key={module.title}
              onClick={() => router.push(module.href)}
              className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left hover:border-clinic hover:bg-cyan-50"
            >
              <module.icon className="h-6 w-6 text-clinic" />
              <h3 className="mt-3 font-semibold">{module.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{module.goal}</p>
              <p className="mt-3 rounded-full bg-white px-3 py-1 text-xs font-semibold text-clinic">{module.ability}</p>
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[0.85fr_1.25fr_0.9fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">学生信息</p>
          <h2 className="mt-2 text-xl font-semibold">{dashboard.student.name}</h2>
          <p className="mt-1 text-sm text-slate-600">{dashboard.student.current_stage}</p>
          <div className="mt-5 rounded-2xl bg-teal-50 p-5">
            <p className="text-sm text-slate-500">综合胜任力指数</p>
            <p className="mt-2 text-5xl font-semibold text-clinic">{competencyAverage}</p>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold">八维能力画像</h2>
          <CompetencyRadar data={dashboard.competency.expanded_chart_data} />
        </section>

        <LearningGapDiagnosisCard weakAbilities={weakAbilities} />
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">AI Adaptive Learning Recommendation</h2>
          <button
            onClick={() => router.push(`/student/pathway?studentId=${studentId}`)}
            className="text-sm text-clinic hover:underline"
          >
            查看学习路径
          </button>
        </div>
        <p className="mt-3 rounded-xl bg-clinic-soft p-3 text-sm text-teal-900">{recommendationReason}</p>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {dashboard.recommended_cases.map((item, index) => (
            <button
              key={item.id}
              onClick={() => enterCase(item.id)}
              className="rounded-2xl border border-slate-200 bg-slate-50 p-5 text-left hover:border-clinic hover:bg-white disabled:opacity-60"
              disabled={busyCaseId === item.id}
            >
              <div className="font-semibold">{item.title}</div>
              <div className="mt-2 text-sm text-slate-500">
                {item.disease_category} · {item.difficulty}
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-700">
                推荐原因：{dashboard.recommendation_details[index]?.recommendation_reason ?? recommendationReason}
              </p>
              <p className="mt-2 text-sm text-slate-600">目标能力：临床推理 / 鉴别诊断</p>
              <span className="mt-4 inline-flex rounded-md bg-clinic px-3 py-2 text-sm font-medium text-white">
                开始训练
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function MetricCard({ title, value, note, icon: Icon }: { title: string; value: string; note: string; icon: LucideIcon }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="mt-3 line-clamp-2 text-2xl font-semibold text-ink">{value}</p>
        </div>
        <span className="rounded-xl bg-teal-50 p-2 text-clinic">
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3 text-sm text-slate-600">{note}</p>
    </div>
  );
}

function trainingModules(studentId: number) {
  return [
    {
      title: "基础知识学习",
      goal: "先补齐关键概念，再进入病例推理训练。",
      ability: "医学知识",
      href: `/student/knowledge?studentId=${studentId}`,
      icon: BookOpen,
    },
    {
      title: "临床技能训练",
      goal: "练习查体和操作流程，获得 OSCE 反馈。",
      ability: "技能操作 / 临床决策",
      href: `/student/skills?studentId=${studentId}`,
      icon: ClipboardCheck,
    },
    {
      title: "临床思维训练",
      goal: "通过病例分步作答训练鉴别诊断与证据整合。",
      ability: "临床推理 / 鉴别诊断",
      href: `/student/pathway?studentId=${studentId}`,
      icon: BrainCircuit,
    },
    {
      title: "循证指南学习",
      goal: "用 PICO 结构解读推荐等级和临床适用性。",
      ability: "循证决策",
      href: `/student/guidelines?studentId=${studentId}`,
      icon: FileText,
    },
    {
      title: "SP模拟考核",
      goal: "与标准化病人对话，训练问诊和沟通。",
      ability: "信息采集 / 医患沟通",
      href: `/student/sp?studentId=${studentId}`,
      icon: MessagesSquare,
    },
  ];
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
