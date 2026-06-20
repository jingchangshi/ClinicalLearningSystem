import { getSkill } from "@/lib/api";

import { SkillDetailClient } from "./SkillDetailClient";

export default async function SkillDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ skillId: string }>;
  searchParams: Promise<{ studentId?: string }>;
}) {
  const resolvedParams = await params;
  const resolvedSearch = await searchParams;
  const skill = await getSkill(resolvedParams.skillId);
  return <SkillDetailClient skill={skill} initialStudentId={Number(resolvedSearch.studentId ?? 1)} />;
}
