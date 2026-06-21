"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { getMe, login as apiLogin, logout as apiLogout, register as apiRegister, type User } from "@/lib/api";

type AuthContextValue = {
  user: User | null;
  role: User["role"] | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (username: string, password: string, nextPath?: string | null) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
};

type RegisterPayload = {
  username: string;
  password: string;
  role: "student" | "teacher";
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useAuthSync(setUser, setLoading, pathname, router);

  async function login(username: string, password: string, nextPath?: string | null) {
    setLoading(true);
    try {
      await apiLogin(username, password);
      const currentUser = await getMe();
      setUser(currentUser);
      router.replace(safeNextPath(nextPath) ?? dashboardPath(currentUser));
      router.refresh();
      return currentUser;
    } finally {
      setLoading(false);
    }
  }

  async function register(payload: RegisterPayload) {
    setLoading(true);
    try {
      await apiRegister(payload);
      const currentUser = await getMe();
      setUser(currentUser);
      router.replace(dashboardPath(currentUser));
      router.refresh();
      return currentUser;
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    setLoading(true);
    try {
      await apiLogout();
      setUser(null);
      router.replace("/login");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user?.role ?? null,
        isAuthenticated: Boolean(user),
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}

export function AuthLifecycleManager() {
  return null;
}

function useAuthSync(
  setUser: (user: User | null) => void,
  setLoading: (loading: boolean) => void,
  pathname: string,
  router: ReturnType<typeof useRouter>,
) {
  useEffect(() => {
    let active = true;
    getMe()
      .then((currentUser) => {
        if (!active) return;
        setUser(currentUser);
        const correctedPath = routeCorrection(pathname, currentUser);
        if (correctedPath) {
          router.replace(correctedPath);
          router.refresh();
        }
      })
      .catch(() => {
        if (!active) return;
        setUser(null);
        if (isProtectedPath(pathname)) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          router.refresh();
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [pathname, router, setLoading, setUser]);
}

function dashboardPath(user: User) {
  return user.role === "student" ? "/student/dashboard" : "/teacher/dashboard";
}

function safeNextPath(nextPath?: string | null) {
  if (!nextPath?.startsWith("/") || nextPath.startsWith("//")) return null;
  if (nextPath.startsWith("/student") || nextPath.startsWith("/teacher")) return nextPath;
  return null;
}

function routeCorrection(pathname: string, user: User) {
  if (pathname === "/login" || pathname === "/register") return dashboardPath(user);
  if (user.role === "student" && pathname.startsWith("/teacher")) return "/student/dashboard";
  if ((user.role === "teacher" || user.role === "admin") && pathname.startsWith("/student")) return "/teacher/dashboard";
  return null;
}

function isProtectedPath(pathname: string) {
  return pathname.startsWith("/student") || pathname.startsWith("/teacher");
}
