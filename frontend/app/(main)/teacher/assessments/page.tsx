"use client";

import { useState } from "react";

import { TabBar } from "@/components/assessment/AssessmentUi";
import { useAuth } from "@/components/AuthProvider";

import { AdjudicationPanel } from "./AdjudicationPanel";
import { BlindQueuePanel } from "./BlindQueuePanel";

type Tab = "blind" | "adjudication";

export default function TeacherAssessmentPage() {
  const { role, loading } = useAuth();
  const [tab, setTab] = useState<Tab>("blind");

  if (loading) {
    return (
      <p className="text-sm text-slate-500" role="status">
        正在确认账号权限…
      </p>
    );
  }

  if (role !== "teacher") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-ink">独立考核盲评</h1>
        <p role="alert" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          盲评与裁决只对具有独立教师身份的评分者开放。研究管理员负责安排与锁定，不参与评分，
          也不能读取评分内容。请使用课程负责人为你分配的教师账号登录。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm font-semibold tracking-[0.22em] text-clinic">独立考核 · 评分</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">盲评与分歧裁决</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          这里是独立考核的双教师盲评工作台。匿名答卷只暴露盲评编码、病例资料、学生作答、评分量表与锚点；
          学生身份、教学组别、批次与考核时点不下发到本页面。评分提交后即锁定，另一位评分者的分数也不可见。
        </p>
      </section>

      <TabBar
        tabs={[
          { key: "blind", label: "盲评队列" },
          { key: "adjudication", label: "分歧裁决" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "blind" ? <BlindQueuePanel /> : <AdjudicationPanel />}
    </div>
  );
}
