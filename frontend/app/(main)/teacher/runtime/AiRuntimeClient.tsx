"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";

import { probeAi, type AiStatus } from "@/lib/api";

export function AiRuntimeClient({ initialStatus }: { initialStatus: AiStatus }) {
  const [status, setStatus] = useState(initialStatus);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runProbe() {
    setProbing(true);
    setError(null);
    try {
      const result = await probeAi();
      setStatus((value) => ({
        ...value,
        configured: result.configured,
        provider: result.provider,
        model: result.model,
        reachable: result.reachable,
        last_probe_latency_ms: result.latency_ms,
        last_error_type: result.error_type,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "探测失败");
    } finally {
      setProbing(false);
    }
  }

  return (
    <div className="space-y-4">
      <dl className="grid gap-3 sm:grid-cols-2">
        <Row label="Configured" value={status.configured ? "yes" : "no"} />
        <Row label="Provider" value={status.provider ?? "—"} />
        <Row label="Model" value={status.model ?? "—"} />
        <Row label="Reachable" value={reachableText(status.reachable)} />
        <Row label="Last probe" value={status.last_probe_at ?? "未探测"} />
        <Row
          label="Latency"
          value={status.last_probe_latency_ms === null ? "—" : `${status.last_probe_latency_ms} ms`}
        />
        <Row label="Last error type" value={status.last_error_type ?? "none"} />
        <Row label="Timeout / retries" value={`${status.timeout_seconds}s / ${status.max_retries}`} />
        <Row label="Last evaluation source" value={status.last_call_mode ?? "—"} />
        <Row label="Calls / failures / fallbacks" value={`${status.calls} / ${status.failures} / ${status.fallbacks}`} />
      </dl>

      {!status.configured ? (
        <p className="flex items-center gap-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <AlertTriangle className="h-4 w-4" /> 未配置模型凭据：所有评分与追问以规则降级模式运行（degraded）。
        </p>
      ) : null}
      {status.reachable === false ? (
        <p className="flex items-center gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-alert">
          <AlertTriangle className="h-4 w-4" /> 模型当前不可达：训练结果会标记为 rule fallback。
        </p>
      ) : null}
      {status.reachable === true ? (
        <p className="flex items-center gap-2 rounded-md bg-teal-50 px-3 py-2 text-sm text-teal-800">
          <CheckCircle2 className="h-4 w-4" /> 模型可达，评分会走真实语义评价。
        </p>
      ) : null}
      {status.deprecated_variables_in_use.length ? (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          仍在使用旧的变量名：{status.deprecated_variables_in_use.join("、")}。建议迁移到 LLM_* 规范命名。
        </p>
      ) : null}

      <button
        type="button"
        onClick={runProbe}
        disabled={probing}
        className="inline-flex items-center gap-2 rounded-md bg-clinic px-4 py-2 text-white disabled:bg-slate-300"
      >
        <RefreshCw className={`h-4 w-4 ${probing ? "animate-spin" : ""}`} />
        {probing ? "探测中..." : "测试连通性"}
      </button>
      {error ? <p className="text-sm text-alert">{error}</p> : null}
      <p className="text-xs text-slate-500">
        该页面不会显示任何 API Key、Authorization 头或 provider 原始返回内容。
      </p>
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

function reachableText(reachable: boolean | null) {
  if (reachable === true) return "yes";
  if (reachable === false) return "no";
  return "未探测";
}
