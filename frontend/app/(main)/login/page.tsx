import { Suspense } from "react";

import { LoginClient } from "./LoginClient";

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="rounded-2xl bg-white p-8 text-slate-600">正在加载登录页...</div>}>
      <LoginClient />
    </Suspense>
  );
}
