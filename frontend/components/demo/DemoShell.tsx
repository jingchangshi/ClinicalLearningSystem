"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Camera, FlaskConical } from "lucide-react";

import { AcademicDashboardDemo } from "./AcademicDashboardDemo";
import { BloomPathwayDemo } from "./BloomPathwayDemo";
import { CompetencyGrowthMapDemo } from "./CompetencyGrowthMapDemo";
import { GrantStoryboardDemo } from "./GrantStoryboardDemo";
import { LearnerDigitalTwinDemo } from "./LearnerDigitalTwinDemo";

const views = [
  { key: "academic", label: "Academic Medicine Dashboard" },
  { key: "digital-twin", label: "Learner Digital Twin" },
  { key: "bloom", label: "Bloom 2-Sigma Adaptive Pathway" },
  { key: "growth-map", label: "Competency Growth Map" },
  { key: "storyboard", label: "Grant Screenshot Storyboard" },
] as const;

type ViewKey = (typeof views)[number]["key"];

function isViewKey(value: string | null): value is ViewKey {
  return views.some((view) => view.key === value);
}

export function DemoShell() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const viewParam = searchParams.get("view");
  const activeView: ViewKey = isViewKey(viewParam) ? viewParam : "academic";

  function selectView(view: ViewKey) {
    router.push(`/demo?view=${view}`, { scroll: false });
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      <section className="rounded-[2rem] border border-slate-200 bg-gradient-to-br from-white via-cyan-50 to-teal-50 p-8 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm font-semibold text-clinic shadow-sm">
              <FlaskConical className="h-4 w-4" />
              Prototype v2 / Medical Education AI / Adaptive Learning / OSCE-ready
            </div>
            <h1 className="mt-6 text-5xl font-semibold tracking-tight text-ink">ClinPath</h1>
            <p className="mt-3 text-xl text-slate-700">AI辅助临床教学与自适应学习路径系统</p>
          </div>
          <div className="max-w-sm rounded-2xl border border-cyan-100 bg-white/85 p-5 shadow-sm">
            <div className="flex items-center gap-3 text-clinic">
              <Camera className="h-5 w-5" />
              <p className="font-semibold">截图模式</p>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">建议浏览器宽度 1440px，适合申请书截图。</p>
            <Link href="/" className="mt-4 inline-flex text-sm font-medium text-clinic hover:underline">
              返回系统入口
            </Link>
          </div>
        </div>
      </section>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="grid gap-2 lg:grid-cols-5">
          {views.map((view) => (
            <button
              key={view.key}
              type="button"
              onClick={() => selectView(view.key)}
              className={`rounded-xl px-4 py-3 text-left text-sm font-semibold transition ${
                activeView === view.key ? "bg-clinic text-white shadow-sm" : "bg-slate-50 text-slate-600 hover:bg-cyan-50 hover:text-clinic"
              }`}
            >
              {view.label}
            </button>
          ))}
        </div>
      </section>

      <main className="mt-6">
        {activeView === "academic" ? <AcademicDashboardDemo /> : null}
        {activeView === "digital-twin" ? <LearnerDigitalTwinDemo /> : null}
        {activeView === "bloom" ? <BloomPathwayDemo /> : null}
        {activeView === "growth-map" ? <CompetencyGrowthMapDemo /> : null}
        {activeView === "storyboard" ? <GrantStoryboardDemo /> : null}
      </main>
    </div>
  );
}
