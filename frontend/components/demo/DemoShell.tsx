"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Camera, FlaskConical } from "lucide-react";

import { AdaptivePathwayDemo } from "./AdaptivePathwayDemo";
import { CompetencyAssessmentDemo } from "./CompetencyAssessmentDemo";
import { DemoTabNav } from "./DemoTabNav";
import { MultimodalMatrixDemo } from "./MultimodalMatrixDemo";
import { SPOSCEDemo } from "./SPOSCEDemo";
import { SystemOverviewDemo } from "./SystemOverviewDemo";
import { TeacherDashboardDemo } from "./TeacherDashboardDemo";

const views = ["overview", "competency", "pathway", "multimodal", "osce", "teacher"] as const;

export type DemoView = (typeof views)[number];

function isDemoView(value: string | null): value is DemoView {
  return views.some((view) => view === value);
}

export function DemoShell() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const viewParam = searchParams.get("view");
  const activeView: DemoView = isDemoView(viewParam) ? viewParam : "overview";

  function selectView(view: DemoView) {
    router.push(`/demo?view=${view}`, { scroll: false });
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      <section className="rounded-[2rem] border border-slate-200 bg-gradient-to-br from-white via-cyan-50 to-teal-50 p-8 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/85 px-4 py-2 text-sm font-semibold text-clinic shadow-sm">
              <FlaskConical className="h-4 w-4" />
              AI辅助临床能力形成性评价与个性化学习路径构建及应用研究
            </div>
            <h1 className="mt-6 text-5xl font-semibold tracking-tight text-ink">ClinPath 图版系统</h1>
            <p className="mt-3 text-xl text-slate-700">AI辅助临床教学与自适应学习路径系统</p>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
              面向课题申报截图，集中呈现多模块多模态训练、多维度能力评估、AI短板识别、个性化学习路径与教师精准干预。
            </p>
          </div>
          <div className="max-w-sm rounded-2xl border border-cyan-100 bg-white/85 p-5 shadow-sm">
            <div className="flex items-center gap-3 text-clinic">
              <Camera className="h-5 w-5" />
              <p className="font-semibold">申请书截图模式</p>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">建议浏览器宽度 1440px。每个视图均可独立截图用于申请书技术路线、评价体系或教学应用场景。</p>
            <Link href="/" className="mt-4 inline-flex text-sm font-medium text-clinic hover:underline">
              返回主站入口
            </Link>
          </div>
        </div>
      </section>

      <div className="mt-6">
        <DemoTabNav activeView={activeView} onSelect={selectView} />
      </div>

      <main className="mt-6">
        {activeView === "overview" ? <SystemOverviewDemo /> : null}
        {activeView === "competency" ? <CompetencyAssessmentDemo /> : null}
        {activeView === "pathway" ? <AdaptivePathwayDemo /> : null}
        {activeView === "multimodal" ? <MultimodalMatrixDemo /> : null}
        {activeView === "osce" ? <SPOSCEDemo /> : null}
        {activeView === "teacher" ? <TeacherDashboardDemo /> : null}
      </main>
    </div>
  );
}
