"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Card, Feedback, Pill } from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  formatAssessmentMoment,
  listMyAssessments,
  sittingStatusLabel,
  type ExamSittingListRow,
  type SittingStatus,
} from "@/lib/assessmentApi";

const TIMEPOINT_LABELS: Record<string, string> = {
  T0: "基线考核",
  T1: "后测考核",
};

const STATUS_TONES: Record<SittingStatus, "slate" | "clinic" | "warn" | "alert"> = {
  assigned: "clinic",
  in_progress: "warn",
  ready_to_submit: "warn",
  submitted: "slate",
  expired: "alert",
};

function actionLabel(status: SittingStatus): string {
  switch (status) {
    case "assigned":
      return "开始考核";
    case "in_progress":
      return "继续作答";
    case "submitted":
      return "查看提交情况";
    default:
      return "查看";
  }
}

export default function StudentAssessmentsPage() {
  const [items, setItems] = useState<ExamSittingListRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await listMyAssessments());
      setError(null);
    } catch (reason) {
      setItems([]);
      setError(assessmentErrorMessage(reason, "无法加载你的考核安排，请检查网络后重试。"));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm font-semibold tracking-[0.22em] text-clinic">独立在线考核</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">我的独立考核</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          这是与病例训练分开的独立考核：系统不会给提示、不会追问、不会给正确答案，也不会给自动评分或学习推荐。
          每个阶段的答案提交后不能修改，提交后才会显示下一阶段新增的临床资料。
        </p>
      </section>

      <Feedback error={error} />

      <Card title="考核须知" description="进入考核前请先读一遍。">
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
          <li>请独立作答，不要查阅资料、不要使用 AI 工具、不要与他人交流。</li>
          <li>请在答案中不要写姓名、学号、床号等可识别信息，以保证评阅的匿名性。</li>
          <li>草稿会自动保存在服务器上；断网或刷新页面后可以继续作答，本机也会保留一份临时备份。</li>
          <li>超出开放时间将无法再提交；如遇断网等情况，可以在考核页面报告中断，由研究管理员登记处理。</li>
          <li>提交整份答卷后不再显示任何正确答案或成绩，只有提交成功的确认。</li>
        </ul>
      </Card>

      <Card title="考核安排">
        {items === null ? (
          <p className="text-sm text-slate-500" role="status">
            正在加载考核安排…
          </p>
        ) : items.length === 0 ? (
          <p className="text-sm text-slate-500">目前没有已开放的独立考核。开放时间到了以后会自动出现在这里。</p>
        ) : (
          <ul className="space-y-3">
            {items.map((item, index) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-4"
              >
                <div>
                  <p className="font-semibold text-ink">
                    第 {index + 1} 场 · {TIMEPOINT_LABELS[item.timepoint] ?? "独立考核"}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    开放时间：{formatAssessmentMoment(item.window_start)} 至 {formatAssessmentMoment(item.window_end)}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Pill tone={STATUS_TONES[item.status]}>{sittingStatusLabel(item.status)}</Pill>
                    {item.status === "expired" ? (
                      <span className="text-xs text-alert">窗口已关闭且未提交，请联系研究管理员。</span>
                    ) : null}
                  </div>
                </div>
                {item.status === "expired" ? (
                  <span className="text-sm text-slate-400">不可再作答</span>
                ) : (
                  <Link
                    href={`/student/assessments/${item.id}`}
                    className="rounded-md bg-clinic px-4 py-2 text-sm text-white hover:bg-teal-800"
                  >
                    {actionLabel(item.status)}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
