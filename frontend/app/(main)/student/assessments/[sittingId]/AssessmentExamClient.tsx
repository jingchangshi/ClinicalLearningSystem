"use client";

/**
 * The student's独立考核 page.
 *
 * The server decides everything: which stage is released, whether a stage may be
 * answered, whether the window is open. This client only renders the stage the
 * server handed it and never holds a future stage, a reference answer or a
 * score. Drafts are saved to the server (and mirrored to this browser so a
 * disconnected tab can recover), and every failure is visible rather than
 * silent.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button, Card, Feedback, Pill, StageBlock } from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  formatAssessmentClock,
  formatAssessmentMoment,
  getMyAssessment,
  isNetworkFailure,
  reportAssessmentInterruption,
  saveAssessmentDraft,
  startAssessment,
  submitAssessment,
  submitAssessmentStage,
  type ExamView,
} from "@/lib/assessmentApi";

const STAGE_TOTAL = 5;
const AUTOSAVE_DELAY_MS = 3000;
const RETRY_DELAY_MS = 5000;

type SaveState = "idle" | "dirty" | "saving" | "saved" | "offline";

const INTERRUPTION_REASONS = [
  "网络中断，无法提交",
  "页面或浏览器异常关闭",
  "设备故障或断电",
  "误操作（提前关闭页面）",
  "其他（请在备注中说明）",
];

function backupKey(sittingId: number, stageIndex: number): string {
  return `clinpath.assessment.draft.${sittingId}.${stageIndex}`;
}

function readBackup(sittingId: number, stageIndex: number): string | null {
  try {
    return window.localStorage.getItem(backupKey(sittingId, stageIndex));
  } catch {
    return null;
  }
}

function writeBackup(sittingId: number, stageIndex: number, text: string): void {
  try {
    window.localStorage.setItem(backupKey(sittingId, stageIndex), text);
  } catch {
    // A blocked or full localStorage only costs the offline safety net.
  }
}

function clearBackup(sittingId: number, stageIndex: number): void {
  try {
    window.localStorage.removeItem(backupKey(sittingId, stageIndex));
  } catch {
    // ignore
  }
}

export function AssessmentExamClient({ sittingId }: { sittingId: number }) {
  const [view, setView] = useState<ExamView | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmStage, setConfirmStage] = useState(false);
  const [confirmPaper, setConfirmPaper] = useState(false);
  const [restoreOffer, setRestoreOffer] = useState<string | null>(null);
  const [online, setOnline] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const [interruptionReason, setInterruptionReason] = useState(INTERRUPTION_REASONS[0]);
  const [interruptionNote, setInterruptionNote] = useState("");
  const [interruptionDone, setInterruptionDone] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const savedTextRef = useRef<string>("");
  const skewMsRef = useRef(0);
  const stageIndex = view?.stage?.index ?? null;

  const applyView = useCallback((next: ExamView) => {
    setView(next);
    skewMsRef.current = Date.parse(next.server_time) - Date.now();
    setLastSavedAt(next.draft?.saved_at ?? null);
    const draftText = next.draft?.answer_text ?? "";
    setText(draftText);
    savedTextRef.current = draftText;
    // Restore from the server is the truth; the browser copy only fills a gap.
    if (next.draft?.answer_text) {
      setNotice(`已恢复服务器上的草稿（保存于 ${formatAssessmentMoment(next.draft.saved_at)}）。`);
      setSaveState("saved");
    } else if (next.stage) {
      const backup = readBackup(next.sitting_id, next.stage.index);
      setRestoreOffer(backup && backup.trim() ? backup : null);
      setSaveState("idle");
    }
  }, []);

  const load = useCallback(async () => {
    try {
      applyView(await getMyAssessment(sittingId));
      setLoadError(null);
    } catch (reason) {
      setLoadError(assessmentErrorMessage(reason, "无法加载这场考核，请检查网络后重试。"));
    }
  }, [applyView, sittingId]);

  useEffect(() => {
    void load();
  }, [load]);

  // One clock for the countdown: the page must not depend on the device's own clock.
  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const goOnline = () => {
      setOnline(true);
      setRetryTick((value) => value + 1);
    };
    const goOffline = () => setOnline(false);
    setOnline(navigator.onLine);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  const persistDraft = useCallback(
    async (value: string) => {
      if (stageIndex === null) return;
      setSaveState("saving");
      try {
        const result = await saveAssessmentDraft(sittingId, stageIndex, value);
        savedTextRef.current = value;
        setLastSavedAt(result.saved_at);
        setSaveState("saved");
      } catch (reason) {
        setSaveState("offline");
        setActionError(assessmentErrorMessage(reason, "草稿保存失败，将在网络恢复后自动重试。"));
        if (isNetworkFailure(reason)) window.setTimeout(() => setRetryTick((tick) => tick + 1), RETRY_DELAY_MS);
      }
    },
    [sittingId, stageIndex],
  );

  // Autosave: mirror to this browser at once, then push to the server after a pause.
  useEffect(() => {
    if (stageIndex === null || view?.status !== "in_progress") return;
    writeBackup(sittingId, stageIndex, text);
    if (text === savedTextRef.current) return;
    setSaveState((current) => (current === "saving" ? current : "dirty"));
    const timer = window.setTimeout(() => void persistDraft(text), AUTOSAVE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [text, stageIndex, view?.status, sittingId, persistDraft, retryTick]);

  const windowEndMs = view ? Date.parse(view.window_end) : Number.NaN;
  const remainingSeconds = Number.isNaN(windowEndMs) ? Number.POSITIVE_INFINITY : (windowEndMs - (nowMs + skewMsRef.current)) / 1000;
  const windowClosed = remainingSeconds <= 0;
  const live = view?.status === "in_progress" || view?.status === "ready_to_submit";

  async function withBusy(action: () => Promise<void>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  async function handleStart() {
    await withBusy(async () => {
      try {
        const next = await startAssessment(sittingId);
        setNotice(null);
        applyView(next);
      } catch (reason) {
        setActionError(assessmentErrorMessage(reason, "无法开始考核，请稍后重试。"));
      }
    });
  }

  async function handleSubmitStage() {
    if (!view?.stage || stageIndex === null) return;
    const trimmed = text.trim();
    if (!trimmed) {
      setActionError("请先填写本阶段的作答内容。");
      return;
    }
    await withBusy(async () => {
      try {
        await submitAssessmentStage(sittingId, stageIndex, trimmed);
        clearBackup(sittingId, stageIndex);
        setConfirmStage(false);
        setRestoreOffer(null);
        setNotice(`第 ${stageIndex + 1} 阶段已提交，答案不能再修改。`);
        applyView(await getMyAssessment(sittingId));
      } catch (reason) {
        setActionError(assessmentErrorMessage(reason, "阶段提交失败，请重试。"));
      }
    });
  }

  async function handleSubmitPaper() {
    await withBusy(async () => {
      try {
        await submitAssessment(sittingId);
        setConfirmPaper(false);
        setNotice(null);
        applyView(await getMyAssessment(sittingId));
      } catch (reason) {
        setActionError(assessmentErrorMessage(reason, "整卷提交失败，请重试；如反复失败请联系研究管理员。"));
      }
    });
  }

  async function handleReportInterruption() {
    const note = interruptionNote.trim();
    const reason = note
      ? `${interruptionReason}：${note}`.slice(0, 500)
      : interruptionReason;
    await withBusy(async () => {
      try {
        await reportAssessmentInterruption(sittingId, reason);
        setInterruptionDone(true);
        setInterruptionNote("");
      } catch (reason2) {
        setActionError(assessmentErrorMessage(reason2, "中断报告未能记录，请稍后重试。"));
      }
    });
  }

  const saveLabel = useMemo(() => {
    if (saveState === "saving") return "正在保存草稿…";
    if (saveState === "offline") return online ? "草稿尚未保存到服务器，正在重试…" : "网络已断开：草稿暂存在本机，恢复网络后自动上传。";
    if (saveState === "saved") return `草稿已保存到服务器${lastSavedAt ? `（${formatAssessmentMoment(lastSavedAt)}）` : ""}`;
    if (saveState === "dirty") return "有未保存的修改…";
    return "草稿会自动保存在服务器上。";
  }, [saveState, online, lastSavedAt]);

  if (loadError) {
    return (
      <div className="space-y-4">
        <Feedback error={loadError} />
        <Link href="/student/assessments" className="inline-flex rounded-md border border-slate-300 px-4 py-2">
          返回我的独立考核
        </Link>
      </div>
    );
  }

  if (!view) {
    return (
      <p className="text-sm text-slate-500" role="status">
        正在加载考核…
      </p>
    );
  }

  if (view.status === "submitted") {
    return (
      <div className="space-y-6" data-testid="assessment-submitted">
        <Card title="答卷已提交" description="本次独立考核已经完成。">
          <p className="text-sm text-slate-700">
            提交时间：{formatAssessmentMoment(view.submitted_at)} · 共提交 {view.completed} / {STAGE_TOTAL} 个阶段。
          </p>
          <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
            按照考核规则，本页面不显示正确答案、参考诊断，也不显示任何评分或成绩反馈。
            阅卷由两位教师独立盲评完成，超过阈值的分歧由第三位教师裁决。
          </p>
          <div className="mt-4">
            <Link
              href="/student/assessments"
              className="inline-flex rounded-md bg-clinic px-4 py-2 text-sm text-white"
            >
              返回我的独立考核
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  if (view.status === "expired") {
    return (
      <div className="space-y-4" data-testid="assessment-expired">
        <Feedback error="考核窗口已经关闭，本场不能再提交。" />
        <p className="text-sm text-slate-700">
          已提交 {view.completed} / {STAGE_TOTAL} 个阶段。如因断网、设备故障等原因未能完成，请联系研究管理员登记补考。
        </p>
        <Link href="/student/assessments" className="inline-flex rounded-md border border-slate-300 px-4 py-2">
          返回我的独立考核
        </Link>
      </div>
    );
  }

  if (view.can_start) {
    return (
      <div className="space-y-6" data-testid="assessment-instructions">
        <Card title="考试说明" description="开始之前请确认以下内容。">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            <li>{view.instructions}</li>
          </ul>
          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">阶段数</dt>
              <dd className="font-medium text-ink">{view.total_stages} 个阶段，按顺序释放</dd>
            </div>
            <div>
              <dt className="text-slate-500">开放窗口（本机时间）</dt>
              <dd className="font-medium text-ink">
                {formatAssessmentMoment(view.window_start)} 至 {formatAssessmentMoment(view.window_end)}
              </dd>
            </div>
          </dl>
          <p className="mt-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            本考核不提供 AI 追问、不提供形成性训练反馈、不更新学习画像与推荐。提交后的答案不能修改。
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={() => void handleStart()} disabled={busy}>
              {busy ? "正在开始…" : "开始考核"}
            </Button>
            <Link href="/student/assessments" className="rounded-md border border-slate-300 px-3 py-2 text-sm">
              稍后再考
            </Link>
          </div>
          {actionError ? <p className="mt-3 text-sm text-alert">{actionError}</p> : null}
        </Card>
      </div>
    );
  }

  const currentStage = view.status === "in_progress" ? view.stage ?? null : null;

  return (
    <div className="space-y-6" data-testid="assessment-exam">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold tracking-[0.22em] text-clinic">独立在线考核</p>
          <h1 className="mt-1 text-2xl font-semibold text-ink">
            已完成 {Math.min(view.completed, STAGE_TOTAL)} / {STAGE_TOTAL} 阶段
          </h1>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">距离本场关闭</p>
          <p
            data-testid="assessment-countdown"
            className={`text-2xl font-semibold ${windowClosed ? "text-alert" : "text-ink"}`}
          >
            {Number.isFinite(remainingSeconds) ? formatAssessmentClock(remainingSeconds) : "—"}
          </p>
          <p className="text-xs text-slate-500">关闭时间 {formatAssessmentMoment(view.window_end)}</p>
        </div>
      </section>

      <Feedback error={actionError} message={notice} />
      {!online ? (
        <p role="status" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          网络连接已断开：你输入的内容会继续保存在本机，网络恢复后会自动上传。请勿关闭页面。
        </p>
      ) : null}
      {windowClosed ? (
        <p role="alert" className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-alert">
          考核窗口已经关闭：现在无法再提交答案。请在本页报告中断，由研究管理员登记处理。
        </p>
      ) : null}

      {view.history?.length ? (
        <Card
          title="已提交的阶段（只读）"
          description="已提交的答案不能修改；这里可以回看你自己写过的内容。"
          actions={
            <Button tone="secondary" onClick={() => setShowHistory((value) => !value)}>
              {showHistory ? "收起" : `展开（${view.history.length}）`}
            </Button>
          }
        >
          {showHistory ? (
            <ol className="space-y-3">
              {view.history.map((item) => (
                <li key={item.index}>
                  <StageBlock stage={item} index={item.index} total={STAGE_TOTAL} answer={item.answer_text} />
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-slate-500">共 {view.history.length} 个阶段已提交。</p>
          )}
        </Card>
      ) : null}

      {view.status === "ready_to_submit" ? (
        <Card title="五个阶段已全部提交" description="确认后提交整份答卷，提交后不能修改。">
          <p className="text-sm text-slate-700">
            你已经完成全部 {STAGE_TOTAL} 个阶段的作答。提交整份答卷后，本次独立考核结束，页面只会显示提交成功，
            不显示正确答案，也不显示分数。
          </p>
          {confirmPaper ? (
            <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4">
              <p className="text-sm text-amber-900">确认提交整份答卷？提交后无法撤回、无法修改任何阶段。</p>
              <div className="mt-3 flex flex-wrap gap-3">
                <Button onClick={() => void handleSubmitPaper()} disabled={busy || windowClosed}>
                  {busy ? "正在提交…" : "确认提交整份答卷"}
                </Button>
                <Button tone="secondary" onClick={() => setConfirmPaper(false)} disabled={busy}>
                  我再检查一下
                </Button>
              </div>
            </div>
          ) : (
            <div className="mt-4">
              <Button onClick={() => setConfirmPaper(true)} disabled={windowClosed}>
                提交整份答卷
              </Button>
            </div>
          )}
        </Card>
      ) : null}

      {currentStage ? (
        <Card
          title="当前阶段"
          description="提交本阶段后才会显示下一阶段新增的临床资料。"
          actions={<Pill tone="warn">{saveLabel}</Pill>}
        >
          <StageBlock stage={currentStage} index={currentStage.index} total={STAGE_TOTAL} />

          {restoreOffer ? (
            <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <p>本机保存有一份未上传到服务器的草稿（可能是上次断网时留下的）。</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  tone="secondary"
                  onClick={() => {
                    setText(restoreOffer);
                    setSaveState("dirty");
                    setRestoreOffer(null);
                    setNotice("已恢复本机草稿，请检查后按需修改。");
                  }}
                >
                  恢复本机草稿
                </Button>
                <Button
                  tone="secondary"
                  onClick={() => {
                    clearBackup(sittingId, currentStage.index);
                    setRestoreOffer(null);
                  }}
                >
                  丢弃
                </Button>
              </div>
            </div>
          ) : null}

            <label className="mt-4 block text-sm">
              <span className="font-medium text-ink">本阶段作答</span>
              <span className="ml-2 text-xs text-slate-500">请写出你的临床推理过程，不要写入姓名、学号等可识别信息。</span>
              <textarea
                aria-label="本阶段作答"
                rows={10}
                value={text}
                disabled={windowClosed || busy}
                onChange={(event) => setText(event.target.value)}
                className="mt-2 w-full rounded-md border border-slate-300 p-3 text-sm"
                placeholder="例如：关键信息 → 初步诊断及依据 → 鉴别诊断 → 进一步检查 → 处理原则"
              />
            </label>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button
                tone="secondary"
                disabled={busy || windowClosed || text === savedTextRef.current}
                onClick={() => void persistDraft(text)}
              >
                立即保存草稿
              </Button>
              <span className="text-xs text-slate-500">{saveLabel}</span>
            </div>

            {confirmStage ? (
              <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4">
                <p className="text-sm font-medium text-amber-900">
                  确认提交第 {currentStage.index + 1} 阶段的作答？提交后不能修改，并且会立即释放下一阶段的临床资料。
                </p>
                <p className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-white p-3 text-sm text-slate-700">
                  {text.trim()}
                </p>
                <div className="mt-3 flex flex-wrap gap-3">
                  <Button onClick={() => void handleSubmitStage()} disabled={busy || windowClosed}>
                    {busy ? "正在提交…" : "确认提交并查看下一阶段"}
                  </Button>
                  <Button tone="secondary" onClick={() => setConfirmStage(false)} disabled={busy}>
                    返回修改
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-4">
                <Button onClick={() => setConfirmStage(true)} disabled={busy || windowClosed || !text.trim()}>
                  保存并提交本阶段
                </Button>
              </div>
            )}
          </Card>
      ) : null}

      {live ? (
        <Card
          title="报告本次中断"
          description="如果本次作答过程中发生断网、设备故障或页面异常关闭，请在这里如实报告，记录会进入研究管理审计日志。"
        >
          {interruptionDone ? (
            <p className="text-sm text-clinic">已记录本次中断报告，研究管理员可以在审计日志中看到。</p>
          ) : (
            <>
              <label className="block text-sm">
                <span className="text-slate-600">中断原因</span>
                <select
                  aria-label="中断原因"
                  value={interruptionReason}
                  onChange={(event) => setInterruptionReason(event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2"
                >
                  {INTERRUPTION_REASONS.map((reason) => (
                    <option key={reason} value={reason}>
                      {reason}
                    </option>
                  ))}
                </select>
              </label>
              <label className="mt-3 block text-sm">
                <span className="text-slate-600">补充说明（可选）</span>
                <textarea
                  aria-label="中断补充说明"
                  rows={2}
                  value={interruptionNote}
                  onChange={(event) => setInterruptionNote(event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2"
                  placeholder="例如：11:05 左右校园网中断约 3 分钟，之后已恢复"
                />
              </label>
              <div className="mt-3">
                <Button tone="secondary" onClick={() => void handleReportInterruption()} disabled={busy}>
                  提交中断报告
                </Button>
              </div>
            </>
          )}
        </Card>
      ) : null}
    </div>
  );
}
