import { BarChart3, Clock, FileText, MessageSquareText, PenLine, Rows3 } from "lucide-react";

const columns = ["基础知识", "临床技能", "临床思维", "循证指南", "SP考核"];
const rows = ["医学知识", "技能操作", "信息采集", "鉴别诊断", "临床决策", "医患沟通"];
const matrix = [
  ["strong", "weak", "mid", "mid", "weak"],
  ["weak", "strong", "weak", "weak", "mid"],
  ["mid", "mid", "strong", "weak", "strong"],
  ["weak", "weak", "strong", "mid", "mid"],
  ["mid", "mid", "strong", "strong", "mid"],
  ["weak", "mid", "weak", "weak", "strong"],
];
const dataSources = [
  ["文本作答", PenLine],
  ["操作步骤", Rows3],
  ["多轮问诊对话", MessageSquareText],
  ["PICO结构化回答", FileText],
  ["评分轨迹", BarChart3],
  ["学习时序数据", Clock],
] as const;

function cellClass(value: string) {
  if (value === "strong") return "bg-teal-700 text-white";
  if (value === "mid") return "bg-teal-100 text-teal-950";
  return "bg-slate-100 text-slate-500";
}

export function MultimodalMatrixDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Multimodal Clinical Training Matrix</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">多模块多模态临床训练矩阵</h2>
        <p className="mt-2 text-slate-600">知识、技能、临床思维、循证指南与SP考核一体化，支撑临床胜任力培养全过程。</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="grid" style={{ gridTemplateColumns: `140px repeat(${columns.length}, minmax(0, 1fr))` }}>
            <div className="bg-slate-50 p-4 text-sm font-semibold text-slate-500">能力 / 模块</div>
            {columns.map((column) => (
              <div key={column} className="bg-slate-50 p-4 text-center text-sm font-semibold text-slate-700">
                {column}
              </div>
            ))}
            {rows.map((row, rowIndex) => (
              <>
                <div key={`${row}-label`} className="border-t border-slate-100 p-4 text-sm font-semibold text-ink">
                  {row}
                </div>
                {columns.map((column, columnIndex) => (
                  <div key={`${row}-${column}`} className="border-t border-slate-100 p-3">
                    <div className={`rounded-xl px-3 py-5 text-center text-sm font-semibold ${cellClass(matrix[rowIndex][columnIndex])}`}>
                      {matrix[rowIndex][columnIndex] === "strong" ? "强关联" : matrix[rowIndex][columnIndex] === "mid" ? "中关联" : "弱关联"}
                    </div>
                  </div>
                ))}
              </>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold">多模态数据来源</h3>
          <div className="mt-4 space-y-3">
            {dataSources.map(([item, Icon]) => (
              <div key={item} className="flex items-center gap-3 rounded-xl bg-cyan-50 px-4 py-3 text-sm font-semibold text-slate-700">
                <Icon className="h-5 w-5 text-clinic" />
                {item}
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
            深色表示该训练模块对对应能力维度贡献最强，可直接作为系统功能架构截图。
          </div>
        </div>
      </div>

      <p className="rounded-2xl bg-teal-900 px-6 py-4 text-center text-lg font-semibold text-white">
        ClinPath 不是单一问答工具，而是覆盖临床胜任力培养全过程的多模块 AI 教学系统。
      </p>
    </section>
  );
}
