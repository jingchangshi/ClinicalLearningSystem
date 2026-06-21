type ClassHeatmapRow = {
  student_id: number;
  student_name: string;
  medical_knowledge: number;
  key_information: number;
  differential_diagnosis: number;
  evidence_integration: number;
  clinical_decision: number;
  evidence_based_medicine: number;
};

const columns = [
  ["medical_knowledge", "医学知识"],
  ["key_information", "关键信息"],
  ["differential_diagnosis", "鉴别诊断"],
  ["evidence_integration", "证据整合"],
  ["clinical_decision", "临床决策"],
  ["evidence_based_medicine", "循证医学"],
] as const;

function heatClass(value: number) {
  if (value >= 80) return "bg-teal-700 text-white";
  if (value >= 70) return "bg-teal-500 text-white";
  if (value >= 60) return "bg-amber-200 text-amber-950";
  return "bg-rose-100 text-rose-900";
}

export function ClassHeatmap({ rows }: { rows: ClassHeatmapRow[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full min-w-[820px] text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-3 text-left font-semibold">学生</th>
            {columns.map(([, label]) => (
              <th key={label} className="px-3 py-3 text-center font-semibold">{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.student_id} className="border-t border-slate-100">
              <td className="px-4 py-3 font-semibold text-ink">{row.student_name}</td>
              {columns.map(([key]) => (
                <td key={key} className="px-3 py-2">
                  <div className={`rounded-lg px-3 py-2 text-center font-semibold ${heatClass(row[key])}`}>{row[key]}</div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
