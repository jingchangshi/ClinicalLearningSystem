import { getGuideline } from "@/lib/api";

import { GuidelineDetailClient } from "./GuidelineDetailClient";

export default async function GuidelineDetailPage({
  params,
}: {
  params: Promise<{ guidelineId: string }>;
}) {
  const resolvedParams = await params;
  const guideline = await getGuideline(resolvedParams.guidelineId);
  return <GuidelineDetailClient guideline={guideline} />;
}
