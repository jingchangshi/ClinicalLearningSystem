/**
 * Timestamps arrive as naive UTC strings (2026-09-10T14:35:00). Every surface
 * renders them the same way, so two pages can never disagree about "when".
 */

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 16).replace("T", " ");
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

/** 09-10, for a time axis where the year is noise. */
export function formatShortDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(5, 10);
}
