import { Suspense } from "react";

import { SPListClient } from "./SPListClient";

export default function SPPage() {
  return (
    <Suspense fallback={<div className="rounded-lg border border-slate-200 bg-white p-5">正在加载 SP 病例...</div>}>
      <SPListClient />
    </Suspense>
  );
}
