import { getSPCase } from "@/lib/api";

import { SPChatClient } from "./SPChatClient";

export default async function SPCasePage({
  params,
  searchParams,
}: {
  params: Promise<{ caseId: string }>;
  searchParams: Promise<{ studentId?: string }>;
}) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const spCase = await getSPCase(resolvedParams.caseId);
  return <SPChatClient spCase={spCase} initialStudentId={Number(resolvedSearch.studentId ?? 1)} />;
}
