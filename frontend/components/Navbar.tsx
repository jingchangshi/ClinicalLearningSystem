"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, BookOpen, GraduationCap, History, LogIn, LogOut, Route, Settings, UserPlus, UserRound, Users } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";

const showRegistration = process.env.NEXT_PUBLIC_ALLOW_PUBLIC_REGISTRATION !== "false";

const studentLinks = [
  { href: "/student/dashboard", label: "学习首页", icon: GraduationCap },
  { href: "/student/pathway", label: "学习路径", icon: Route },
  { href: "/student/knowledge", label: "知识学习", icon: BookOpen },
  { href: "/student/profile", label: "能力画像", icon: UserRound },
  { href: "/student/history", label: "学习记录", icon: History },
];

const teacherLinks = [
  { href: "/teacher/dashboard", label: "教学驾驶舱", icon: GraduationCap },
  { href: "/teacher/students", label: "学生画像", icon: Users },
  { href: "/teacher/research-export", label: "研究数据", icon: BarChart3 },
  { href: "/teacher/runtime", label: "系统状态", icon: Activity },
];

const adminLinks = [
  { href: "/teacher/dashboard", label: "教学驾驶舱", icon: GraduationCap },
  { href: "/teacher/cases", label: "病例管理", icon: Settings },
  { href: "/teacher/students", label: "学生画像", icon: Users },
  { href: "/teacher/runtime", label: "系统状态", icon: Activity },
];

function getMenuByRole(role: string | null) {
  if (role === "student") return studentLinks;
  if (role === "teacher") return teacherLinks;
  if (role === "admin") return adminLinks;
  return [];
}

export function Navbar() {
  const pathname = usePathname();
  const { role, isAuthenticated, loading, logout } = useAuth();
  const links = getMenuByRole(role);

  async function handleLogout() {
    await logout();
  }

  if (loading) {
    return <nav className="h-9 w-24 rounded-md bg-slate-100" aria-label="正在加载导航" />;
  }

  if (!isAuthenticated) {
    return (
      <nav className="flex items-center gap-2 text-sm">
        <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/login">
          <LogIn className="h-4 w-4" />
          登录
        </Link>
        {showRegistration ? (
          <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/register">
            <UserPlus className="h-4 w-4" />
            注册
          </Link>
        ) : null}
      </nav>
    );
  }

  // A route is "current" not only on its own path: /student/history/12 and
  // /teacher/students/3 must keep their section highlighted, otherwise a click
  // looks like it did nothing.
  const isCurrent = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <nav className="flex flex-wrap items-center justify-end gap-2 text-sm">
      {links.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          aria-current={isCurrent(href) ? "page" : undefined}
          className={`flex items-center gap-1 rounded-md border px-3 py-2 ${
            isCurrent(href)
              ? "border-clinic bg-clinic-soft font-semibold text-clinic"
              : "border-transparent text-slate-700 hover:bg-slate-100"
          }`}
          href={href}
        >
          <Icon className="h-4 w-4" />
          {label}
        </Link>
      ))}
      <button
        type="button"
        onClick={handleLogout}
        className="flex items-center gap-1 rounded-md px-3 py-2 text-slate-700 hover:bg-slate-100"
      >
        <LogOut className="h-4 w-4" />
        退出登录
      </button>
    </nav>
  );
}
