"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Check, Loader2, MessageSquare, Save, ShieldCheck } from "lucide-react";

import {
  getTutorConversation,
  missingStepsFrom,
  saveAnswer,
  sendTutorTurn,
  startSession,
  submitSession,
  type ReasoningStep,
  type SessionDetail,
  type StudentCaseDetail,
  type TutorState,
  type TutorTurn,
} from "@/lib/api";

type SaveState = "idle" | "saving" | "saved" | "error";
type TutorView = {
  turns: TutorTurn[];
  state: TutorState | null;
  stoppedReason: string | null;
  loaded: boolean;
};

export function CaseTrainingClient({
  caseData,
  initialSession,
  steps,
}: {
  caseData: StudentCaseDetail;
  initialSession: SessionDetail | null;
  steps: ReasoningStep[];
}) {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<number | null>(initialSession?.id ?? null);
  const [activeStep, setActiveStep] = useState(steps[0].key);
  const [answers, setAnswers] = useState<Record<string, string>>(() => initialAnswers(initialSession));
  const [savedAnswers, setSavedAnswers] = useState<Record<string, string>>(() => initialAnswers(initialSession));
  const [saveState, setSaveState] = useState<Record<string, SaveState>>({});
  // Historic (pre-tutor) coaching prompts stay visible for in-progress sessions.
  const [questions] = useState<Record<string, string>>(() => {
    const rows: Record<string, string> = {};
    initialSession?.ai_messages.forEach((message) => {
      rows[message.reasoning_step] = message.message;
    });
    return rows;
  });
  const [busy, setBusy] = useState(false);
  const [tutor, setTutor] = useState<Record<string, TutorView>>({});
  const [tutorReplies, setTutorReplies] = useState<Record<string, string>>({});
  const [tutorBusy, setTutorBusy] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [missingSteps, setMissingSteps] = useState<string[]>([]);
  const answersRef = useRef(answers);
  answersRef.current = answers;

  const activeTutor = tutor[activeStep];

  // Load the persisted coaching history when a step becomes active.
  useEffect(() => {
    if (!sessionId || tutor[activeStep]?.loaded) return;
    let cancelled = false;
    getTutorConversation(sessionId, activeStep)
      .then((conversation) => {
        if (cancelled) return;
        setTutor((value) => ({
          ...value,
          [activeStep]: {
            turns: conversation.turns,
            state: conversation.state,
            stoppedReason: conversation.stopped_reason ?? null,
            loaded: true,
          },
        }));
      })
      .catch(() => {
        if (!cancelled) {
          setTutor((value) => ({
            ...value,
            [activeStep]: { turns: [], state: null, stoppedReason: null, loaded: true },
          }));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeStep, sessionId, tutor]);

  const active = useMemo(
    () => steps.find((step) => step.key === activeStep) ?? steps[0],
    [activeStep, steps],
  );

  const stepTitle = useCallback(
    (key: string) => steps.find((step) => step.key === key)?.title ?? key,
    [steps],
  );

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const session = await startSession(null, caseData.id);
    setSessionId(session.session_id);
    window.history.replaceState(null, "", `?sessionId=${session.session_id}`);
    return session.session_id;
  }, [caseData.id, sessionId]);

  const persistStep = useCallback(async (id: number, step: string, text: string) => {
    setSaveState((value) => ({ ...value, [step]: "saving" }));
    try {
      await saveAnswer(id, step, text);
      setSavedAnswers((value) => ({ ...value, [step]: text }));
      setSaveState((value) => ({ ...value, [step]: "saved" }));
    } catch (reason) {
      setSaveState((value) => ({ ...value, [step]: "error" }));
      setError(reason instanceof Error ? `回答保存失败：${reason.message}` : "回答保存失败");
      throw reason;
    }
  }, []);

  const handleSave = useCallback(
    async (step: string) => {
      setBusy(true);
      setError(null);
      try {
        const id = await ensureSession();
        await persistStep(id, step, answersRef.current[step] ?? "");
      } catch {
        // Already reported through the per-step save state.
      } finally {
        setBusy(false);
      }
    },
    [ensureSession, persistStep],
  );

  /** Persist every step whose textarea differs from what the server last accepted. */
  const saveDirtySteps = useCallback(async () => {
    const id = await ensureSession();
    const dirty = steps
      .map((step) => step.key)
      .filter((key) => (answersRef.current[key] ?? "") !== (savedAnswers[key] ?? ""));
    for (const key of dirty) {
      await persistStep(id, key, answersRef.current[key] ?? "");
    }
    return id;
  }, [ensureSession, persistStep, savedAnswers, steps]);

  async function runTutor(step: string, message?: string) {
    setTutorBusy((value) => ({ ...value, [step]: true }));
    setError(null);
    try {
      const id = await ensureSession();
      // The tutor must reason about stored text, not about unsaved textareas.
      if ((answersRef.current[step] ?? "") !== (savedAnswers[step] ?? "")) {
        await persistStep(id, step, answersRef.current[step] ?? "");
      }
      const conversation = await sendTutorTurn(id, step, message);
      setTutor((value) => ({
        ...value,
        [step]: {
          turns: conversation.turns,
          state: conversation.state,
          stoppedReason: conversation.stopped_reason ?? null,
          loaded: true,
        },
      }));
      if (message) {
        setTutorReplies((value) => ({ ...value, [step]: "" }));
      }
    } catch (reason) {
      setError(reason instanceof Error ? `追问失败：${reason.message}` : "追问失败");
    } finally {
      setTutorBusy((value) => ({ ...value, [step]: false }));
    }
  }

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    setMissingSteps([]);
    try {
      const id = await saveDirtySteps();
      await submitSession(id);
      router.push(`/student/result/${id}`);
    } catch (reason) {
      const missing = missingStepsFrom(reason);
      if (missing.length > 0) {
        setMissingSteps(missing);
        setError(`还有 ${missing.length} 个阶段尚未作答或未保存：${missing.map(stepTitle).join("、")}`);
        setActiveStep(missing[0]);
      } else {
        setError(reason instanceof Error ? `提交失败：${reason.message}` : "提交失败");
      }
    } finally {
      setBusy(false);
    }
  }

  // A refresh or tab close must not silently drop the paragraph being typed.
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      const dirty = steps.some((step) => (answers[step.key] ?? "") !== (savedAnswers[step.key] ?? ""));
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [answers, savedAnswers, steps]);

  const dirtyCount = steps.filter(
    (step) => (answers[step.key] ?? "") !== (savedAnswers[step.key] ?? ""),
  ).length;

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">
          {caseData.disease_category} · {caseData.difficulty}
        </p>
        <h1 className="mt-1 text-2xl font-semibold">{caseData.title}</h1>
        <div className="mt-3 flex flex-wrap gap-2">
          {caseData.learning_objectives.map((item) => (
            <span key={item} className="rounded-md bg-clinic-soft px-2 py-1 text-xs text-teal-900">
              {item}
            </span>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
          <ClinicalBlock title="主诉" text={caseData.chief_complaint} />
          <ClinicalBlock title="现病史" text={caseData.history} />
          <ClinicalBlock title="体格检查" text={caseData.physical_exam} />
          <ClinicalBlock title="实验室检查" text={caseData.lab_results} />
          <ClinicalBlock title="影像资料" text={caseData.imaging} />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex flex-wrap gap-2">
            {steps.map((step) => (
              <button
                key={step.key}
                onClick={() => setActiveStep(step.key)}
                className={`rounded-md px-3 py-2 text-sm ${
                  activeStep === step.key ? "bg-clinic text-white" : "bg-slate-100 text-slate-600"
                } ${missingSteps.includes(step.key) ? "ring-2 ring-amber-400" : ""}`}
              >
                {step.title}
              </button>
            ))}
          </div>

          <div className="mt-5">
            <h2 className="font-semibold">{active.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{active.prompt}</p>
            <textarea
              value={answers[active.key] ?? ""}
              onChange={(event) => setAnswers((value) => ({ ...value, [active.key]: event.target.value }))}
              className="mt-3 min-h-44 w-full rounded-md border border-slate-300 p-3 outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                onClick={() => handleSave(active.key)}
                disabled={busy || !(answers[active.key] ?? "").trim()}
                className="inline-flex items-center gap-2 rounded-md bg-clinic px-4 py-2 text-white disabled:bg-slate-300"
              >
                <Save className="h-4 w-4" />
                保存回答
              </button>
              <button
                onClick={() => runTutor(active.key)}
                disabled={busy || tutorBusy[active.key] || (activeTutor?.turns.length ?? 0) > 0}
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 disabled:text-slate-300"
              >
                <MessageSquare className="h-4 w-4" />
                开始追问
              </button>
              <SaveIndicator state={saveState[active.key]} />
            </div>

            <StepTutor
              view={activeTutor}
              legacyQuestion={activeTutor?.turns.length ? undefined : questions[active.key]}
              reply={tutorReplies[active.key] ?? ""}
              busy={tutorBusy[active.key] ?? false}
              onReplyChange={(value) =>
                setTutorReplies((current) => ({ ...current, [active.key]: value }))
              }
              onSend={() => runTutor(active.key, (tutorReplies[active.key] ?? "").trim() || undefined)}
            />

          </div>
        </section>
      </div>

      {error ? (
        <p
          data-testid="training-error"
          className="rounded-md bg-red-50 px-4 py-3 text-sm text-alert"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-3">
        {dirtyCount > 0 ? (
          <span className="inline-flex items-center gap-2 text-sm text-amber-700">
            <AlertTriangle className="h-4 w-4" />
            还有 {dirtyCount} 个阶段的修改尚未保存，提交时会自动保存。
          </span>
        ) : null}
        <button
          onClick={handleSubmit}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md bg-ink px-5 py-3 text-white disabled:bg-slate-300"
        >
          <ShieldCheck className="h-4 w-4" />
          提交病例并生成反馈
        </button>
      </div>
    </div>
  );
}

function initialAnswers(session: SessionDetail | null): Record<string, string> {
  const rows: Record<string, string> = {};
  session?.answers.forEach((answer) => {
    rows[answer.step] = answer.answer_text;
  });
  return rows;
}

function StepTutor({
  view,
  legacyQuestion,
  reply,
  busy,
  onReplyChange,
  onSend,
}: {
  view?: TutorView;
  legacyQuestion?: string;
  reply: string;
  busy: boolean;
  onReplyChange: (value: string) => void;
  onSend: () => void;
}) {
  const turns = view?.turns ?? [];
  const state = view?.state ?? null;
  const stopped = Boolean(view?.stoppedReason);
  if (turns.length === 0 && !legacyQuestion) return null;

  return (
    <div className="mt-4 rounded-md border border-teal-100 bg-teal-50/40 p-3" data-testid="tutor-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-medium text-clinic">苏格拉底式追问</div>
        {state ? (
          <span className="text-xs text-slate-500">
            第 {state.turn_count}/{state.max_turns} 轮 · {tutorStageLabel(state.completion_state)}
          </span>
        ) : null}
      </div>

      {legacyQuestion ? (
        <p className="mt-2 rounded-md bg-white p-2 text-sm text-slate-700">
          <span className="mr-1 text-xs text-slate-500">升级前的历史追问：</span>
          {legacyQuestion}
        </p>
      ) : null}

      <ol className="mt-3 space-y-2">
        {turns.map((turn) => (
          <li
            key={turn.id}
            data-testid={`tutor-turn-${turn.role}`}
            className={`max-w-[95%] rounded-md px-3 py-2 text-sm ${
              turn.role === "tutor" ? "bg-white text-slate-800" : "ml-auto bg-clinic text-white"
            }`}
          >
            <span className="mr-2 text-xs opacity-70">{turn.role === "tutor" ? "导师" : "我"}</span>
            {turn.message}
          </li>
        ))}
      </ol>

      {state ? (
        <div className="mt-3 space-y-1 text-xs text-slate-600">
          {state.missing_reasoning_elements.length ? (
            <p>待补充推理要素：{state.missing_reasoning_elements.slice(0, 4).join("、")}</p>
          ) : null}
          {state.misconceptions.length ? <p className="text-amber-700">可能的问题：{state.misconceptions.join("；")}</p> : null}
          {state.safety_gap.length ? <p className="text-alert">安全性提醒：{state.safety_gap[0]}</p> : null}
        </div>
      ) : null}

      {stopped ? (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          本阶段追问已结束（{tutorStageLabel(state?.completion_state ?? "")}）。请把补充内容写入上方回答并保存，
          再提交病例。
        </p>
      ) : turns.length > 0 ? (
        <div className="mt-3">
          <textarea
            value={reply}
            onChange={(event) => onReplyChange(event.target.value)}
            placeholder="回答导师的问题（例如：为什么、依据是什么、如何排除）"
            className="min-h-20 w-full rounded-md border border-slate-300 p-2 text-sm"
          />
          <button
            onClick={onSend}
            disabled={busy || !reply.trim()}
            className="mt-2 inline-flex items-center gap-2 rounded-md bg-clinic px-3 py-2 text-sm text-white disabled:bg-slate-300"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquare className="h-4 w-4" />}
            继续追问
          </button>
        </div>
      ) : null}
    </div>
  );
}

function tutorStageLabel(state: string) {
  if (state === "coverage_sufficient") return "覆盖已充分";
  if (state === "max_turns_reached") return "已达本轮上限";
  if (state === "in_progress") return "进行中";
  return "未开始";
}

function SaveIndicator({ state }: { state?: SaveState }) {
  if (state === "saving") {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> 保存中...
      </span>
    );
  }
  if (state === "saved") {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-teal-700">
        <Check className="h-4 w-4" /> 已保存
      </span>
    );
  }
  if (state === "error") {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-alert">
        <AlertTriangle className="h-4 w-4" /> 保存失败
      </span>
    );
  }
  return null;
}

function ClinicalBlock({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <h2 className="font-medium">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-slate-600">{text}</p>
    </div>
  );
}
