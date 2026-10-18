import Link from "next/link";
import { AlertTriangle, Download, FlaskConical, ShieldAlert } from "lucide-react";

import {
  getDemoResearchDictionary,
  getDemoResearchExpertReview,
  getDemoResearchMeta,
  getDemoResearchStudents,
  getDemoResearchSummary,
} from "@/lib/api";

import { DemoStudentExplorer } from "./DemoStudentExplorer";

/**
 * Teacher-facing page for the synthetic teaching-research demo (work package D).
 *
 * This page is intentionally separate from /teacher/research-export: that one
 * serves real (anonymised) learning records. Nothing here is a real student, a
 * real rater or a real teaching effect, and the banner says so above every other
 * element so that a screenshot cannot crop it out.
 */
export default async function ResearchDemoPage() {
  const [meta, summary, students, dictionary, expertReview] = await Promise.all([
    getDemoResearchMeta(),
    getDemoResearchSummary(),
    getDemoResearchStudents(),
    getDemoResearchDictionary(),
    getDemoResearchExpertReview(),
  ]);

  const formatP = (value: number) => (value < 0.001 ? "< 0.001（模拟）" : value.toFixed(4));

  return (
    <div className="space-y-6">
      {/* Sticky on purpose: the marker must be present in any viewport slice. */}
      <div
        role="alert"
        data-testid="demo-research-banner"
        className="sticky top-0 z-10 rounded-xl border-2 border-amber-400 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-900 shadow-sm"
      >
        <span className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          合成教学研究演示｜虚拟学生、虚拟评分者｜不代表真实教学成效
        </span>
        <span className="mt-1 block text-xs font-normal text-amber-800">
          数据集 {meta.dataset_id} · 随机种子 {meta.seed} · 全部记录标记 {meta.data_origin}
        </span>
      </div>

      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold tracking-[0.22em] text-amber-700">教学驾驶舱 · 模拟研究</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">合成教学研究演示</h1>
          <p className="mt-2 max-w-3xl text-slate-600">{meta.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href="/api/teacher/demo-research/export.csv"
            className="flex items-center gap-2 rounded-md bg-amber-600 px-4 py-2 text-white"
            data-testid="demo-research-csv"
          >
            <Download className="h-4 w-4" />
            下载 SYNTHETIC CSV
          </a>
          <Link href="/teacher/research-export" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
            前往真实研究数据
          </Link>
          <Link href="/teacher/dashboard" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
            返回教学驾驶舱
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <StatCard label="虚拟学生" value={String(meta.counts.students)} note="CBL 30 / ClinPath 30" />
        <StatCard label="独立前后测" value={String(meta.counts.assessments)} note="每人 T0、T1 各一条" />
        <StatCard label="模拟训练记录" value={String(meta.counts.learning_sessions)} note="每人 3 次" />
        <StatCard label="模拟五阶段作答" value={String(meta.counts.reasoning_steps)} note="仅干预组：3 病例 × 5 阶段 × 30 人" />
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="flex items-center gap-2 font-semibold">
          <FlaskConical className="h-5 w-5 text-amber-600" />
          研究设计与结果（模拟）
        </h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div className="space-y-1 text-sm text-slate-600">
            <p>分组：CBL vs ClinPath 辅助病例教学，各 30 人</p>
            <p>时点：T0（基线）/ T1（结课）</p>
            <p>主结局：{meta.design.primary_outcome}</p>
            <p>考核：{meta.design.assessment}</p>
            <p>批次：{meta.design.cohorts.join(" / ")}</p>
          </div>
          <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-semibold">预设情景说明</p>
            <p className="mt-1">
              生成器在造数时注入的两组提升期望约为 CBL {meta.scenario_assumptions.nominal_CBL_gain} 分、
              ClinPath {meta.scenario_assumptions.nominal_CLINPATH_gain} 分。下面的 P 值是统计程序对这种
              <strong>模拟差异</strong>的计算结果，不是从真实学生中发现的规律。
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">两组均值与模拟效应</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {(["CBL", "CLINPATH"] as const).map((key) => {
            const group = summary.groups[key];
            return (
              <div key={key} className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-baseline justify-between">
                  <span className="font-medium">{group.label}</span>
                  <span className="text-sm text-slate-500">n = {group.n}</span>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                  <Metric label="T0 均值" value={group.pre_mean.toFixed(2)} />
                  <Metric label="T1 均值" value={group.post_mean.toFixed(2)} />
                  <Metric label="平均提升" value={group.gain_mean.toFixed(2)} />
                </div>
                <p className="mt-2 text-xs text-slate-500">提升标准差 {group.gain_sd.toFixed(2)}</p>
              </div>
            );
          })}
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl bg-slate-50 p-4 text-sm">
            <p className="font-semibold">{summary.difference.label}</p>
            <p className="mt-2 text-2xl font-semibold text-clinic">{summary.difference.value.toFixed(2)} 分</p>
            <p className="mt-1 text-slate-600">
              95% CI {summary.difference.ci95[0].toFixed(2)} – {summary.difference.ci95[1].toFixed(2)}
            </p>
            <p className="mt-1 text-slate-600">
              Welch t = {summary.difference.welch_t}，df = {summary.difference.welch_df}，P {formatP(summary.difference.welch_p)}
            </p>
          </div>
          <div className="rounded-xl bg-slate-50 p-4 text-sm">
            <p className="font-semibold">{summary.ancova.label}</p>
            <p className="mt-2 text-2xl font-semibold text-clinic">{summary.ancova.value.toFixed(2)} 分</p>
            <p className="mt-1 text-slate-600">
              95% CI {summary.ancova.ci95[0].toFixed(2)} – {summary.ancova.ci95[1].toFixed(2)}
            </p>
            <p className="mt-1 text-slate-600">P {formatP(summary.ancova.p_value)}</p>
          </div>
        </div>
        <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{summary.analysis_note}</p>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">可筛选的虚拟学生</h2>
        <p className="mt-1 text-sm text-slate-600">
          点击任一研究编号查看该虚拟学生的六维前后测、五阶段模拟作答与训练过程。
        </p>
        <DemoStudentExplorer initial={students.students} />
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="flex items-center gap-2 font-semibold">
          <ShieldAlert className="h-5 w-5 text-amber-600" />
          数据来源与可复现性
        </h2>
        <div className="mt-3 grid gap-3 text-sm text-slate-600 md:grid-cols-2">
          <div>
            <p>描述统计：{meta.methods.descriptive}</p>
            <p className="mt-1">提升检验：{meta.methods.gain_test}</p>
            <p className="mt-1">基线校正：{meta.methods.baseline_adjusted}</p>
            <p className="mt-1">真值源：{meta.methods.source}</p>
          </div>
          <div>
            <p>生成器：{meta.generator.script}（{meta.generator.version}）</p>
            <p className="mt-1">{meta.generator.note}</p>
            <ul className="mt-2 space-y-1 text-xs text-slate-500">
              {meta.files.map((file) => (
                <li key={file.name}>
                  {file.path} · sha256 {file.sha256.slice(0, 12)}…
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">教学研究数据字典</h2>
        <div className="mt-3 max-h-80 overflow-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="sticky top-0 bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2">实体</th>
                <th className="px-3 py-2">字段</th>
                <th className="px-3 py-2">类型</th>
                <th className="px-3 py-2">定义</th>
                <th className="px-3 py-2">要求</th>
              </tr>
            </thead>
            <tbody>
              {dictionary.fields.map((field) => (
                <tr key={`${field.entity}-${field.field}`} className="border-b border-slate-100">
                  <td className="px-3 py-2">{field.entity}</td>
                  <td className="px-3 py-2 font-medium">{field.field}</td>
                  <td className="px-3 py-2 text-slate-500">{field.type}</td>
                  <td className="px-3 py-2">{field.definition}</td>
                  <td className="px-3 py-2 text-slate-500">{field.requirement}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-amber-300 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">真实教师专家审核</h2>
        <p className="mt-2 text-sm text-amber-900">
          状态：<strong>待审核（PENDING_REAL_REVIEW）</strong> · 待填写 {meta.expert_review.pending_rows} / {meta.expert_review.total_rows} 项
        </p>
        <p className="mt-1 text-sm text-slate-600">{meta.expert_review.note}</p>
        <p className="mt-1 text-xs text-slate-500">模板路径：{meta.expert_review.template}</p>
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-medium">展开待审核清单</summary>
          <div className="mt-2 max-h-64 overflow-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-3 py-2">审核人席位</th>
                  <th className="px-3 py-2">病例</th>
                  <th className="px-3 py-2">主题</th>
                  <th className="px-3 py-2">审核人</th>
                  <th className="px-3 py-2">日期</th>
                  <th className="px-3 py-2">结论</th>
                </tr>
              </thead>
              <tbody>
                {expertReview.rows.map((row) => (
                  <tr key={`${row.reviewer_slot}-${row.case_id}`} className="border-b border-slate-100">
                    <td className="px-3 py-2">{row.reviewer_slot}</td>
                    <td className="px-3 py-2">{row.case_id}</td>
                    <td className="px-3 py-2">{row.case_topic}</td>
                    <td className="px-3 py-2 text-slate-400">{row.reviewer_name || "—"}</td>
                    <td className="px-3 py-2 text-slate-400">{row.review_date || "—"}</td>
                    <td className="px-3 py-2 text-amber-700">{row.final_approval}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
    </div>
  );
}

function StatCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-ink">{value}</p>
      <p className="mt-3 text-sm text-slate-600">{note}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-semibold text-ink">{value}</p>
    </div>
  );
}
