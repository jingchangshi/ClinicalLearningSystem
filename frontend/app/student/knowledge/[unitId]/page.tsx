import { getKnowledgeUnit } from "@/lib/api";

import { KnowledgeDetailClient } from "./KnowledgeDetailClient";

export default async function KnowledgeDetailPage({
  params,
}: {
  params: Promise<{ unitId: string }>;
}) {
  const resolvedParams = await params;
  const unit = await getKnowledgeUnit(resolvedParams.unitId);
  return <KnowledgeDetailClient unit={unit} />;
}
