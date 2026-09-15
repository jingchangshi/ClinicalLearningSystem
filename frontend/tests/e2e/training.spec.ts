import { expect, test } from "@playwright/test";
import type { Browser, Page } from "@playwright/test";

test.skip(!process.env.E2E_RUN_MUTATING, "Set E2E_RUN_MUTATING=1 to run a training flow against a disposable deployment.");

// Production real-AI acceptance: with this gate on, a rule fallback is a failure,
// not an acceptable alternative.  See docs/ARCH.md §14.3.
const EXPECT_REAL_AI = Boolean(process.env.E2E_EXPECT_REAL_AI);

test("SP encounter works while hidden history stays hidden", async ({ page }) => {
  await login(page);

  // Hidden answers must not be readable through the API the page uses.
  const casePayload = await page.evaluate(async () => {
    const response = await fetch("/api/sp-cases/1", { credentials: "include" });
    return await response.json();
  });
  expect(casePayload.hidden_history).toBeUndefined();
  expect(casePayload.scoring_rubric).toBeUndefined();

  await page.goto("/student/sp/1");
  await expect(page.getByText("问诊对话")).toBeVisible();
  await page.getByPlaceholder("输入问诊问题...").fill("发热持续多久了？有没有关节疼痛？");
  await page.getByRole("button", { name: /发送|提问/ }).click();

  // The simulated patient must still answer from the hidden history.
  await expect(page.locator("text=问诊对话")).toBeVisible();
  await expect
    .poll(async () => page.locator("div.bg-white.text-slate-700").count(), { timeout: 20_000 })
    .toBeGreaterThan(1);
});

test("knowledge quiz still grades without exposing answer keys", async ({ page }) => {
  await login(page);

  const unit = await page.evaluate(async () => {
    const response = await fetch("/api/knowledge/1", { credentials: "include" });
    return await response.json();
  });
  expect(unit.quiz_items.length).toBeGreaterThan(0);
  expect(unit.quiz_items[0].answer_keywords).toBeUndefined();

  await page.goto("/student/knowledge/1");
  await expect(page.getByRole("heading", { name: "知识测验" })).toBeVisible();
  await page.locator("textarea").first().fill("抗dsDNA升高与补体下降提示疾病活动。");
  await page.getByRole("button", { name: "提交测验" }).click();
  await expect(page.getByText(/测验得分/)).toBeVisible({ timeout: 20_000 });
});

const STEPS: { label: string; text: string }[] = [
  { label: "关键信息提取", text: "关键信息：发热、皮疹、ANA阳性、蛋白尿，需评估器官受累。" },
  { label: "初步诊断及依据", text: "初步诊断：考虑系统性红斑狼疮，依据症状、抗体和器官受累。" },
  { label: "鉴别诊断", text: "鉴别诊断：需排除感染、AOSD、HLH、淋巴瘤和其他结缔组织病。" },
  { label: "进一步检查", text: "进一步检查：补体、抗dsDNA、尿蛋白定量、肺功能评估活动度。" },
  { label: "治疗方案", text: "治疗：激素联合免疫抑制剂，治疗前感染筛查，随访监测不良反应。" },
];

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(process.env.E2E_STUDENT_USERNAME ?? "student1");
  await page.getByLabel("密码").fill(process.env.E2E_STUDENT_PASSWORD ?? "student123");
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/student\/dashboard$/);
}

async function sessionIdFromUrl(page: import("@playwright/test").Page): Promise<number> {
  const match = page.url().match(/sessionId=(\d+)/);
  expect(match, `expected ?sessionId= in ${page.url()}`).not.toBeNull();
  return Number(match![1]);
}

async function answersForStep(page: import("@playwright/test").Page, sessionId: number, step: string) {
  return page.evaluate(
    async ([id, key]) => {
      const response = await fetch(`/api/sessions/${id}`, { credentials: "include" });
      const payload = await response.json();
      return (payload.answers as { step: string; answer_text: string }[]).filter(
        (answer) => answer.step === key,
      );
    },
    [sessionId, step] as const,
  );
}

