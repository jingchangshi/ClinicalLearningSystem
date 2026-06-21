import { getSkill } from "@/lib/api";

import { SkillDetailClient } from "./SkillDetailClient";

export default async function SkillDetailPage({
  params,
}: {
  params: Promise<{ skillId: string }>;
}) {
  const resolvedParams = await params;
  const skill = await getSkill(resolvedParams.skillId);
  return <SkillDetailClient skill={skill} />;
}
