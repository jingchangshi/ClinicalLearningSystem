"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, Save, ShieldCheck } from "lucide-react";

import {
  CaseDetail,
  getCoachQuestion,
  saveAnswer,
  SessionDetail,
  startSession,
  submitSession,
} from "@/lib/api";

const steps = [
  { key: "key_information", title: "关键信息提取", prompt: "提取关键阳性表现、关键阴性表现和异常检查结果。" },
  { key: "initial_diagnosis", title: "初步诊断及依据", prompt: "提出首要诊断，并从症状、实验室检查和器官受累说明依据。" },
  { key: "differential_diagnosis", title: "鉴别诊断", prompt: "列出需要排除的感染、肿瘤、HLH、其他结缔组织病等。" },
  { key: "examination", title: "进一步检查", prompt: "说明还需要哪些检查，以及每项检查解决什么临床问题。" },
  { key: "treatment", title: "治疗方案", prompt: "给出治疗方案、依据、风险评估和监测计划。" },
];

export function CaseTrainingClient({
  caseData,
  initialSession,
  initialStudentId,
}: {
  caseData: CaseDetail;
  initialSession: SessionDetail | null;
  initialStudentId: number;
}) {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<number | null>(initialSession?.id ?? null);
  const [activeStep, setActiveStep] = useState(steps[0].key);
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const rows: Record<string, string> = {};
    initialSession?.answers.forEach((answer) => {
      rows[answer.step] = answer.answer_text;
    });
    return rows;
  });
  const [questions, setQuestions] = useState<Record<string, string>>(() => {
    const rows: Record<string, string> = {};
    initialSession?.ai_messages.forEach((message) => {
      rows[message.reasoning_step] = message.message;
    });
    return rows;
  });
  const [busy, setBusy] = useState(false);

  const active = useMemo(() => steps.find((step) => step.key === activeStep) ?? steps[0], [activeStep]);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const session = await startSession(initialStudentId, caseData.id);
    setSessionId(session.session_id);
    window.history.replaceState(null, "", `?sessionId=${session.session_id}&studentId=${initialStudentId}`);
    return session.session_id;
  }

  async function handleSave(step: string) {
    setBusy(true);
    try {
      const id = await ensureSession();
      await saveAnswer(id, step, answers[step] ?? "");
    } finally {
      setBusy(false);
    }
  }

  async function handleCoach(step: string) {
    setBusy(true);
    try {
      const id = await ensureSession();
      const question = await getCoachQuestion(id, step, answers[step] ?? "");
      setQuestions((value) => ({ ...value, [step]: question.message }));
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit() {
    setBusy(true);
    try {
      const id = await ensureSession();
      await submitSession(id);
      router.push(`/student/result/${id}`);
    } finally {
      setBusy(false);
    }
  }

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
                }`}
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
            <div className="mt-3 flex flex-wrap gap-3">
              <button
                onClick={() => handleSave(active.key)}
                disabled={busy || !(answers[active.key] ?? "").trim()}
                className="inline-flex items-center gap-2 rounded-md bg-clinic px-4 py-2 text-white disabled:bg-slate-300"
              >
                <Save className="h-4 w-4" />
                保存回答
              </button>
              <button
                onClick={() => handleCoach(active.key)}
                disabled={busy}
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 disabled:text-slate-300"
              >
                <MessageSquare className="h-4 w-4" />
                获取追问
              </button>
            </div>

            {questions[active.key] ? (
              <div className="mt-4 rounded-md bg-slate-50 p-3">
                <div className="text-sm font-medium text-clinic">系统追问</div>
                <p className="mt-1 text-sm text-slate-700">{questions[active.key]}</p>
              </div>
            ) : null}
          </div>
        </section>
      </div>

      <div className="flex justify-end">
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

function ClinicalBlock({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <h2 className="font-medium">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-slate-600">{text}</p>
    </div>
  );
}
