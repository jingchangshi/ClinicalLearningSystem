import type { LucideIcon } from "lucide-react";

type MetricCardProps = {
  title: string;
  value: string;
  delta: string;
  icon: LucideIcon;
};

export function MetricCard({ title, value, delta, icon: Icon }: MetricCardProps) {
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
      <p className="mt-3 text-sm font-medium text-emerald-600">{delta} vs. last stage</p>
    </div>
  );
}
