"use client";

/**
 * R3.4/R4.6: the coded research dataset, agreement, and frozen versions.
 *
 * Exports are pseudonymous: rows carry the study code only, and the identity map
 * is a separate audited call. A lock stores the snapshot with its SHA-256, so a
 * version can be re-read byte-for-byte later.
 */
import { useCallback, useEffect, useState } from "react";

import {
  Button,
  Card,
  EmptyHint,
  Feedback,
  Moment,
  Pill,
  SyntheticNotice,
} from "@/components/assessment/AssessmentUi";
import {
  assessmentErrorMessage,
  dataOriginLabel,
  getRaterAgreement,
  listAssessmentDatasetLocks,
  lockAssessmentDataset,
  missingnessLabel,
  researchAssessmentExport,
  scoringProvenanceLabel,
  type AgreementPayload,
  type DatasetLockRow,
  type ExportPayload,
} from "@/lib/assessmentApi";

import { DATA_ORIGIN_OPTIONS } from "./adminShared";

type IccShape = {
  status?: string;
  reason?: string;
  method?: string;
  n_subjects?: number;
  n_raters?: number;
  n_dropped_incomplete?: number;
  icc_2_1?: number | null;
  icc_2_k?: number | null;
  ci_2_1?: [number, number] | null;
  ci_2_k?: [number, number] | null;
  ci_level?: number;
  note?: string | null;
  mean_abs_difference?: number | null;
};

