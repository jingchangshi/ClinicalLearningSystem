import { Suspense } from "react";

import { GuidelinesListClient } from "./GuidelinesListClient";

export default function GuidelinesPage() {
  return (
    <Suspense fallback={<div className="rounded-lg border border-slate-200 bg-white p-5">正在加载指南...</div>}>
      <GuidelinesListClient />
    </Suspense>
  );
}
