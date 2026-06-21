"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { UserPlus } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";

export function RegisterClient() {
  const { register, loading } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"student" | "teacher">("student");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await register({ username, password, role });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "注册失败");
    }
  }

  return (
    <div className="mx-auto grid max-w-4xl gap-6 lg:grid-cols-[0.9fr_1fr]">
      <section className="rounded-[2rem] border border-emerald-100 bg-gradient-to-br from-emerald-700 to-teal-700 p-8 text-white shadow-sm">
        <div className="inline-flex rounded-2xl bg-white/15 p-3">
          <UserPlus className="h-7 w-7" />
        </div>
        <h1 className="mt-6 text-4xl font-semibold">创建 ClinPath 账号</h1>
        <p className="mt-4 leading-7 text-emerald-50">
          注册后系统会自动建立账户、写入安全 cookie，并进入对应角色工作台。
        </p>
      </section>

      <form onSubmit={submit} className="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
        <h2 className="text-2xl font-semibold text-ink">注册</h2>
        <label className="mt-6 block text-sm font-medium text-slate-600">
          用户名
          <input
            required
            minLength={3}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3"
          />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-600">
          密码
          <input
            required
            minLength={6}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3"
          />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-600">
          角色
          <select
            value={role}
            onChange={(event) => setRole(event.target.value as "student" | "teacher")}
            className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3"
          >
            <option value="student">学生</option>
            <option value="teacher">教师</option>
          </select>
        </label>
        {error ? <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-alert">{error}</p> : null}
        <button
          disabled={loading}
          className="mt-6 w-full rounded-xl bg-clinic px-4 py-3 font-semibold text-white disabled:opacity-60"
        >
          {loading ? "注册中..." : "注册并进入系统"}
        </button>
        <p className="mt-4 text-center text-sm text-slate-500">
          已有账号？{" "}
          <Link href="/login" className="font-medium text-clinic hover:underline">
            返回登录
          </Link>
        </p>
      </form>
    </div>
  );
}
