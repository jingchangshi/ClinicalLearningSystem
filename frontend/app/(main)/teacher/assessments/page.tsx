"use client";

import { useEffect, useState } from "react";
import { getBlindQueue,getBlindDetail,submitBlindReview } from "@/lib/assessmentApi";
import type { BlindDetail, BlindQueueItem } from "@/lib/assessmentApi";

const DIMENSIONS = [
  ["medical_knowledge","医学知识"],["key_information","关键信息"],["differential_diagnosis","鉴别诊断"],
  ["evidence_integration","证据整合"],["clinical_decision","临床决策"],["evidence_based_medicine","循证安全"]
] as const;

export default function BlindReviewPage() {
  const [items,setItems]=useState<BlindQueueItem[]>([]);
  const [detail,setDetail]=useState<BlindDetail|null>(null);
  const [scores,setScores]=useState<Record<string,number>>({});
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function refresh(){try{setItems(await getBlindQueue())}catch(e){setError(String(e))}}
  useEffect(()=>{void refresh()},[]);
  async function open(code:string){try{setDetail(await getBlindDetail(code));setScores({});setError("")}catch(e){setError(String(e))}}
  async function submit(){
    if(!detail)return;
    setLoading(true);
    try{await submitBlindReview(detail.blind_code,scores);setDetail(null);await refresh();setError("")}
    catch(e){setError(String(e))}finally{setLoading(false)}
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-semibold">独立考核盲评</h1>
    <p className="text-sm text-slate-600">盲评页面不显示学生姓名、教学组别或前后测时点。每份答卷提交评分后立即锁定。</p>
    {error?<p role="alert" className="text-red-700">{error}</p>:null}
    {!detail?<div className="space-y-2">{items.map(item=><button type="button" key={item.blind_code} disabled={item.reviewed} className="block w-full rounded border p-3 text-left disabled:opacity-50" onClick={()=>void open(item.blind_code)}>匿名答卷 {item.blind_code.slice(0,10)}… · {item.reviewed?"已评分":"待评分"}</button>)}</div>:
    <section className="space-y-4 rounded border p-5">
      <p className="font-medium">匿名答卷 {detail.blind_code.slice(0,12)}…</p>
      {detail.stages.map((s,i)=><div key={i} className="rounded border p-3"><h2 className="font-semibold">{s.title}</h2><p className="whitespace-pre-wrap text-sm">{s.clinical_information}</p><p className="text-sm font-medium">{s.question}</p><p className="mt-2 whitespace-pre-wrap">{detail.answers.find(x=>x.index===i)?.answer_text??"缺失"}</p></div>)}
      <details className="rounded border p-3"><summary>评分锚点与参考要点（只供盲评者）</summary><pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify({rubric:detail.rubric,answer_key:detail.answer_key},null,2)}</pre></details>
      <div className="grid gap-3 md:grid-cols-2">{DIMENSIONS.map(([key,label])=><label key={key} className="text-sm">{label}（0–100）<input type="number" min={0} max={100} value={scores[key]??""} onChange={e=>setScores(old=>({...old,[key]:Number(e.target.value)}))} className="block w-full rounded border p-2"/></label>)}</div>
      <button type="button" disabled={loading||DIMENSIONS.some(([key])=>scores[key]===undefined||scores[key]<0||scores[key]>100)} onClick={()=>void submit()} className="rounded bg-teal-700 px-4 py-2 text-white disabled:opacity-50">锁定并提交独立评分</button>
    </section>}
  </div>;