function downloadJson(name: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export function DatasetPanel() {
  const [dataOrigin, setDataOrigin] = useState("pilot_test");
  const [exported, setExported] = useState<ExportPayload | null>(null);
  const [agreement, setAgreement] = useState<AgreementPayload | null>(null);
  const [locks, setLocks] = useState<DatasetLockRow[]>([]);
  const [version, setVersion] = useState("");
  const [note, setNote] = useState("");
  const [allowIncomplete, setAllowIncomplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadLocks = useCallback(async () => {
    try {
      setLocks(await listAssessmentDatasetLocks());
    } catch (why) {
      setError(assessmentErrorMessage(why));
    }
  }, []);

  useEffect(() => {
    void loadLocks();
  }, [loadLocks]);

  async function loadExport() {
    setBusy(true);
    setError(null);
    try {
      setExported(await researchAssessmentExport(dataOrigin));
    } catch (why) {
      setExported(null);
      setError(assessmentErrorMessage(why));
    } finally {
      setBusy(false);
    }
  }

  async function loadAgreement() {
    setBusy(true);
    setError(null);
    try {
      setAgreement(await getRaterAgreement(dataOrigin));
    } catch (why) {
      setAgreement(null);
      setError(assessmentErrorMessage(why));
    } finally {
      setBusy(false);
    }
  }

  async function lock() {
    if (version.trim().length < 3) {
      setError("数据集版本号至少 3 个字符（例如 PILOT-2026-11-01-v1）。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await lockAssessmentDataset({
        dataset_version: version.trim(),
        data_origin: dataOrigin,
        ...(note.trim() ? { note: note.trim() } : {}),
        allow_incomplete: allowIncomplete,
      });
      setMessage(
        `数据集 ${result.dataset_version} 已冻结：${result.records} 条记录，SHA-256 ${result.sha256.slice(0, 16)}…。` +
          "此后同一版本可以按原样重现。",
      );
      setVersion("");
      setNote("");
      await loadLocks();
    } catch (why) {
      setError(assessmentErrorMessage(why));
    } finally {
      setBusy(false);
    }
  }

  const icc = (agreement?.icc ?? null) as IccShape | null;

  return (
    <div className="space-y-4">
      <Feedback error={error} message={message} />

      <Card
        title="数据来源"
        description="不同来源的数据永不混合。测试/合成数据不能作为真实研究结果报告。"
      >
        <label className="text-sm">
          <span className="text-slate-600">数据来源</span>
          <select
            aria-label="数据集数据来源"
            value={dataOrigin}
            onChange={(event) => {
              setDataOrigin(event.target.value);
              setExported(null);
              setAgreement(null);
            }}
            className="mt-1 block w-full max-w-md rounded-md border border-slate-300 p-2"
          >
            {DATA_ORIGIN_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <p className="mt-2 text-sm text-slate-600">当前：{dataOriginLabel(dataOrigin)}</p>
        <SyntheticNotice dataOrigin={dataOrigin} />
      </Card>

      <Card
        title="研究导出（编码数据）"
        description="只含研究编码，不含姓名或学号；身份映射需单独、留痕地读取。"
        actions={
          <>
            <Button onClick={() => void loadExport()} disabled={busy}>
              生成工作数据集
            </Button>
            <Button
              tone="secondary"
              onClick={() => exported && downloadJson(`assessment-export-${dataOrigin}.json`, exported)}
              disabled={!exported}
            >
              下载 JSON
            </Button>
          </>
        }
      >
        {exported ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone="warn">{exported.dataset_status}</Pill>
              <span className="text-sm text-slate-600">共 {exported.records.length} 条记录</span>
            </div>
            {exported.records.length === 0 ? (
              <EmptyHint>该数据来源下没有考试记录。</EmptyHint>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[1080px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500">
                    <tr>
                      <th className="px-3 py-2">研究编码</th>
                      <th className="px-3 py-2">批次 / 组别</th>
                      <th className="px-3 py-2">时点 / 题本</th>
                      <th className="px-3 py-2">评分者 1</th>
                      <th className="px-3 py-2">评分者 2</th>
                      <th className="px-3 py-2">绝对差</th>
                      <th className="px-3 py-2">裁决</th>
                      <th className="px-3 py-2">最终成绩</th>
                      <th className="px-3 py-2">完整性</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exported.records.map((row, index) => (
                      <tr key={`${row.study_student_code}-${row.timepoint}-${index}`} className="border-b border-slate-100">
                        <td className="px-3 py-2 font-mono text-xs">{row.study_student_code ?? "—"}</td>
                        <td className="px-3 py-2">
                          {row.cohort_id} · {row.study_group}
                          {row.randomization_mode ? (
                            <p className="text-xs text-slate-500">{row.randomization_mode}</p>
                          ) : null}
                        </td>
                        <td className="px-3 py-2">
                          {row.timepoint} · {row.assessment_form_code} v{row.assessment_form_version}
                          {row.form_order ? <p className="text-xs text-slate-500">顺序 {row.form_order}</p> : null}
                        </td>
                        <td className="px-3 py-2">{row.blinded_rater_1_score ?? "—"}</td>
                        <td className="px-3 py-2">{row.blinded_rater_2_score ?? "—"}</td>
                        <td className="px-3 py-2">{row.absolute_total_diff ?? "—"}</td>
                        <td className="px-3 py-2">{row.adjudicated_score ?? "—"}</td>
                        <td className="px-3 py-2">
                          {row.final_score ?? "—"}
                          <p className="text-xs text-slate-500">{scoringProvenanceLabel(row.scoring_provenance)}</p>
                        </td>
                        <td className="px-3 py-2 text-xs">{missingnessLabel(row.missingness)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <EmptyHint>点击「生成工作数据集」查看当前编码数据。</EmptyHint>
        )}
      </Card>

      <Card
        title="评分者一致性"
        description="ICC(2,1) 与 ICC(2,k)，仅使用两位评分者都完成评分的答卷。样本不足时如实报告，不伪造可靠性指标。"
        actions={
          <Button tone="secondary" onClick={() => void loadAgreement()} disabled={busy}>
            计算一致性
          </Button>
        }
      >
        {!agreement ? (
          <EmptyHint>尚未计算。</EmptyHint>
        ) : (
          <>
            <p className="text-sm text-slate-600">有效配对：{agreement.pairs.length} 份答卷</p>
            {icc ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">状态</p>
                  <p className="font-semibold text-ink">
                    {icc.status === "ok" ? "可计算" : `不可计算（${icc.reason ?? icc.status}）`}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">ICC(2,1)</p>
                  <p className="font-semibold text-ink">
                    {icc.icc_2_1 === null || icc.icc_2_1 === undefined ? "—" : icc.icc_2_1.toFixed(3)}
                  </p>
                  <p className="text-xs text-slate-500">
                    95% CI {icc.ci_2_1 ? `${icc.ci_2_1[0].toFixed(3)} – ${icc.ci_2_1[1].toFixed(3)}` : "不可用"}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">ICC(2,k)</p>
                  <p className="font-semibold text-ink">
                    {icc.icc_2_k === null || icc.icc_2_k === undefined ? "—" : icc.icc_2_k.toFixed(3)}
                  </p>
                  <p className="text-xs text-slate-500">
                    95% CI {icc.ci_2_k ? `${icc.ci_2_k[0].toFixed(3)} – ${icc.ci_2_k[1].toFixed(3)}` : "不可用"}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">平均绝对差</p>
                  <p className="font-semibold text-ink">
                    {icc.mean_abs_difference === null || icc.mean_abs_difference === undefined
                      ? "—"
                      : icc.mean_abs_difference.toFixed(2)}
                  </p>
                  <p className="text-xs text-slate-500">完整样本 {icc.n_subjects ?? 0} 例</p>
                </div>
              </div>
            ) : null}
            {icc?.method ? <p className="mt-2 text-xs text-slate-500">方法：{icc.method}</p> : null}
            {icc?.note ? <p className="mt-1 text-xs text-amber-800">{icc.note}</p> : null}
            {agreement.pairs.length ? (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500">
                    <tr>
                      <th className="px-3 py-2">研究编码</th>
                      <th className="px-3 py-2">时点</th>
                      <th className="px-3 py-2">评分者 1</th>
                      <th className="px-3 py-2">评分者 2</th>
                      <th className="px-3 py-2">绝对差</th>
                      <th className="px-3 py-2">最终成绩</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agreement.pairs.map((row, index) => (
                      <tr key={index} className="border-b border-slate-100">
                        <td className="px-3 py-2 font-mono text-xs">{row.study_student_code ?? "—"}</td>
                        <td className="px-3 py-2">{row.timepoint}</td>
                        <td className="px-3 py-2">{row.blinded_rater_1_score ?? "—"}</td>
                        <td className="px-3 py-2">{row.blinded_rater_2_score ?? "—"}</td>
                        <td className="px-3 py-2">{row.absolute_total_diff ?? "—"}</td>
                        <td className="px-3 py-2">
                          {row.final_score ?? "—"} · {scoringProvenanceLabel(row.scoring_provenance ?? null)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        )}
      </Card>

      <Card title="冻结数据集版本" description="冻结后保存快照与 SHA-256；同一版本可逐字节重现。">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">
            <span className="text-slate-600">数据集版本号</span>
            <input
              aria-label="数据集版本号"
              value={version}
              onChange={(event) => setVersion(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
              placeholder="PILOT-2026-11-01-v1"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="text-slate-600">备注（可选）</span>
            <input
              aria-label="数据集备注"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            />
          </label>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={allowIncomplete}
            onChange={(event) => setAllowIncomplete(event.target.checked)}
          />
          <span>允许包含尚未锁定最终成绩的记录（缺失会在数据集中如实标注）</span>
        </label>
        <div className="mt-3">
          <Button onClick={() => void lock()} disabled={busy}>
            冻结当前数据为 {dataOriginLabel(dataOrigin)}
          </Button>
        </div>

        <div className="mt-5">
          <h3 className="font-semibold text-ink">已冻结版本</h3>
          {locks.length === 0 ? (
            <EmptyHint>还没有冻结的数据集版本。</EmptyHint>
          ) : (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2">版本</th>
                    <th className="px-3 py-2">数据来源</th>
                    <th className="px-3 py-2">记录数</th>
                    <th className="px-3 py-2">SHA-256</th>
                    <th className="px-3 py-2">冻结时间</th>
                  </tr>
                </thead>
                <tbody>
                  {locks.map((row) => (
                    <tr key={row.dataset_version} className="border-b border-slate-100">
                      <td className="px-3 py-2 font-mono text-xs">{row.dataset_version}</td>
                      <td className="px-3 py-2">{dataOriginLabel(row.data_origin)}</td>
                      <td className="px-3 py-2">{row.records}</td>
                      <td className="px-3 py-2 font-mono text-xs">{row.sha256.slice(0, 16)}…</td>
                      <td className="px-3 py-2 text-slate-600">
                        <Moment value={row.locked_at} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
