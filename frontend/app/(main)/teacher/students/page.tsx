import Link from "next/link";

import { getTeacherDashboard } from "@/lib/api";

export default async function TeacherStudentsPage() {
  const data = await getTeacherDashboard();

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Students Overview</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">学生总览</h1>
        <p className="mt-2 text-slate-600">按学生查看最近得分、短板能力与推荐训练方向。</p>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2">学生姓名</th>
                <th className="px-3 py-2">当前阶段</th>
                <th className="px-3 py-2">最近得分</th>
                <th className="px-3 py-2">最弱能力</th>
                <th className="px-3 py-2">推荐训练方向</th>
                <th className="px-3 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              {data.students.map((student) => (
                <tr key={student.id} className="border-b border-slate-100">
                  <td className="px-3 py-3">{student.name}</td>
                  <td className="px-3 py-3">{student.current_stage}</td>
                  <td className="px-3 py-3">{student.recent_score ?? "待评分"}</td>
                  <td className="px-3 py-3">{student.weakest_ability}</td>
                  <td className="px-3 py-3">{student.recommended_training}</td>
                  <td className="px-3 py-3">
                    <Link href={`/teacher/students/${student.id}`} className="text-clinic hover:underline">
                      查看详情
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
