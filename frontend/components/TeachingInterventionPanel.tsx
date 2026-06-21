import { Activity } from "lucide-react";

export function TeachingInterventionPanel({ interventions }: { interventions: string[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2 text-clinic">
        <Activity className="h-5 w-5" />
        <h3 className="text-lg font-semibold">AI Teaching Intervention Suggestions</h3>
      </div>
      <div className="mt-4 space-y-3">
        {interventions.map((item) => (
          <p key={item} className="rounded-xl bg-cyan-50 px-4 py-3 text-sm font-semibold text-slate-700">
            {item}
          </p>
        ))}
      </div>
    </div>
  );
}
