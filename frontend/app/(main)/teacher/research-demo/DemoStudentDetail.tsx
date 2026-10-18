"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ApiError, getDemoResearchStudent } from "@/lib/api";
import type { DemoResearchStudentDetail } from "@/lib/api";

/**
 * The per-student view of the synthetic study.
 *
 * The number that matters is the independent T0/T1 pair, because that is the
 * study's primary outcome. The training score and the five-stage reasoning
 * dialogue sit below it and are labelled as *process* data — a demo must not
 * let an internal formative score look like the measured effect.
 */
export function DemoStudentDetail({ studyId }: { studyId: string }) {
  const [detail, setDetail] = useState<DemoResearchStudentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setDetail(null);
    setError(null);
    getDemoResearchStudent(studyId)
      .then((payload) => {
        if (active) setDetail(payload);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof ApiError ? `无法读取该虚拟学生（HTTP ${reason.status}）` : "无法读取该虚拟学生");
      });
    return () => {
      active = false;
    };
  }, [studyId]);

  const dimensionData = useMemo(() => {
    if (!detail) return [];
    const byTimepoint = Object.fromEntries(
      detail.assessments.map((assessment) => [assessment.timepoint, assessment]),
    );
    const pre = byTimepoint.T0;
    const post = byTimepoint.T1;
    if (!pre || !post) return [];
    return pre.dimensions.map((dimension, index) => ({
      dimension: dimension.label,
      T0: dimension.score,
      T1: post.dimensions[index]?.score ?? 0,
      weight: `${dimension.weight * 100}%`,
    }));
  }, [detail]);

  if (error) {
    return <p className="mt-3 text-sm text-rose-600">{error}</p>;
  }
  if (!detail) {
    return <p className="mt-3 text-sm text-slate-500">正在读取虚拟学生 {studyId} …</p>;
  }

  return (
    <div className="mt-4 space-y-4" data-testid={`demo-student-${detail.study_id}`}>
      <div className="grid gap-3 md:grid-cols-4">
        <MiniStat label="研究编号" value={detail.study_id} note={detail.group_label} />
        <MiniStat label="T0 独立评分" value={detail.pre_score?.toFixed(1) ?? "—"} note="模拟评分者独立病例" />
        <MiniStat label="T1 独立评分" value={detail.post_score?.toFixed(1) ?? "—"} note="模拟评分者独立病例" />
        <MiniStat
          label="提升"
          value={detail.gain_score === null ? "—" : `${detail.gain_score > 0 ? "+" : ""}${detail.gain_score.toFixed(2)}`}
          note="T1 − T0，模拟数据"
        />
      </div>

      <section className="rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold">六维度前后测（模拟评分）</h3>
        <p className="mt-1 text-xs text-slate-500">同一名学生、同一份模拟答卷的 T0 与 T1 分维度得分。</p>
        <div className="mt-2 h-64 w-full">
          <ResponsiveContainer>
            <BarChart data={dimensionData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="dimension" tick={{ fontSize: 11 }} interval={0} angle={-12} textAnchor="end" height={54} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(value) => Number(value).toFixed(1)} />
              <Legend />
              <Bar dataKey="T0" fill="#94a3b8" radius={[3, 3, 0, 0]} />
              <Bar dataKey="T1" fill="#0f766e" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold">独立前后测明细</h3>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2">时点</th>
                <th className="px-3 py-2">考核病例</th>
                <th className="px-3 py-2">评分者A</th>
                <th className="px-3 py-2">评分者B</th>
                <th className="px-3 py-2">主结局</th>
                <th className="px-3 py-2">评分来源</th>
              </tr>
            </thead>
            <tbody>
              {detail.assessments.map((assessment) => (
                <tr key={assessment.timepoint} className="border-b border-slate-100">
                  <td className="px-3 py-2 font-medium">{assessment.timepoint}</td>
                  <td className="px-3 py-2">{assessment.assessment_case_id}</td>
                  <td className="px-3 py-2">
                    {assessment.rater_A.id} · {assessment.rater_A.total.toFixed(1)}
                  </td>
                  <td className="px-3 py-2">
                    {assessment.rater_B.id} · {assessment.rater_B.total.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 font-semibold text-clinic">{assessment.independent_total.toFixed(2)}</td>
                  <td className="px-3 py-2 text-slate-600">
                    {assessment.rater_origin === "SIMULATED_NOT_HUMAN" ? "计算机模拟评分者（非真实教师）" : assessment.rater_origin}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold">训练过程（模拟，不作为主结局）</h3>
        <p className="mt-1 text-xs text-slate-500">
          训练分是平台内部形成性评分，与独立前后测不同源，不能替代研究主结局。
        </p>
        {detail.sessions.length ? (
          <>
            <div className="mt-3 h-44 w-full">
              <ResponsiveContainer>
                <LineChart
                  data={detail.sessions.map((session) => ({
                    name: `第${session.week}周·${session.case_code}`,
                    score: session.training_score_internal,
                  }))}
                  margin={{ top: 8, right: 12, bottom: 8, left: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#b45309" strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 space-y-3">
              {detail.sessions.map((session, sessionIndex) => (
                // The first case is open: a teacher reviewing the demo should
                // see the five-stage dialogue without hunting for a toggle.
                <details
                  key={session.session_id}
                  open={sessionIndex === 0 && session.reasoning_steps.length > 0}
                  className="rounded-lg bg-slate-50 p-3"
                >
                  <summary className="cursor-pointer text-sm font-medium">
                    {session.session_id} · 第{session.week}周 · {session.case_code} · {session.teaching_mode}
                  </summary>
                  <div className="mt-2 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                    <span>训练分（内部）：{session.training_score_internal?.toFixed(1) ?? "—"}</span>
                    <span>评价模式：{session.evaluation_mode}</span>
                    <span>模型：{session.model_id}</span>
                    <span>模拟教师干预：{session.simulated_teacher_intervention}</span>
                    <span>时间：{session.date_relative}</span>
                  </div>
                  {session.reasoning_steps.length ? (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs font-semibold text-amber-700">
                        以下文字为模板化模拟作答，不是真实学生文字。
                      </p>
                      {session.reasoning_steps.map((step) => (
                        <div key={step.step_id} className="rounded-md border border-slate-200 bg-white p-3">
                          <div className="text-xs font-semibold text-slate-500">
                            {step.step_id} · {step.step_label}
                          </div>
                          <div className="mt-1 text-sm">
                            <span className="font-medium text-slate-500">模拟学生初答：</span>
                            {step.initial_answer}
                          </div>
                          <div className="mt-1 text-sm text-amber-800">
                            <span className="font-medium">模拟AI追问：</span>
                            {step.tutor_question}
                          </div>
                          <div className="mt-1 text-sm text-clinic">
                            <span className="font-medium">模拟修订作答：</span>
                            {step.revised_answer}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-slate-500">常规CBL组没有平台内五阶段作答记录（模拟设计如此）。</p>
                  )}
                </details>
              ))}
            </div>
          </>
        ) : (
          <p className="mt-2 text-sm text-slate-500">该虚拟学生没有训练记录。</p>
        )}
      </section>

      <ul className="space-y-1 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
        {detail.notes.map((note) => (
          <li key={note}>· {note}</li>
        ))}
      </ul>
    </div>
  );
}

function MiniStat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-ink">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{note}</p>
    </div>
  );
}
