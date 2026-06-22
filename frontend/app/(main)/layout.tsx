import Link from "next/link";
import { Stethoscope } from "lucide-react";

import { AuthProvider } from "@/components/AuthProvider";
import { Navbar } from "@/components/Navbar";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <header className="border-b border-slate-200 bg-white">
        <div className="app-container flex items-center justify-between py-4">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <Stethoscope className="h-6 w-6 text-clinic" />
            <span>ClinPath</span>
          </Link>
          <Navbar />
        </div>
      </header>
      <main className="app-container">
        <div className="page-container">{children}</div>
      </main>
    </AuthProvider>
  );
}
