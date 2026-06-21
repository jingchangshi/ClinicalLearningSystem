import { Suspense } from "react";

import { RegisterClient } from "./RegisterClient";

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="rounded-2xl bg-white p-8 text-slate-600">正在加载注册页...</div>}>
      <RegisterClient />
    </Suspense>
  );
}
