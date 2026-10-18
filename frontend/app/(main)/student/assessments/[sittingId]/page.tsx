import Link from "next/link";

import { AssessmentExamClient } from "./AssessmentExamClient";

export default async function StudentAssessmentPage({ params }: { params: Promise<{ sittingId: string }> }) {
  const { sittingId } = await params;
  const parsed = Number(sittingId);

  if (!Number.isInteger(parsed) || parsed <= 0) {
    return (
      <div className="space-y-4">
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-alert">
          这场考核的地址不正确。请从「我的独立考核」列表进入。
        </p>
        <Link href="/student/assessments" className="inline-flex rounded-md border border-slate-300 px-4 py-2">
          返回我的独立考核
        </Link>
      </div>
    );
  }

  return <AssessmentExamClient sittingId={parsed} />;
}