type Invocation = {
  task_type: string;
  provider: string | null;
  model: string | null;
  session_id: number | null;
  calls: number;
  failures: number;
  success: boolean;
  fallback_used: boolean;
};

async function realInvocationsFor(page: Page, sessionId: number, taskTypes: string[]): Promise<Invocation[]> {
  return page.evaluate(
    async ([id, types]) => {
      const response = await fetch("/api/system/ai-invocations?limit=100", { credentials: "include" });
      if (!response.ok) return [];
      const payload = (await response.json()) as { recent: Invocation[] };
      return payload.recent.filter(
        (row) =>
          (types as string[]).includes(row.task_type) &&
          row.session_id === id &&
          row.provider === "deepseek" &&
          row.model === "deepseek-flash" &&
          row.calls > 0 &&
          row.success === true &&
          row.fallback_used === false,
      );
    },
    [sessionId, taskTypes] as const,
  );
}

/**
 * The badge can be right while the audit is wrong, so the real-AI gate proves the
 * provider call itself: a teacher session reads the same `ai_invocations` rows the
 * runtime page shows.  The audit writer is asynchronous, hence the polling.
 */
async function expectRealDeepSeekInvocations(browser: Browser, sessionId: number, taskTypes: string[]) {
  const username = process.env.E2E_TEACHER_USERNAME;
  const password = process.env.E2E_TEACHER_PASSWORD;
  expect(username && password, "E2E_EXPECT_REAL_AI needs teacher credentials to read the audit trail").toBeTruthy();

  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await page.goto("/login");
    await page.getByLabel("用户名").fill(username!);
    await page.getByLabel("密码").fill(password!);
    await page.getByRole("button", { name: "登录并进入系统" }).click();
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);

    let found: Invocation[] = [];
    await expect
      .poll(
        async () => {
          found = await realInvocationsFor(page, sessionId, taskTypes);
          return found.map((row) => row.task_type).sort().join(",");
        },
        { timeout: 30_000, message: "ai_invocations must prove real DeepSeek calls" },
      )
      .toBe([...taskTypes].sort().join(","));

    for (const row of found) {
      expect(row.failures, `${row.task_type} had provider failures`).toBe(0);
    }
  } finally {
    await context.close();
  }
}

test("re-saving one step keeps a single logical answer", async ({ page }) => {
  await login(page);
  await page.goto("/student/case/1");

  const textarea = page.locator("textarea");
  await textarea.fill("第一版回答 A：发热皮疹，考虑感染。");
  await page.getByRole("button", { name: "保存回答" }).click();
  await expect(page.getByText("已保存")).toBeVisible();
  const sessionId = await sessionIdFromUrl(page);

  await textarea.fill("第二版回答 B：发热皮疹伴ANA阳性，考虑SLE并评估器官受累。");
  await page.getByRole("button", { name: "保存回答" }).click();
  await expect(page.getByText("已保存")).toBeVisible();

  const saved = await answersForStep(page, sessionId, "key_information");
  expect(saved).toHaveLength(1);
  expect(saved[0].answer_text).toContain("第二版回答 B");

  await page.reload();
  await expect(page.locator("textarea")).toHaveValue(/第二版回答 B/);
});

