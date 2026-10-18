/** Independent assessment API; intentionally separate from formative api.ts. */
const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
async function call<T>(path:string,init?:RequestInit):Promise<T>{
  const res=await fetch(BASE+path,{...init,credentials:"include",cache:"no-store",headers:{"Content-Type":"application/json",...(init?.headers??{})}});
  if(!res.ok)throw new Error("考核服务错误："+res.status+" "+(await res.text()).slice(0,200));
  return res.json();
}
export type AssessmentMine={id:number;status:string};
export type AssessmentStage={sitting_id:number;status:string;completed:number;stage?:{index:number;title:string;clinical_information:string;question:string}};
export type BlindQueueItem={blind_code:string;reviewed:boolean};
export type BlindDetail={blind_code:string;stages:Array<{title:string;clinical_information:string;question:string}>;answers:Array<{index:number;answer_text:string}>;rubric:Record<string,unknown>;answer_key:Record<string,unknown>;already_reviewed:boolean};
export const getAssessments=()=>call<AssessmentMine[]>("/assessments/my");
export const getAssessment=(id:number)=>call<AssessmentStage>("/assessments/my/"+id);
export const answerAssessmentStage=(id:number,answer_text:string)=>call<{completed:number}>("/assessments/my/"+id+"/answer",{method:"POST",body:JSON.stringify({answer_text})});
export const submitAssessment=(id:number)=>call<{status:string}>("/assessments/my/"+id+"/submit",{method:"POST"});
export const getBlindQueue=()=>call<BlindQueueItem[]>("/assessments/blind/queue");
export const getBlindDetail=(code:string)=>call<BlindDetail>("/assessments/blind/"+encodeURIComponent(code));
export const submitBlindReview=(code:string,scores:Record<string,number>)=>call<{status:string}>("/assessments/blind/"+encodeURIComponent(code)+"/review",{method:"POST",body:JSON.stringify({scores})});
