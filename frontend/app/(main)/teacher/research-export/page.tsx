import Link from "next/link";

import { exportResearchData } from "@/lib/api";

import { ResearchDataPreview } from "./ResearchDataPreview";

export default async function ResearchExportPage() {
  const data = await exportResearchData();
  const { summary } = data;
  const dateRange =
    summary.date_range.start && summary.date_range.end
      ? `${summary.date_range.start} 至 ${summary.date_range.end}`
      : "暂无记录";

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold tracking-[0.22em] text-clinic">教学驾驶舱 · 研究数据</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">匿名化研究数据</h1>
          <p className="mt-2 text-slate-600">
            只导出匿名学生编号，不包含学生姓名，用于形成性评价的课题研究数据整理。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href="/api/teacher/export/research-data.csv"
            className="rounded-md bg-clinic px-4 py-2 text-white"
            data-testid="research-csv-download"
          >
            下载完整匿名化 CSV
          </a>
          <Link href="/teacher/dashboard" className="rounded-md border border-slate-300 px-4 py-2 hover:border-clinic">
            返回教学驾驶舱
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <SummaryCard title="学生数" value={String(summary.student_count)} note="已匿名化为研究编号" />
        <SummaryCard title="训练记录数" value={String(summary.record_count)} note="覆盖全部学习证据事件" />
        <SummaryCard
          title="覆盖模块"
          value={String(summary.module_labels.length)}
          note={summary.module_labels.join(" / ") || "暂无"}
        />
        <SummaryCard title="数据时间范围" value={dateRange} note="跨越多个教学周更有研究价值" small />
      </section>

      <ResearchDataPreview rows={data.rows} previewLimit={summary.preview_limit} />

      <p className="text-sm text-slate-500">
        页面展示的是便于阅读的预览视图；下载的 CSV 才是完整研究数据集，使用 UTF-8 BOM 编码，可直接用 Excel 打开。
      </p>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  note,
  small,
}: {
  title: string;
  value: string;
  note: string;
  small?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{title}</p>
      <p className={`mt-3 font-semibold text-ink ${small ? "text-lg" : "text-2xl"}`}>{value}</p>
      <p className="mt-3 text-sm text-slate-600">{note}</p>
    </div>
  );
}
