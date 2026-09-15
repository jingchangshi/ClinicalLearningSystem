"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { changeText, headlineChanges } from "@/lib/competencyChanges";
import type { GrowthTrendPoint } from "@/lib/competencyChanges";
import { formatDateTime, formatShortDate } from "@/lib/format";

function TrendTooltip({ active, payload }: { active?: boolean; payload?: { payload: GrowthTrendPoint }[] }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-md">
      <div className="font-semibold text-ink">{formatDateTime(point.created_at)}</div>
      <div className="mt-1 text-slate-600">{point.module_label}</div>
      <div className="mt-1 font-semibold text-clinic">训练得分 {point.score ?? "待评分"}</div>
      {headlineChanges(point.competency_changes).map((change) => (
        <div key={change.key} className="mt-1 text-slate-600">
          {changeText(change)}
        </div>
      ))}
    </div>
  );
}

/**
 * Training score over time. The vertical axis is pinned to 0-100 so two
 * learners are comparable, and the tooltip explains what moved — a line whose
 * points cannot be explained is decoration, not evidence.
 */
export function GrowthTrendChart({ points }: { points: GrowthTrendPoint[] }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!points.length) {
    return <p className="mt-4 text-sm text-slate-500">暂无学习证据事件。</p>;
  }

  if (points.length === 1) {
    return (
      <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
        当前仅有 1 次有效训练记录，完成更多训练后可形成趋势。
        <div className="mt-1 text-slate-500">
          {formatDateTime(points[0].created_at)} · {points[0].module_label} · {points[0].score ?? "待评分"} 分
        </div>
      </div>
    );
  }

  const data = points.map((point) => ({ ...point, axis: formatShortDate(point.created_at) }));

  return (
    <div className="mt-4 h-72 w-full" data-testid="growth-trend-chart">
      {mounted ? (
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="axis" tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
            <Tooltip content={<TrendTooltip />} />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#0f766e"
              strokeWidth={2}
              dot={{ r: 4, fill: "#0f766e" }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : null}
    </div>
  );
}
