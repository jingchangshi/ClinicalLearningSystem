import { Suspense } from "react";

import { DemoShell } from "@/components/demo/DemoShell";

export default function DemoPage() {
  return (
    <Suspense fallback={<div className="rounded-2xl bg-white p-8 text-slate-600">正在加载 ClinPath 展示模式...</div>}>
      <DemoShell />
    </Suspense>
  );
}
