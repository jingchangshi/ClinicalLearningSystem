import Link from "next/link";
import { Stethoscope } from "lucide-react";

import { AuthProvider } from "@/components/AuthProvider";
import { Navbar } from "@/components/Navbar";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <Stethoscope className="h-6 w-6 text-clinic" />
            <span>ClinPath</span>
          </Link>
          <Navbar />
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-6">{children}</main>
    </AuthProvider>
  );
}
