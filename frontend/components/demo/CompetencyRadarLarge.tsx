"use client";

import { useEffect, useState } from "react";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";

export type CompetencyPoint = {
  dimension: string;
  score: number;
};

export function CompetencyRadarLarge({ data, height = 390 }: { data: CompetencyPoint[]; height?: number }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="w-full" style={{ height }}>
      {mounted ? (
        <ResponsiveContainer>
          <RadarChart data={data}>
            <PolarGrid stroke="#cbd5e1" />
            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12, fill: "#334155" }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 11, fill: "#64748b" }} />
            <Radar dataKey="score" stroke="#0f766e" fill="#0f766e" fillOpacity={0.28} />
          </RadarChart>
        </ResponsiveContainer>
      ) : null}
    </div>
  );
}
