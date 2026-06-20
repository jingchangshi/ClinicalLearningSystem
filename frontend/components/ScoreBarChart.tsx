"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { ChartPoint } from "@/lib/api";

export function ScoreBarChart({ data }: { data: ChartPoint[] }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="h-72 w-full">
      {mounted ? (
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="dimension" tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="score" fill="#0f766e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : null}
    </div>
  );
}
