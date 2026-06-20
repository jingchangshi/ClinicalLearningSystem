"use client";

import { useEffect, useState } from "react";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";

import type { ChartPoint } from "@/lib/api";

export function CompetencyRadar({ data }: { data: ChartPoint[] }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="h-72 w-full">
      {mounted ? (
        <ResponsiveContainer>
          <RadarChart data={data}>
            <PolarGrid />
            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 11 }} />
            <Radar dataKey="score" stroke="#0f766e" fill="#0f766e" fillOpacity={0.25} />
          </RadarChart>
        </ResponsiveContainer>
      ) : null}
    </div>
  );
}
