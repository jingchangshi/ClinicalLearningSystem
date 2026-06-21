"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, Wand2 } from "lucide-react";

import { approveGeneratedCase, CaseDetail, generateTeacherCase } from "@/lib/api";

type GeneratorForm = {
  disease_category: string;
  difficulty: string;
  teaching_goal: string;
  required_elements: string;
  target_abilities: string;
};

const defaultForm: GeneratorForm = {
  disease_category: "系统性红斑狼疮",
  difficulty: "中等",
  teaching_goal: "训练学生识别疾病活动、器官受累和治疗监测计划",
  required_elements: "发热\n皮疹\n关节痛\n尿蛋白异常",
  target_abilities: "医学知识\n关键信息提取\n鉴别诊断\n临床决策\n循证医学",
};

export function CaseGeneratorClient() {
  const [form, setForm] = useState<GeneratorForm>(defaultForm);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [draftJson, setDraftJson] = useState("");
  const [approvedCase, setApprovedCase] = useState<CaseDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setApprovedCase(null);
    try {
      const response = await generateTeacherCase({
        disease_category: form.disease_category,
        difficulty: form.difficulty,
        teaching_goal: form.teaching_goal,
        required_elements: lines(form.required_elements),
        target_abilities: lines(form.target_abilities),
      });
      setDraftId(response.draft_id);
      setDraftJson(JSON.stringify(response.generated_payload, null, 2));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "病例生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    if (!draftId) return;
    setBusy(true);
    setError(null);
    try {
      const payload = JSON.parse(draftJson) as Omit<CaseDetail, "id">;
      const response = await approveGeneratedCase(draftId, payload);
      setApprovedCase(response.case);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "批准病例失败，请检查 JSON 格式和必填字段");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">教师端</p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">AI 病例生成器</h1>
        <form onSubmit={handleGenerate} className="mt-5 grid gap-4">
          <TextInput
            label="疾病类别"
            value={form.disease_category}
            onChange={(value) => setForm({ ...form, disease_category: value })}
          />
          <label className="block text-sm">
            <span className="font-medium">难度</span>
            <select
              value={form.difficulty}
              onChange={(event) => setForm({ ...form, difficulty: event.target.value })}
              className="mt-1 w-full rounded-md border border-slate-300 p-2"
            >
              <option>基础</option>
              <option>中等</option>
              <option>进阶</option>
              <option>高阶</option>
            </select>
          </label>
          <TextArea
            label="教学目标"
            value={form.teaching_goal}
            onChange={(value) => setForm({ ...form, teaching_goal: value })}
          />
          <TextArea
            label="必须包含元素，每行一项"
            value={form.required_elements}
            onChange={(value) => setForm({ ...form, required_elements: value })}
          />
          <TextArea
            label="目标能力维度，每行一项"
            value={form.target_abilities}
            onChange={(value) => setForm({ ...form, target_abilities: value })}
          />
          <button
            disabled={busy}
            className="inline-flex items-center justify-center gap-2 rounded-md bg-clinic px-4 py-2 text-white disabled:bg-slate-300"
          >
            <Wand2 className="h-4 w-4" />
            生成病例草稿
          </button>
        </form>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">病例草稿 JSON</h2>
            <p className="mt-1 text-sm text-slate-500">可直接编辑后批准入库。</p>
          </div>
          <button
            onClick={handleApprove}
            disabled={busy || !draftId || !draftJson.trim()}
            className="inline-flex items-center gap-2 rounded-md bg-ink px-4 py-2 text-white disabled:bg-slate-300"
          >
            <CheckCircle2 className="h-4 w-4" />
            批准入库
          </button>
        </div>
        <textarea
          value={draftJson}
          onChange={(event) => setDraftJson(event.target.value)}
          className="mt-4 h-[620px] w-full rounded-md border border-slate-300 p-3 font-mono text-sm outline-none focus:border-clinic focus:ring-2 focus:ring-clinic-soft"
          placeholder="生成后将在此显示病例 JSON"
        />
        {error ? <p className="mt-3 text-sm text-alert">{error}</p> : null}
        {approvedCase ? (
          <div className="mt-4 rounded-md bg-clinic-soft p-4 text-sm text-teal-950">
            <div className="font-medium">已写入病例库：{approvedCase.title}</div>
            <Link href="/teacher/cases" className="mt-2 inline-flex text-clinic hover:underline">
              查看病例管理
            </Link>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function lines(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm">
      <span className="font-medium">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-slate-300 p-2"
        required
      />
    </label>
  );
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm">
      <span className="font-medium">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 min-h-24 w-full rounded-md border border-slate-300 p-2"
        required
      />
    </label>
  );
}
