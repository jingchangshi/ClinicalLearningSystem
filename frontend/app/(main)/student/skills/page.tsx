import { Suspense } from "react";

import { SkillsListClient } from "./SkillsListClient";

export default function SkillsPage() {
  return (
    <Suspense fallback={<div className="rounded-lg border border-slate-200 bg-white p-5">正在加载技能项目...</div>}>
      <SkillsListClient />
    </Suspense>
  );
}
