import Link from "next/link";

import { getSPResult } from "@/lib/api";

export default async function SPResultPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const resolvedParams = await params;
  const result = await getSPResult(resolvedParams.sessionId);
  const scoreItems = [
    ["问诊完整性", result.history_taking_score],
    ["沟通表达", result.communication_score],
    ["临床推理", result.reasoning_score],
    ["人文关怀", result.humanistic_care_score],
  ];

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">{result.sp_case.title}</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">SP 考核反馈</h1>
            <p className="mt-2 max-w-3xl text-slate-600">{result.feedback}</p>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-500">总分</div>
            <div className="text-4xl font-semibold text-clinic">{result.total_score ?? "待评分"}</div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        {scoreItems.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="text-sm text-slate-500">{label}</div>
            <div className="mt-2 text-2xl font-semibold text-ink">{value ?? "待评分"}</div>
          </div>
        ))}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">诊断与处理总结</h2>
        <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-700">
          {result.diagnosis_summary ?? "尚未提交。"}
        </p>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">对话回顾</h2>
        <div className="mt-4 space-y-3">
          {result.transcript.map((item, index) => (
            <div
              key={`${item.role}-${index}`}
              className={`rounded-md p-3 text-sm leading-6 ${
                item.role === "student" ? "bg-clinic-soft text-teal-950" : "bg-slate-50 text-slate-700"
              }`}
            >
              <div className="font-medium">{item.role === "student" ? "学生" : "患者"}</div>
              <p className="mt-1">{item.message}</p>
            </div>
          ))}
        </div>
      </section>

      <Link href="/student/sp" className="inline-flex rounded-md bg-clinic px-4 py-2 text-white">
        返回 SP 病例
      </Link>
    </div>
  );
}
