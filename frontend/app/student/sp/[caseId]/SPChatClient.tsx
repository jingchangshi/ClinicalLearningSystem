"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Send, ShieldCheck } from "lucide-react";

import { sendSPMessage, SPCase, SPSession, startSPSession, submitSPSession } from "@/lib/api";

export function SPChatClient({
  spCase,
}: {
  spCase: SPCase;
}) {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [transcript, setTranscript] = useState<SPSession["transcript"]>([]);
  const [message, setMessage] = useState("");
  const [diagnosisSummary, setDiagnosisSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const response = await startSPSession(null, spCase.id);
    setSessionId(response.session_id);
    setTranscript(response.session.transcript);
    window.history.replaceState(null, "", `?sessionId=${response.session_id}`);
    return response.session_id;
  }

  async function handleSend() {
    const text = message.trim();
    if (!text) return;
    setBusy(true);
    setError(null);
    try {
      const id = await ensureSession();
      setMessage("");
      const response = await sendSPMessage(id, text);
      setTranscript(response.transcript);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "SP 消息发送失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    try {
      const id = await ensureSession();
      await submitSPSession(id, diagnosisSummary);
      router.push(`/student/sp/result/${id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "SP 考核提交失败");
    } finally {
      setBusy(false);
    }
  }

  const visibleTranscript = transcript.length
    ? transcript
    : [{ role: "patient" as const, message: spCase.opening_statement }];

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">
          {spCase.disease_category} · {spCase.difficulty} · {spCase.emotional_style}
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">{spCase.title}</h1>
        <div className="mt-3 flex flex-wrap gap-2">
          {spCase.expected_tasks.map((task) => (
            <span key={task} className="rounded-md bg-clinic-soft px-2 py-1 text-xs text-teal-900">
              {task}
            </span>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">问诊对话</h2>
          <div className="mt-4 h-[460px] space-y-3 overflow-y-auto rounded-md bg-slate-50 p-4">
            {visibleTranscript.map((item, index) => (
              <div
                key={`${item.role}-${index}`}
                className={`flex ${item.role === "student" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[82%] rounded-lg px-4 py-3 text-sm leading-6 ${
                    item.role === "student" ? "bg-clinic text-white" : "bg-white text-slate-700"
                  }`}
                >
                  {item.message}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <input
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleSend();
              }}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
              placeholder="输入问诊问题..."
            />
            <button
              onClick={handleSend}
              disabled={busy || !message.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-clinic px-4 py-2 text-white disabled:bg-slate-300"
            >
              <Send className="h-4 w-4" />
              发送
            </button>
          </div>
          {error ? <p className="mt-3 text-sm text-alert">{error}</p> : null}
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">提交初步判断</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            请概括初步诊断、重要鉴别诊断、下一步检查和处理计划。
          </p>
          <textarea
            value={diagnosisSummary}
            onChange={(event) => setDiagnosisSummary(event.target.value)}
            className="mt-4 min-h-72 w-full rounded-md border border-slate-300 p-3 text-sm outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
          />
          <button
            onClick={handleSubmit}
            disabled={busy || !diagnosisSummary.trim()}
            className="mt-4 inline-flex items-center gap-2 rounded-md bg-ink px-4 py-2 text-white disabled:bg-slate-300"
          >
            <ShieldCheck className="h-4 w-4" />
            提交 SP 考核
          </button>
        </section>
      </div>
    </div>
  );
}
