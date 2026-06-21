type HeatmapGridProps = {
  rows: string[];
  columns: string[];
  values: number[][];
};

function heatClass(value: number) {
  if (value >= 80) return "bg-teal-700 text-white";
  if (value >= 70) return "bg-teal-500 text-white";
  if (value >= 60) return "bg-amber-200 text-amber-950";
  return "bg-rose-100 text-rose-900";
}

export function HeatmapGrid({ rows, columns, values }: HeatmapGridProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="grid" style={{ gridTemplateColumns: `120px repeat(${columns.length}, minmax(0, 1fr))` }}>
        <div className="bg-slate-50 p-3 text-sm font-semibold text-slate-500">学生</div>
        {columns.map((column) => (
          <div key={column} className="bg-slate-50 p-3 text-center text-sm font-semibold text-slate-600">
            {column}
          </div>
        ))}
        {rows.map((row, rowIndex) => (
          <>
            <div key={`${row}-label`} className="border-t border-slate-100 p-3 text-sm font-semibold text-ink">
              {row}
            </div>
            {values[rowIndex].map((value, columnIndex) => (
              <div key={`${row}-${columns[columnIndex]}`} className="border-t border-slate-100 p-2">
                <div className={`rounded-lg px-3 py-2 text-center text-sm font-semibold ${heatClass(value)}`}>{value}</div>
              </div>
            ))}
          </>
        ))}
      </div>
    </div>
  );
}
