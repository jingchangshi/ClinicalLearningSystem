"use client";

import { useState } from "react";

import { TabBar } from "@/components/assessment/AssessmentUi";
import { useAuth } from "@/components/AuthProvider";

import { FormAdminPanel } from "./FormAdminPanel";
import { FormAuthorPanel } from "./FormAuthorPanel";
import { FormReviewPanel } from "./FormReviewPanel";

type Tab = "review" | "author" | "admin";

export default function AssessmentFormsPage() {
  const { role, loading } = useAuth();
  const [tab, setTab] = useState<Tab | null>(null);

  if (loading) {
    return (
      <p className="text-sm text-slate-500" role="status">
        正在确认账号权限…
      </p>
    );
  }

  if (role === "student") {
    return (
      <p role="alert" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
        该页面仅限教师与管理员账号使用。
      </p>
    );
  }

  const isAdmin = role === "admin";
  const tabs: { key: Tab; label: string }[] = isAdmin
    ? [
        { key: "admin", label: "题本审核状态与发布" },
        { key: "author", label: "创建题本 / 新版本" },
      ]
    : [
        { key: "review", label: "待我审核" },
        { key: "author", label: "创建题本 / 新版本" },
      ];
  const active = tab && tabs.some((item) => item.key === tab) ? tab : tabs[0].key;

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm font-semibold tracking-[0.22em] text-clinic">独立考核 · 题本</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">考核题本与双教师审核</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          题本必须由两位不同的真实教师独立审核通过，再由管理员核验发布；未经审核的题本不能用于考试。
          已发布并用于考试的版本冻结，修改医学内容只能创建新版本，历史答卷对应的题本不会被静默改变。
        </p>
      </section>

      <TabBar
        tabs={tabs}
        active={active}
        onChange={(key) => setTab(key)}
      />

      {active === "review" ? <FormReviewPanel /> : null}
      {active === "author" ? <FormAuthorPanel /> : null}
      {active === "admin" ? <FormAdminPanel /> : null}
    </div>
  );
}
