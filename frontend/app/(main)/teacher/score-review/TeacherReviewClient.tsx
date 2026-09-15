"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { createTeacherScoreReview, type ReviewableEvidence } from "@/lib/api";

const labels: Record<string, string> = {
  medical_knowledge: "医学知识",
  key_information: "关键信息提取",
  differential_diagnosis: "鉴别诊断",
  evidence_integration: "证据整合",
  clinical_decision: "临床决策",
  evidence_based_medicine: "循证医学",
};

export function TeacherReviewClient({ evidence }: { evidence: ReviewableEvidence[] }) {
  const router = useRouter();
  const [selected, setSelected] = useState<ReviewableEvidence | null>(null);
  const [dimensions, setDimensions] = useState<Record<string, number>>({});
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function openReview(item: ReviewableEvidence) {
    setSelected(item);
    setDimensions(item.dimensions);
    setComment("");
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      await createTeacherScoreReview({ evidence_event_id: selected.evidence_event_id, confirmed_dimensions: dimensions, comment });
      setSelected(null);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存教师确认失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="font-semibold">待复核病例评分</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[700px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-500"><tr><th className="px-3 py-2">学生</th><th className="px-3 py-2">AI评分</th><th className="px-3 py-2">状态</th><th className="px-3 py-2" /></tr></thead>
          <tbody>{evidence.map((item) => <tr key={item.evidence_event_id} className="border-b border-slate-100"><td className="px-3 py-3">{item.student_name}</td><td className="px-3 py-3">{item.ai_score}</td><td className="px-3 py-3">{item.teacher_confirmed_score === null ? "待教师确认" : "已确认"}</td><td className="px-3 py-3"><button type="button" onClick={() => openReview(item)} className="rounded-md border border-clinic px-3 py-1 text-clinic">复核</button></td></tr>)}</tbody>
        </table>
        {!evidence.length ? <p className="mt-4 text-sm text-slate-500">暂无可复核的病例评分。</p> : null}
      </div>
      {selected ? <form onSubmit={submit} className="mt-6 rounded-xl bg-slate-50 p-4">
        <h3 className="font-semibold">确认 {selected.student_name} 的六维评分</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-2">{Object.entries(labels).map(([key, label]) => <label key={key} className="text-sm text-slate-600">{label}<input aria-label={label} required min="0" max="100" type="number" value={dimensions[key] ?? ""} onChange={(event) => setDimensions((value) => ({ ...value, [key]: Number(event.target.value) }))} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1" /></label>)}</div>
        <label className="mt-3 block text-sm text-slate-600">复核说明<textarea required value={comment} onChange={(event) => setComment(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 p-2" /></label>
        {error ? <p className="mt-2 text-sm text-alert">{error}</p> : null}
        <div className="mt-3 flex gap-2"><button disabled={saving} className="rounded-md bg-clinic px-4 py-2 text-white disabled:opacity-60">{saving ? "保存中…" : "确认并更新画像"}</button><button type="button" onClick={() => setSelected(null)} className="rounded-md border px-4 py-2">取消</button></div>
      </form> : null}
    </section>
  );
}
