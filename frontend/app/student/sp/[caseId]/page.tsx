import { getSPCase } from "@/lib/api";

import { SPChatClient } from "./SPChatClient";

export default async function SPCasePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const resolvedParams = await params;
  const spCase = await getSPCase(resolvedParams.caseId);
  return <SPChatClient spCase={spCase} />;
}
