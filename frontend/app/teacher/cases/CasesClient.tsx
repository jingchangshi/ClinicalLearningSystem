"use client";

import { useEffect, useState } from "react";
import { Edit, Plus, Trash2 } from "lucide-react";

import {
  CaseDetail,
  teacherCreateCase,
  teacherDeleteCase,
  teacherListCases,
  teacherUpdateCase,
} from "@/lib/api";

type CaseForm = Omit<CaseDetail, "id" | "learning_objectives" | "differential_diagnosis" | "rubric"> & {
  learning_objectives: string;
  differential_diagnosis: string;
  rubric: string;
};

const emptyForm: CaseForm = {
  title: "",
  disease_category: "风湿免疫",
  difficulty: "基础",
  learning_objectives: "",
  chief_complaint: "",
  history: "",
  physical_exam: "",
  lab_results: "",
  imaging: "",
  standard_diagnosis: "",
  differential_diagnosis: "",
  treatment_plan: "",
  rubric: "",
};

export function CasesClient() {
  const [cases, setCases] = useState<CaseDetail[]>([]);
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<CaseForm>(emptyForm);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    const items = await teacherListCases();
    setCases(items);
    setSelected(items[0] ?? null);
  }

  function editCase(item: CaseDetail) {
    setEditingId(item.id);
    setForm({
      ...item,
      learning_objectives: item.learning_objectives.join("\n"),
      differential_diagnosis: item.differential_diagnosis.join("\n"),
      rubric: JSON.stringify(item.rubric, null, 2),
    });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const payload = toPayload(form);
      if (editingId) {
        await teacherUpdateCase(editingId, payload);
      } else {
        await teacherCreateCase(payload);
      }
      setEditingId(null);
      setForm(emptyForm);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(caseId: number) {
    setBusy(true);
    try {
      await teacherDeleteCase(caseId);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
        <h1 className="text-xl font-semibold">病例管理</h1>
        <div className="space-y-3">
          {cases.map((item) => (
            <div key={item.id} className="rounded-md border border-slate-200 p-3">
              <button onClick={() => setSelected(item)} className="block w-full text-left">
                <div className="font-medium">{item.title}</div>
                <div className="mt-1 text-sm text-slate-500">
                  {item.disease_category} · {item.difficulty}
                </div>
                <div className="mt-1 text-sm text-slate-600">{item.chief_complaint}</div>
              </button>
              <div className="mt-3 flex gap-2">
                <button onClick={() => editCase(item)} className="inline-flex items-center gap-1 rounded-md border px-3 py-1 text-sm">
                  <Edit className="h-3.5 w-3.5" />
                  编辑
                </button>
                <button
                  onClick={() => handleDelete(item.id)}
                  disabled={busy}
                  className="inline-flex items-center gap-1 rounded-md border border-red-200 px-3 py-1 text-sm text-alert"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>

        {selected ? (
          <div className="rounded-md bg-slate-50 p-4">
            <h2 className="font-semibold">病例详情</h2>
            <Detail label="标准诊断" value={selected.standard_diagnosis} />
            <Detail label="鉴别诊断" value={selected.differential_diagnosis.join("、")} />
            <Detail label="治疗方案" value={selected.treatment_plan} />
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">{editingId ? "编辑病例" : "新增病例"}</h2>
        <form onSubmit={handleSubmit} className="mt-4 grid gap-3">
          <TextInput label="病例标题" value={form.title} onChange={(value) => setForm({ ...form, title: value })} />
          <TextInput label="疾病类别" value={form.disease_category} onChange={(value) => setForm({ ...form, disease_category: value })} />
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
          <TextArea label="学习目标，每行一项" value={form.learning_objectives} onChange={(value) => setForm({ ...form, learning_objectives: value })} />
          <TextArea label="主诉" value={form.chief_complaint} onChange={(value) => setForm({ ...form, chief_complaint: value })} />
          <TextArea label="现病史" value={form.history} onChange={(value) => setForm({ ...form, history: value })} />
          <TextArea label="体格检查" value={form.physical_exam} onChange={(value) => setForm({ ...form, physical_exam: value })} />
          <TextArea label="实验室检查" value={form.lab_results} onChange={(value) => setForm({ ...form, lab_results: value })} />
          <TextArea label="影像资料" value={form.imaging} onChange={(value) => setForm({ ...form, imaging: value })} />
          <TextArea label="标准诊断" value={form.standard_diagnosis} onChange={(value) => setForm({ ...form, standard_diagnosis: value })} />
          <TextArea label="鉴别诊断，每行一项" value={form.differential_diagnosis} onChange={(value) => setForm({ ...form, differential_diagnosis: value })} />
          <TextArea label="治疗方案" value={form.treatment_plan} onChange={(value) => setForm({ ...form, treatment_plan: value })} />
          <TextArea label="评分Rubric，JSON格式" value={form.rubric} onChange={(value) => setForm({ ...form, rubric: value })} />
          <div className="flex gap-2">
            <button disabled={busy} className="inline-flex items-center gap-2 rounded-md bg-clinic px-4 py-2 text-white disabled:bg-slate-300">
              <Plus className="h-4 w-4" />
              {editingId ? "保存修改" : "新增病例"}
            </button>
            {editingId ? (
              <button
                type="button"
                onClick={() => {
                  setEditingId(null);
                  setForm(emptyForm);
                }}
                className="rounded-md border border-slate-300 px-4 py-2"
              >
                取消
              </button>
            ) : null}
          </div>
        </form>
      </section>
    </div>
  );
}

function toPayload(form: CaseForm): Omit<CaseDetail, "id"> {
  return {
    ...form,
    learning_objectives: lines(form.learning_objectives),
    differential_diagnosis: lines(form.differential_diagnosis),
    rubric: parseRubric(form.rubric),
  };
}

function lines(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function parseRubric(value: string) {
  if (!value.trim()) return {};
  try {
    return JSON.parse(value) as Record<string, string>;
  } catch {
    return { raw: value };
  }
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3">
      <div className="text-sm font-medium">{label}</div>
      <p className="mt-1 text-sm text-slate-600">{value}</p>
    </div>
  );
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
        className="mt-1 min-h-20 w-full rounded-md border border-slate-300 p-2"
        required
      />
    </label>
  );
}
