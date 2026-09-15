import { getAiInvocations, getAiStatus, getSystemVersion } from "@/lib/api";

import { AiRuntimeClient } from "./AiRuntimeClient";

export const dynamic = "force-dynamic";

export default async function RuntimePage() {
  const [status, version, audit] = await Promise.all([
    getAiStatus(),
    getSystemVersion(),
    getAiInvocations(15),
  ]);
  const frontendSha = process.env.NEXT_PUBLIC_BUILD_SHA ?? "unknown";

  return (
    <div className="space-y-6">
      <section>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clinic">Deployment &amp; AI Runtime</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">运行状态</h1>
        <p className="mt-2 text-slate-600">
          用于在 30 秒内确认「浏览器里跑的到底是哪一版」，以及 AI 是否真的可用。
        </p>
      </section>

      <section
        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
        data-testid="deployment-version"
      >
        <h2 className="font-semibold">部署版本</h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          <Row label="Environment" value={version.environment} />
          <Row
            label="Backend git SHA"
            value={`${version.git_sha_short ?? "unknown"}${version.git_dirty ? " (working tree has local changes)" : ""}`}
          />
          <Row label="Backend source fingerprint" value={version.backend_source_fingerprint} />
          <Row label="Frontend build SHA" value={frontendSha} />
          <Row label="Schema revision" value={version.schema_revision ?? "unknown"} />
          <Row label="Backend runtime" value={version.backend_runtime} />
          <Row label="AI configured" value={version.ai_configured ? "yes" : "no"} />
        </dl>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">AI Runtime</h2>
        <div className="mt-4">
          <AiRuntimeClient initialStatus={status} />
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="ai-audit">
        <h2 className="font-semibold">AI 调用审计</h2>
        <p className="mt-2 text-sm text-slate-600">
          每个 AI 能力一次调用事件，只记录元数据与证据引用，不记录 prompt / 响应正文。
        </p>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="py-2 pr-4">task_type</th>
                <th className="py-2 pr-4">events</th>
                <th className="py-2 pr-4">calls</th>
                <th className="py-2 pr-4">failures</th>
                <th className="py-2 pr-4">fallbacks</th>
                <th className="py-2 pr-4">avg latency</th>
              </tr>
            </thead>
            <tbody>
              {audit.by_task.map((row) => (
                <tr key={row.task_type} className="border-t border-slate-100">
                  <td className="py-2 pr-4 font-medium">{row.task_type}</td>
                  <td className="py-2 pr-4">{row.events}</td>
                  <td className="py-2 pr-4">{row.calls}</td>
                  <td className="py-2 pr-4">{row.failures}</td>
                  <td className="py-2 pr-4">{row.fallbacks}</td>
                  <td className="py-2 pr-4">{row.avg_latency_ms ?? 0} ms</td>
                </tr>
              ))}
              {audit.by_task.length === 0 ? (
                <tr>
                  <td className="py-2 text-slate-500" colSpan={6}>
                    暂无 AI 调用记录。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <h3 className="mt-5 text-sm font-semibold text-slate-700">最近事件</h3>
        <ul className="mt-2 space-y-1 text-xs text-slate-600">
          {audit.recent.slice(0, 8).map((row) => (
            <li key={row.id} className="flex flex-wrap gap-2 rounded-md bg-slate-50 px-3 py-2">
              <span className="font-medium text-slate-800">{row.task_type}</span>
              <span>{row.provider ?? "—"}/{row.model ?? "—"}</span>
              <span>{row.latency_ms} ms</span>
              <span>{row.success ? "success" : row.fallback_used ? "fallback" : "failed"}</span>
              <span className="text-slate-500">{row.evidence_ref ?? "—"}</span>
              <span className="text-slate-400">{row.created_at}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 font-medium text-slate-800">{value}</dd>
    </div>
  );
}
