"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";

const demoAccounts = [
  { label: "学生账号", username: "student1", password: "student123" },
  { label: "教师账号", username: "teacher", password: "teacher123" },
  { label: "管理员", username: "admin", password: "admin123" },
];

export function LoginClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, loading } = useAuth();
  const [username, setUsername] = useState("student1");
  const [password, setPassword] = useState("student123");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const user = await login(username, password);
      const next = searchParams.get("next");
      if (next?.startsWith("/")) {
        router.push(next);
      } else if (user.role === "student") {
        router.push("/student/dashboard");
      } else {
        router.push("/teacher/dashboard");
      }
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    }
  }

  return (
    <div className="mx-auto grid max-w-4xl gap-6 lg:grid-cols-[1fr_0.85fr]">
      <section className="rounded-[2rem] border border-teal-100 bg-gradient-to-br from-teal-700 to-cyan-700 p-8 text-white shadow-sm">
        <div className="inline-flex rounded-2xl bg-white/15 p-3">
          <ShieldCheck className="h-7 w-7" />
        </div>
        <h1 className="mt-6 text-4xl font-semibold">ClinPath 账户登录</h1>
        <p className="mt-4 leading-7 text-cyan-50">
          系统已启用 JWT 认证与角色权限控制。学生只能访问自己的学习数据，教师和管理员可进入教学管理与研究分析入口。
        </p>
        <div className="mt-8 grid gap-3">
          {demoAccounts.map((account) => (
            <button
              key={account.username}
              type="button"
              onClick={() => {
                setUsername(account.username);
                setPassword(account.password);
              }}
              className="rounded-2xl bg-white/15 px-4 py-3 text-left text-sm hover:bg-white/25"
            >
              <span className="font-semibold">{account.label}</span>
              <span className="ml-3 text-cyan-50">{account.username} / {account.password}</span>
            </button>
          ))}
        </div>
      </section>

      <form onSubmit={submit} className="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
        <h2 className="text-2xl font-semibold text-ink">登录</h2>
        <label className="mt-6 block text-sm font-medium text-slate-600">
          用户名
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3"
          />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-600">
          密码
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3"
          />
        </label>
        {error ? <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-alert">{error}</p> : null}
        <button
          disabled={loading}
          className="mt-6 w-full rounded-xl bg-clinic px-4 py-3 font-semibold text-white disabled:opacity-60"
        >
          {loading ? "登录中..." : "登录并进入系统"}
        </button>
      </form>
    </div>
  );
}
