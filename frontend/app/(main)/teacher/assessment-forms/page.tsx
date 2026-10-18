"use client";
import {useEffect,useState} from "react";
import {reviewableForms,recordFormReview} from "@/lib/assessmentApi";
type Form={id:number;code:string;title:string;stages:Array<{title:string;clinical_information:string;question:string}>;rubric:unknown;answer_key:unknown;reviewed_by_me:boolean};
export default function ReviewFormsPage(){
  const [items,setItems]=useState<Form[]>([]),[error,setError]=useState(""),[comments,setComments]=useState<Record<number,string>>({});
  async function load(){try{setItems(await reviewableForms())}catch(e){setError(String(e))}}
  useEffect(()=>{void load()},[]);
  async function decide(id:number,decision:"approve"|"reject"){
    try{await recordFormReview(id,decision,comments[id]??"");await load();setError("")}catch(e){setError(String(e))}
  }
  return <div className="space-y-5"><h1 className="text-2xl font-semibold">独立考核病例专家审核</h1>
  <p className="text-sm text-slate-600">请核对医学准确性、题本难度、正确答案、六维评分锚点。每位教师只能独立审核一次，审核人由当前账户自动记录。</p>
  {error?<p role="alert">{error}</p>:null}
  {items.map(f=><section key={f.id} className="space-y-3 rounded border p-4"><h2 className="font-semibold">{f.code}：{f.title}</h2>
  {f.stages.map((s,i)=><div key={i} className="rounded bg-slate-50 p-2"><strong>第{i+1}阶段：{s.title}</strong><p className="whitespace-pre-wrap">{s.clinical_information}</p><p>{s.question}</p></div>)}
  <details><summary>参考答案及评分量表</summary><pre className="whitespace-pre-wrap text-xs">{JSON.stringify({answer_key:f.answer_key,rubric:f.rubric},null,2)}</pre></details>
  {f.reviewed_by_me?<p>本账户已提交审核。</p>:<><textarea className="w-full rounded border p-2" rows={3} placeholder="医学核对、修改意见及真实审核记录" value={comments[f.id]??""} onChange={e=>setComments({...comments,[f.id]:e.target.value})}/>
  <div className="flex gap-3"><button className="rounded bg-teal-700 p-2 text-white" onClick={()=>void decide(f.id,"approve")}>批准草案</button><button className="rounded border p-2" onClick={()=>void decide(f.id,"reject")}>驳回修改</button></div></>}
  </section>)}</div>;