test("submitting with missing steps is rejected and nothing is scored", async ({ page }) => {
  await login(page);
  await page.goto("/student/case/1");

  const textarea = page.locator("textarea");
  await textarea.fill("只有第一阶段作答，不应允许提交。");
  await page.getByRole("button", { name: "保存回答" }).click();
  await expect(page.getByText("已保存")).toBeVisible();
  const sessionId = await sessionIdFromUrl(page);

  await page.getByRole("button", { name: "提交病例并生成反馈" }).click();
  await expect(page.getByTestId("training-error")).toContainText("尚未作答或未保存");
  await expect(page).toHaveURL(new RegExp(`sessionId=${sessionId}`));
  await expect(page).not.toHaveURL(/\/student\/result\//);
});

test("student completes a case with Coach and receives formative feedback", async ({ page, browser }) => {
  await login(page);
  await page.goto("/student/case/1");

  let first = true;
  let lastSaved = false;
  for (const step of STEPS) {
    await page.getByRole("button", { name: step.label, exact: true }).click();
    await page.locator("textarea").fill(step.text);
    // Matrix H: leave the final step unsaved on purpose. Submitting must persist
    // the dirty textarea rather than dropping the last answer.
    const isLastStep = step === STEPS[STEPS.length - 1];
    if (!isLastStep) {
      await page.getByRole("button", { name: "保存回答" }).click();
      await expect(page.getByText("已保存")).toBeVisible();
    } else {
      lastSaved = true;
    }
    if (first) {
      const sessionId = await sessionIdFromUrl(page);
      await page.getByRole("button", { name: "开始追问" }).click();
      // The first question is a real provider call (DeepSeek Thinking Mode), so it
      // can take well over the 5s default before the panel has anything to render.
      await expect(page.getByTestId("tutor-panel")).toBeVisible({ timeout: 90_000 });
      await expect(page.getByTestId("tutor-turn-tutor").first()).toBeVisible({ timeout: 30_000 });
      await page
        .getByPlaceholder("回答导师的问题（例如：为什么、依据是什么、如何排除）")
        .fill("因为患者发热伴皮疹和ANA阳性，我优先考虑自身免疫病，但需要先排除感染。");
      await page.getByRole("button", { name: "继续追问" }).click();
      await expect(page.getByTestId("tutor-turn-student")).toHaveCount(1, { timeout: 90_000 });
      await expect(page.getByTestId("tutor-turn-tutor")).toHaveCount(2, { timeout: 90_000 });
      const coached = await answersForStep(page, sessionId, "key_information");
      expect(coached).toHaveLength(1);

      // The coaching conversation is persisted, so a reload must restore it
      // together with the saved answer for this step.
      await page.reload({ waitUntil: "networkidle" });
      await expect(page.getByTestId("tutor-turn-tutor")).toHaveCount(2);
      await expect(page.getByTestId("tutor-turn-student")).toHaveCount(1);
      await expect(page.locator("textarea").first()).toHaveValue(/关键信息/);
      first = false;
    }
  }
  expect(lastSaved).toBe(true);

  const submit = page.getByRole("button", { name: "提交病例并生成反馈" });
  await expect(submit).toBeEnabled();
  // A real semantic evaluation runs a Thinking-Mode request across five answers,
  // so the submit round trip is minutes-scale in the worst case, not seconds.
  const submission = page.waitForResponse(
    (response) => response.url().includes("/api/sessions/") && response.url().endsWith("/submit"),
    { timeout: 240_000 },
  );
  await submit.click();
  expect((await submission).status()).toBe(200);
  const summary = (await (await submission).json()).summary as { evaluation_mode: string; degraded: boolean };
  const submittedSessionId = Number(page.url().match(/sessionId=(\d+)/)?.[1] ?? 0);
  if (submittedSessionId) {
    // The unsaved final answer must have been persisted by the submit path.
    const persisted = await answersForStep(page, submittedSessionId, "treatment");
    expect(persisted).toHaveLength(1);
    expect(persisted[0].answer_text).toContain("激素");
  }
  await expect(page).toHaveURL(/\/student\/result\//);

  // The indicator must state which engine actually produced the score.
  const indicator = page.getByTestId("evaluation-mode");
  if (EXPECT_REAL_AI) {
    // Production acceptance: a rule result is a failure here, not a variant.
    expect(summary.evaluation_mode, "E2E_EXPECT_REAL_AI requires a real DeepSeek evaluation").toBe("ai");
    expect(summary.degraded).toBe(false);
    await expect(indicator).toContainText("AI 语义评价");
    await expect(indicator).not.toContainText("规则降级评价");

    const resultSessionId = Number(page.url().split("/").pop());
    const result = await page.evaluate(async (id) => {
      const response = await fetch(`/api/sessions/${id}/result`, { credentials: "include" });
      return await response.json();
    }, resultSessionId);
    expect(result.score.evaluation_mode).toBe("ai");
    expect(result.score.degraded).toBe(false);
    expect(result.score.provider).toBe("deepseek");
    expect(result.score.model).toBe("deepseek-flash");
    expect(result.score.ai_score).not.toBeNull();
  } else if (summary.evaluation_mode === "ai" && !summary.degraded) {
    await expect(indicator).toContainText("AI 语义评价");
    // Cross-check the API provenance behind the badge: a real model call records
    // provider, model and an AI score.
    const resultSessionId = Number(page.url().split("/").pop());
    const result = await page.evaluate(async (id) => {
      const response = await fetch(`/api/sessions/${id}/result`, { credentials: "include" });
      return await response.json();
    }, resultSessionId);
    expect(result.score.evaluation_mode).toBe("ai");
    expect(result.score.degraded).toBe(false);
    expect(result.score.provider).toBeTruthy();
    expect(result.score.model).toBeTruthy();
    expect(result.score.ai_score).not.toBeNull();
  } else {
    await expect(indicator).toContainText("规则降级评价");
  }
  await expect(page.getByText("评分依据、遗漏点与安全提示")).toBeVisible();
  await expect(page.getByText("改进建议")).toBeVisible();
  await expect(page.getByText("更新后的能力画像")).toBeVisible();
  await page.getByRole("link", { name: "返回学习路径" }).click();
  await expect(page).toHaveURL(/\/student\/pathway$/);

  if (EXPECT_REAL_AI) {
    expect(submittedSessionId, "the submitted session id is required by the audit gate").toBeGreaterThan(0);
    await expectRealDeepSeekInvocations(browser, submittedSessionId, ["case_evaluation", "tutor_question"]);
  }
});

test("teacher confirms six dimensions and the review is recorded", async ({ page }) => {
  test.skip(!process.env.E2E_TEACHER_USERNAME || !process.env.E2E_TEACHER_PASSWORD, "Teacher credentials are required for the mutating review flow.");
  await page.goto("/login");
  await page.getByLabel("用户名").fill(process.env.E2E_TEACHER_USERNAME!);
  await page.getByLabel("密码").fill(process.env.E2E_TEACHER_PASSWORD!);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/teacher\/dashboard$/);
  await page.goto("/teacher/score-review");
  await page.getByRole("button", { name: "复核" }).first().click();
  for (const label of ["医学知识", "关键信息提取", "鉴别诊断", "证据整合", "临床决策", "循证医学"]) {
    await page.getByLabel(label).fill("65");
  }
  await page.getByLabel("复核说明").fill("E2E teacher review verification.");
  await page.getByRole("button", { name: "确认并更新画像" }).click();
  await expect(page.getByText("已确认").first()).toBeVisible();
});

test("teacher case authoring warns about identifiers and can undo the draft", async ({ page }) => {
  const teacherUser = process.env.E2E_TEACHER_USERNAME;
  const teacherPass = process.env.E2E_TEACHER_PASSWORD;
  test.skip(!teacherUser || !teacherPass, "Teacher credentials are required for the authoring flow.");

  await page.goto("/login");
  await page.getByLabel("用户名").fill(teacherUser!);
  await page.getByLabel("密码").fill(teacherPass!);
  const submit = page.getByRole("button", { name: "登录并进入系统" });
  await expect(submit).toBeEnabled();
  await submit.click();
  // Parallel workers make hydration and the redirect slower than the 5s default.
  await expect(page).toHaveURL(/\/teacher\/dashboard$/, { timeout: 20_000 });

  await page.goto("/teacher/cases");
  const suffix = Date.now().toString().slice(-6);
  await page.getByLabel("病例标题").fill(`E2E 去标识化验证 ${suffix}`);
  await page.getByLabel("学习目标，每行一项").fill("关键信息提取");
  await page.getByLabel("主诉").fill("发热两周");
  await page.getByLabel("现病史").fill("患者姓名：测试者，联系电话 13700137000，住院号 ZY202600999。");
  await page.getByLabel("体格检查").fill("面部皮疹");
  await page.getByLabel("实验室检查").fill("ANA阳性");
  await page.getByLabel("影像资料").fill("未见异常");
  await page.getByLabel("标准诊断").fill("系统性红斑狼疮");
  await page.getByLabel("鉴别诊断，每行一项").fill("感染");
  await page.getByLabel("治疗方案").fill("激素治疗后随访");
  await page.getByLabel("评分Rubric，JSON格式").fill("{}");
  await page.getByRole("button", { name: "新增病例" }).click();

  const warning = page.getByTestId("deidentification-warning");
  await expect(warning).toBeVisible({ timeout: 15_000 });
  await expect(warning).toContainText("涉及字段：现病史");
  // The warning must not echo the identifiers back into the page.
  await expect(warning).not.toContainText("13700137000");

  // Clean up the verification case through the page's own API session.
  const removed = await page.evaluate(async (title) => {
    const list = await (await fetch("/api/teacher/cases", { credentials: "include" })).json();
    const created = (list as { id: number; title: string }[]).find((row) => row.title === title);
    if (!created) return "not-found";
    const response = await fetch(`/api/teacher/cases/${created.id}`, { method: "DELETE", credentials: "include" });
    return String(response.status);
  }, `E2E 去标识化验证 ${suffix}`);
  expect(removed).toBe("200");
});

// Run against a deployment with no provider key (ai_configured=false), e.g. a
// disposable stack started without LLM_API_KEY:
//   E2E_EXPECT_FALLBACK=1 E2E_BASE_URL=http://127.0.0.1:18301 npx playwright test -g fallback
test("a keyless deployment shows the rule fallback honestly", async ({ page }) => {
  test.skip(!process.env.E2E_EXPECT_FALLBACK, "Set E2E_EXPECT_FALLBACK=1 for a keyless deployment.");

  await login(page);
  await page.goto("/student/case/1");

  for (const step of STEPS) {
    await page.getByRole("button", { name: step.label, exact: true }).click();
    await page.locator("textarea").first().fill(step.text);
    await page.getByRole("button", { name: "保存回答" }).click();
    await expect(page.getByText("已保存")).toBeVisible();
  }

  const submission = page.waitForResponse(
    (response) => response.url().includes("/api/sessions/") && response.url().endsWith("/submit"),
  );
  await page.getByRole("button", { name: "提交病例并生成反馈" }).click();
  expect((await submission).status()).toBe(200);
  await expect(page).toHaveURL(/\/student\/result\//);

  // The badge must state the degraded engine instead of implying a model call.
  await expect(page.getByTestId("evaluation-mode")).toContainText("规则降级评价");
  await expect(page.getByTestId("evaluation-mode")).not.toContainText("AI 语义评价");
  // The explanation surface still explains the score.
  await expect(page.getByText("评分依据、遗漏点与安全提示")).toBeVisible();

  const sessionId = Number(page.url().split("/").pop());
  const result = await page.evaluate(async (id) => {
    const response = await fetch(`/api/sessions/${id}/result`, { credentials: "include" });
    return await response.json();
  }, sessionId);
  expect(result.score.evaluation_mode).toBe("rule_fallback");
  expect(result.score.degraded).toBe(true);
  expect(result.score.ai_score).toBeNull();
  expect(result.score.rule_score).not.toBeNull();
});
