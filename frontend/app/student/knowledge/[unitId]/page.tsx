import { getKnowledgeUnit } from "@/lib/api";

import { KnowledgeDetailClient } from "./KnowledgeDetailClient";

export default async function KnowledgeDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ unitId: string }>;
  searchParams: Promise<{ studentId?: string }>;
}) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const unit = await getKnowledgeUnit(resolvedParams.unitId);
  return <KnowledgeDetailClient unit={unit} initialStudentId={Number(resolvedSearch.studentId ?? 1)} />;
}
