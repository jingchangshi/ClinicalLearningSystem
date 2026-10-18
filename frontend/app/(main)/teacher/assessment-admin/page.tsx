"use client";

import { useState } from "react";

import { TabBar } from "@/components/assessment/AssessmentUi";
import { useAuth } from "@/components/AuthProvider";

import { AllocationPanel } from "./AllocationPanel";
import { AuditPanel } from "./AuditPanel";
import { CohortPanel } from "./CohortPanel";
import { DatasetPanel } from "./DatasetPanel";
import { SchedulePanel } from "./SchedulePanel";
import { SittingPanel } from "./SittingPanel";
import { useAdminDirectory } from "./adminShared";

type Tab = "sittings" | "cohorts" | "allocation" | "schedule" | "dataset" | "audit";

export default function AssessmentAdminPage() {
  const { role, loading } = useAuth();
  const [tab, setTab] = useState<Tab>("sittings");
  const directory = useAdminDirectory();

  if (loading) {
    return (
      <p className="text-sm text-slate-500" role="status">
        正在确认账号权限…
      </p>
    );
  }

  if (role !== "admin") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-ink">独立考核管理</h1>
        <p role="alert" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          该页面仅限研究管理员账号使用。研究管理员负责批次、排考、窗口与成绩锁定，不参与评分或题本审核。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm font-semibold tracking-[0.22em] text-clinic">独立考核 · 研究管理</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">独立考核管理</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          管理 7 个轮转批次、整批随机化、T0/T1 排考、考试窗口与成绩锁定。研究管理员可以安排和锁定，
          但不能代替教师评分或审核题本，也不能改写已锁定的评分——任何更正都通过审计留痕的作废与新版本完成。
        </p>
      </section>

      <TabBar
        tabs={[
          { key: "sittings", label: "考试与评分" },
          { key: "cohorts", label: "批次与入组" },
          { key: "allocation", label: "分配冻结" },
          { key: "schedule", label: "批量排考" },
          { key: "dataset", label: "数据集与一致性" },
          { key: "audit", label: "审计日志" },
        ]}
        active={tab}
        onChange={(key) => setTab(key)}
      />

      {tab === "sittings" ? <SittingPanel directory={directory} /> : null}
      {tab === "cohorts" ? <CohortPanel directory={directory} /> : null}
      {tab === "allocation" ? <AllocationPanel directory={directory} /> : null}
      {tab === "schedule" ? <SchedulePanel directory={directory} /> : null}
      {tab === "dataset" ? <DatasetPanel /> : null}
      {tab === "audit" ? <AuditPanel /> : null}
    </div>
  );
}
