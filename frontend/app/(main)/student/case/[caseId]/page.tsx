import { getCase, getReasoningSteps, getSession } from "@/lib/api";

import { CaseTrainingClient } from "./CaseTrainingClient";

export default async function CaseTrainingPage({
  params,
  searchParams,
}: {
  params: Promise<{ caseId: string }>;
  searchParams: Promise<{ sessionId?: string }>;
}) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;
  const [caseData, reasoning] = await Promise.all([
    getCase(resolvedParams.caseId),
    getReasoningSteps(),
  ]);
  const session = resolvedSearchParams.sessionId
    ? await getSession(Number(resolvedSearchParams.sessionId))
    : null;
  return (
    <CaseTrainingClient
      caseData={caseData}
      initialSession={session}
      steps={reasoning.steps}
    />
  );
}
