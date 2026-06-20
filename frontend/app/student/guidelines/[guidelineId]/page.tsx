import { getGuideline } from "@/lib/api";

import { GuidelineDetailClient } from "./GuidelineDetailClient";

export default async function GuidelineDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ guidelineId: string }>;
  searchParams: Promise<{ studentId?: string }>;
}) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const guideline = await getGuideline(resolvedParams.guidelineId);
  return <GuidelineDetailClient guideline={guideline} initialStudentId={Number(resolvedSearch.studentId ?? 1)} />;
}
