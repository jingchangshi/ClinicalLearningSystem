import { Suspense } from "react";

import { KnowledgeListClient } from "./KnowledgeListClient";

export default function KnowledgePage() {
  return (
    <Suspense fallback={<div className="rounded-lg border border-slate-200 bg-white p-5">正在加载知识单元...</div>}>
      <KnowledgeListClient />
    </Suspense>
  );
}
