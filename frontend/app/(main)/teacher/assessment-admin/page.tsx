"use client";
import {useEffect,useState} from "react";
import {createAssessmentForm,approveAssessmentForm,allAssessmentForms,assignAssessment,researchAssessmentExport} from "@/lib/assessmentApi";
type Item={id:number;code:string;title:string;review_status:string};
const example={
  code:"CASE-A02-V1",title:"干燥症状待查（真实教师审核前不得批准）",
  stages:Array.from({length:5},(_,i)=>({title:"第"+(i+1)+"阶段",clinical_information:"请录入经过审核的阶段信息",question:"请录入经过审核的推理问题"})),
  answer_key:{},rubric:{}
};
export default function AssessmentAdminPage(){
  const [forms,setForms]=useState<Item[]>([]),[json,setJson]=useState(JSON.stringify(example,null,2)),[error,setError]=useState(""),[message,setMessage]=useState("");
  const [assignment,setAssignment]=useState({student_id:0,form_id:0,cohort_code:"B1",study_group:"CLINPATH",timepoint:"T0",rater_a_id:0,rater_b_id:0,window_start:"",window_end:""});
  async function load(){try{setForms(await allAssessmentForms())}catch(e){setError(String(e))}}
  useEffect(()=>{void load()},[]);
  async function create(){try{const payload=JSON.parse(json);await createAssessmentForm(payload);setMessage("已建立待审草案");await load();setError("")}catch(e){setError(String(e))}}
  async function approve(id:number){try{await approveAssessmentForm(id);setMessage("已有两名教师独立审核，管理员已允许考核");await load();setError("")}catch(e){setError(String(e))}}
  async function assign(){try{await assignAssessment({...assignment,window_start:new Date(assignment.window_start).toISOString(),window_end:new Date(assignment.window_end).toISOString()});setMessage("考试已分配");setError("")}catch(e){setError(String(e))}}
  async function exportData(){try{const content=await researchAssessmentExport();const blob=new Blob([JSON.stringify(content,null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download="real_assessments_private.json";link.click();URL.revokeObjectURL(url)}catch(e){setError(String(e))}}
  return <div className="space-y-6"><h1 className="text-2xl font-semibold">独立考核管理（管理员）</h1>
    <p className="text-sm text-slate-600">创建题本、两位教师审核后发布、按批次和考核时间分配。考试结果与训练能力画像隔离。</p>
    {error?<p role="alert" className="text-red-700">{error}</p>:null}{message?<p>{message}</p>:null}
    <section className="space-y-3 rounded border p-4"><h2 className="font-semibold">题本草案</h2>
      <textarea aria-label="题本JSON" className="w-full rounded border p-2 font-mono text-xs" rows={12} value={json} onChange={e=>setJson(e.target.value)}/>
      <button className="rounded bg-teal-700 px-4 py-2 text-white" onClick={()=>void create()}>创建待审题本</button>
      {forms.map(f=><div key={f.id} className="flex items-center justify-between border-t py-2"><span>#{f.id} {f.title} · {f.review_status}</span>{f.review_status!=="APPROVED_FOR_ASSESSMENT"?<button className="rounded border p-2" onClick={()=>void approve(f.id)}>核验审核并发布</button>:null}</div>)}
    </section>
    <section className="space-y-3 rounded border p-4"><h2 className="font-semibold">分配独立考试</h2>
    <p className="text-sm text-slate-600">此界面仅供管理员输入已确认的学生、题本及两位不同教师的数据库ID。分组和时间点对盲评者隐藏。</p>
    <div className="grid gap-2 sm:grid-cols-2">{(["student_id","form_id","cohort_code","study_group","timepoint","rater_a_id","rater_b_id","window_start","window_end"] as const).map(key=><label key={key} className="text-sm">{key}<input className="block w-full rounded border p-2" type={key.includes("window")?"datetime-local":["student_id","form_id","rater_a_id","rater_b_id"].includes(key)?"number":"text"} value={assignment[key]} onChange={e=>setAssignment(old=>({...old,[key]:["student_id","form_id","rater_a_id","rater_b_id"].includes(key)?Number(e.target.value):e.target.value}))}/></label>)}</div>
    <button onClick={()=>void assign()} className="rounded bg-teal-700 px-4 py-2 text-white">分配考试</button></section>
    <button className="rounded border px-4 py-2" onClick={()=>void exportData()}>导出管理员研究数据（敏感）</button>
  </div>;
