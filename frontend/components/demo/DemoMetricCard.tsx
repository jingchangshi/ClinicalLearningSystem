import type { LucideIcon } from "lucide-react";

type DemoMetricCardProps = {
  title: string;
  value: string;
  note: string;
  icon: LucideIcon;
};

export function DemoMetricCard({ title, value, note, icon: Icon }: DemoMetricCardProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="mt-3 text-3xl font-semibold text-ink">{value}</p>
        </div>
        <span className="rounded-xl bg-teal-50 p-2 text-clinic">
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{note}</p>
    </div>
  );
}
