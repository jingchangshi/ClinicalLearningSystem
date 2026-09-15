/**
 * Competency-change display helpers.
 *
 * These live outside the chart component on purpose: a module marked
 * `"use client"` turns its exports into client references, and a server
 * component that calls one during render fails the whole page. Both the chart
 * (client) and the evidence table (server) need the same formatting, so the
 * formatting lives here.
 */

export type CompetencyChange = {
  key: string;
  label: string;
  before: number | null;
  after: number | null;
  delta: number | null;
};

export type GrowthTrendPoint = {
  event_id: number;
  module_label: string;
  event_label: string;
  score: number | null;
  created_at: string;
  competency_changes: CompetencyChange[];
};

/** `鉴别诊断 58 → 64（+6）` */
export function changeText(change: CompetencyChange): string {
  const delta = change.delta ?? 0;
  return `${change.label} ${change.before} → ${change.after}（${delta >= 0 ? "+" : ""}${delta}）`;
}

/** The changes worth showing first: the ones that moved the most. */
export function headlineChanges(changes: CompetencyChange[], limit = 2): CompetencyChange[] {
  return [...changes].sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0)).slice(0, limit);
}
