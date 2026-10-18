"use client";

import { useEffect, useState } from "react";
import { getAssessments, getAssessment, answerAssessmentStage, submitAssessment } from "@/lib/assessmentApi";
import type { AssessmentStage, AssessmentMine } from "@/lib/assessmentApi";

export default function StudentAssessmentsPage() {
  const [items,setItems] = useState<AssessmentMine[]>([]);
  const [active,setActive] = useState<AssessmentStage | null>(null);
  const [text,setText] = useState("");
  const [error,setError] = useState("");
  const [loading,setLoading] = useState(false);
  async function refresh() { try { setItems(await getAssessments()); } catch(e) {setError(String(e));} }
  useEffect(()=>{void refresh()},[]);
  async function open(id:number) {
    try {setError("");setActive(await getAssessment(id));setText("");}
    catch(e){setError(String(e));}
  }
  async function save() {
    if(!active || !text.trim())return;
    setLoading(true);setError("");
    try {
      await answerAssessmentStage(active.sitting_id,text);
      setText("");setActive(await getAssessment(active.sitting_id));
    } catch(e){setError(String(e));} finally {setLoading(false);}
  }
  async function submit() {
    if(!active)return;
    setLoading(true);
    try {await submitAssessment(active.sitting_id);setActive(null);await refresh();}
    catch(e){setError(String(e))}finally{setLoading(false);}
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-semibold">独立临床推理考核</h1>
    <p className="text-sm text-slate-600">与病例训练分离：考试没有AI追问、自动评分反馈或学习推荐。按顺序提交的阶段答案不能修改。</p>
    {error?<p role="alert" className="text-red-700">{error}</p>:null}
    {!active?<div className="space-y-2">{items.length?items.map(i=><button type="button" key={i.id} onClick={()=>void open(i.id)} disabled={i.status==="submitted"} className="block w-full rounded border p-3 text-left disabled:opacity-50">考核编号 {i.id} · {i.status==="submitted"?"已提交":"开始考核"}</button>):<p>目前没有开放的考核。</p>}</div>:
    <section className="space-y-4 rounded border p-5" data-testid="assessment-stage">
      <p className="font-semibold">已完成 {active.completed}/5 阶段</p>
      {active.stage?<><h2 className="text-lg">{active.stage.title}</h2>
        <p className="whitespace-pre-wrap">{active.stage.clinical_information}</p>
        <p className="font-medium">{active.stage.question}</p>
        <textarea value={text} onChange={e=>setText(e.target.value)} rows={7} aria-label="当前阶段作答" className="w-full rounded border p-2" />
        <button type="button" disabled={loading||!text.trim()} onClick={()=>void save()} className="rounded bg-teal-700 px-4 py-2 text-white disabled:opacity-50">提交此阶段并查看下一阶段</button></>:
      <button type="button" disabled={loading} onClick={()=>void submit()} className="rounded bg-teal-700 px-4 py-2 text-white">提交整份答卷</button>}
    </section>}
  </div>;
