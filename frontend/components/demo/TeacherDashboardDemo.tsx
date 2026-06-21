import { Activity, ClipboardList, Target, TrendingUp, Users } from "lucide-react";

import { CompetencyRadarLarge } from "./CompetencyRadarLarge";
import { DemoMetricCard } from "./DemoMetricCard";
import { FlowArrow } from "./FlowArrow";
import { HeatmapGrid } from "./HeatmapGrid";

const radar = [
  { dimension: "循证决策", score: 61 },
  { dimension: "鉴别诊断", score: 66 },
  { dimension: "临床决策", score: 70 },
  { dimension: "医学知识", score: 75 },
  { dimension: "沟通能力", score: 78 },
];
const rows = ["学生A", "学生B", "学生C", "学生D", "学生E"];
const columns = ["医学知识", "技能操作", "鉴别诊断", "循证决策", "沟通能力"];
const values = [
  [78, 72, 61, 58, 82],
  [82, 76, 68, 60, 79],
  [70, 68, 57, 54, 74],
  [86, 80, 74, 66, 88],
  [76, 71, 64, 59, 81],
];
const loop = ["学生训练数据", "班级短板识别", "教师教学调整", "再训练", "效果评价"];

export function TeacherDashboardDemo() {
  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Teacher Analytics Dashboard</p>
        <h2 className="mt-2 text-3xl font-semibold text-ink">教师精准教学驾驶舱</h2>
        <p className="mt-2 text-slate-600">基于班级学习数据的教学诊断与干预建议，体现教师端教学应用与质量改进价值。</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <DemoMetricCard title="参与学生" value="48" note="覆盖临床医学本科三年级" icon={Users} />
        <DemoMetricCard title="完成训练" value="326次" note="知识、病例、指南、SP综合记录" icon={ClipboardList} />
        <DemoMetricCard title="平均能力提升" value="+13.2%" note="基于形成性评价前后测" icon={TrendingUp} />
        <DemoMetricCard title="当前共性短板" value="循证决策" note="班级最低能力维度" icon={Target} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
        <div>
          <h3 className="mb-3 text-lg font-semibold">班级能力热力图</h3>
          <HeatmapGrid rows={rows} columns={columns} values={values} />
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold">班级雷达图与共性短板</h3>
          <CompetencyRadarLarge data={radar} height={300} />
          <div className="grid gap-2">
            {["循证决策 61", "鉴别诊断 66", "临床决策 70"].map((item) => (
              <p key={item} className="rounded-xl bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-900">
                {item}
              </p>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 text-clinic">
            <Activity className="h-5 w-5" />
            <h3 className="text-lg font-semibold">AI Teaching Intervention Suggestions</h3>
          </div>
          <div className="mt-4 space-y-3">
            {["下周增加“指南推荐等级与PICO构建”小课", "安排“SLE活动与感染鉴别”病例讨论", "对循证能力低于60分学生推送个性化指南任务"].map((item) => (
              <p key={item} className="rounded-xl bg-cyan-50 px-4 py-3 text-sm font-semibold text-slate-700">
                {item}
              </p>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-teal-100 bg-teal-50 p-6 shadow-sm">
          <h3 className="text-lg font-semibold">教学闭环</h3>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            {loop.map((item, index) => (
              <div key={item} className="flex items-center gap-3">
                <span className="rounded-full bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm">{item}</span>
                {index < loop.length - 1 ? <FlowArrow /> : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
