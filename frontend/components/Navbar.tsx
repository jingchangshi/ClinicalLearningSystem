"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GraduationCap, LogIn, LogOut, UserPlus, UserRound } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";

const studentLinks = [
  { href: "/student/dashboard", label: "Dashboard", icon: GraduationCap },
  { href: "/student/profile", label: "Profile", icon: UserRound },
];

const teacherLinks = [
  { href: "/teacher/dashboard", label: "Dashboard", icon: GraduationCap },
  { href: "/teacher/students", label: "Profile", icon: UserRound },
];

export function Navbar() {
  const pathname = usePathname();
  const { role, isAuthenticated, loading, logout } = useAuth();
  const links = role === "student" ? studentLinks : role === "teacher" || role === "admin" ? teacherLinks : [];

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
          Login
        </Link>
        <Link className="flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100" href="/register">
          <UserPlus className="h-4 w-4" />
          Register
        </Link>
      </nav>
    );
  }

  return (
    <nav className="flex flex-wrap items-center justify-end gap-2 text-sm">
      {links.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          className={`flex items-center gap-1 rounded-md px-3 py-2 hover:bg-slate-100 ${
            pathname === href ? "bg-slate-100 text-clinic" : ""
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
        Logout
      </button>
    </nav>
  );
}
