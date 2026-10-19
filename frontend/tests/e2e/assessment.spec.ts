import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

/**
 * Independent-assessment E2E.
 *
 * Environment contract (all optional except the base URL):
 *   E2E_BASE_URL          the disposable deployment (default 127.0.0.1:8101)
 *   E2E_EXAM_STUDENT_USERNAME / E2E_EXAM_STUDENT_PASSWORD
 *                         a student with at least one OPEN sitting (the mutating
 *                         exam flow only; falls back to E2E_STUDENT_*)
 *   E2E_STUDENT_USERNAME  the account used by the read-only gate checks
 *   E2E_STUDENT_PASSWORD  that account's password
 *   E2E_RUN_MUTATING=1    enables the full login → start → five stages → submit run
 *   E2E_ADMIN_USERNAME / E2E_ADMIN_PASSWORD   optional role-gate check
 *
 * The mutating test consumes one open sitting. Provision it with the assessment
 * API (published form + a sitting whose window is open for that student) before
 * running; it is never a real student account.
 *
 * It takes its own account on purpose. A sitting is an independent assessment,
 * not a ClinPath formative intervention, so the student who sits it does not have
 * to be a study student -- and under the study access policy a CBL batch may not
 * train, which makes "some study student" the wrong default for a test that must
 * only depend on the exam working.
 *
 * The read-only tests work without any seeded sitting and assert the server-side
 * gates the UI relies on: anonymous access is refused and future stages are not
 * part of a sitting payload.
 */

const student = {
  username: process.env.E2E_STUDENT_USERNAME ?? "student1",
  password: process.env.E2E_STUDENT_PASSWORD ?? "student123",
};

const examStudent = {
  username: process.env.E2E_EXAM_STUDENT_USERNAME ?? student.username,
  password: process.env.E2E_EXAM_STUDENT_PASSWORD ?? student.password,
};

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/student\/dashboard$|\/teacher\/dashboard$/);
}

test("anonymous requests to the assessment API are refused", async ({ request }) => {
  for (const path of [
    "/api/assessments/my",
    "/api/assessments/blind/queue",
    "/api/assessments/adjudication/queue",
    "/api/assessments/admin/sittings",
    "/api/assessments/forms/admin/all",
  ]) {
    const response = await request.get(path);
    expect(response.status(), `${path} must not answer anonymously`).toBe(401);
  }
});

test("a student account cannot reach rating, authoring or study administration", async ({ page }) => {
  await login(page, student.username, student.password);

  const forbidden = await page.evaluate(async () => {
    const paths = [
      "/api/assessments/blind/queue",
      "/api/assessments/adjudication/queue",
      "/api/assessments/forms/reviewable",
      "/api/assessments/forms/admin/all",
      "/api/assessments/admin/sittings",
      "/api/assessments/admin/cohorts",
    ];
    const out: { path: string; status: number; code: string | null }[] = [];
    for (const path of paths) {
      const response = await fetch(path, { credentials: "include" });
      let code: string | null = null;
      try {
        const body = await response.json();
        code = body?.detail?.code ?? null;
      } catch {
        code = null;
      }
      out.push({ path, status: response.status, code });
    }
    return out;
  });

  for (const row of forbidden) {
    expect(row.status, `${row.path} must refuse a student`).toBe(403);
  }
});

test("the assessment list explains the rules and never leaks a score", async ({ page }) => {
  await login(page, student.username, student.password);
  await page.goto("/student/assessments");

  await expect(page.getByRole("heading", { name: "我的独立考核" })).toBeVisible();
  const body = (await page.locator("body").innerText()).toLowerCase();
  expect(body).toContain("不会给正确答案");
  expect(body).toContain("不会给自动评分");
  expect(body).not.toContain("总分");
});

test("a teacher-only surface tells an administrator it is not for them", async ({ page }) => {
  const adminUser = process.env.E2E_ADMIN_USERNAME;
  const adminPassword = process.env.E2E_ADMIN_PASSWORD;
  test.skip(!adminUser || !adminPassword, "Set E2E_ADMIN_USERNAME / E2E_ADMIN_PASSWORD to check the admin gate.");

  await login(page, adminUser!, adminPassword!);
  await page.goto("/teacher/assessments");
  await expect(page.getByRole("heading", { name: "独立考核盲评" })).toBeVisible();
  await expect(page.getByText("只对具有独立教师身份的评分者开放")).toBeVisible();
});

test.describe("student exam flow", () => {
  test.skip(!process.env.E2E_RUN_MUTATING, "Set E2E_RUN_MUTATING=1 to run a full exam against a disposable deployment.");

  test("start → draft survives reload → five stages → submit, with no answer feedback", async ({ page }) => {
    test.slow();
    await login(page, examStudent.username, examStudent.password);
    await page.goto("/student/assessments");

    const startLink = page.getByRole("link", { name: "开始考核" }).first();
    const resumeLink = page.getByRole("link", { name: "继续作答" }).first();
    // Wait for the list to settle before deciding there is nothing to do.
    await expect(
      startLink.or(resumeLink).or(page.getByText("目前没有已开放的独立考核")),
    ).toBeVisible();
    if ((await startLink.count()) === 0 && (await resumeLink.count()) === 0) {
      test.skip(true, "This account has no open sitting; provision one before running the mutating flow.");
      return;
    }

    const entry = (await startLink.count()) > 0 ? startLink : resumeLink;
    const sittingId = Number((await entry.getAttribute("href"))?.split("/").pop());
    expect(Number.isInteger(sittingId) && sittingId > 0, "sitting id in the exam URL").toBe(true);

    await entry.click();
    await expect(page).toHaveURL(new RegExp(`/student/assessments/${sittingId}$`));

    // A fresh sitting opens on the instructions screen; a resumed one goes straight in.
    // Wait for whichever the server decided before branching, otherwise the first
    // client render (still loading) makes the branch look like "resumed".
    await expect(
      page.getByTestId("assessment-instructions").or(page.getByTestId("assessment-exam")),
    ).toBeVisible();
    if (await page.getByTestId("assessment-instructions").count()) {
      await expect(page.getByText("不提供 AI 追问")).toBeVisible();
      await page.getByRole("button", { name: "开始考核" }).click();
    }
    await expect(page.getByTestId("assessment-exam")).toBeVisible();
    await expect(page.getByTestId("assessment-countdown")).toBeVisible();

    // The server tells us where the student is; the page must not show anything else.
    const view = await page.evaluate(async (id) => {
      const response = await fetch(`/api/assessments/my/${id}`, { credentials: "include" });
      return { status: response.status, body: await response.json() };
    }, sittingId);
    expect(view.status).toBe(200);
    expect(view.body).not.toHaveProperty("answer_key");
    expect(view.body).not.toHaveProperty("rubric");

    let completed = view.body.completed as number;
    let firstStage = true;

    while (completed < 5) {
      const textarea = page.getByLabel("本阶段作答");
      await expect(textarea).toBeVisible();
      const text = `第${completed + 1}阶段：关键信息、鉴别诊断与处理原则的推理记录（E2E）。`;
      await textarea.fill(text);

      if (firstStage) {
        // Proves the server-side draft, not just React state.
        await page.getByRole("button", { name: "立即保存草稿" }).click();
        await expect(page.getByText(/草稿已保存到服务器/).first()).toBeVisible();
        await page.reload();
        await expect(page.getByTestId("assessment-exam")).toBeVisible();
        await expect(page.getByLabel("本阶段作答")).toHaveValue(text);
        firstStage = false;
      }

      await page.getByRole("button", { name: "保存并提交本阶段" }).click();
      await expect(page.getByText(/提交后不能修改/).first()).toBeVisible();
      await page.getByRole("button", { name: "确认提交并查看下一阶段" }).click();

      completed += 1;
      if (completed < 5) {
        await expect(page.getByText(`已完成 ${completed} / 5 阶段`)).toBeVisible();
      }
    }

    // All five stages answered; the whole paper is submitted next.
    await expect(page.getByText("五个阶段已全部提交")).toBeVisible();
    await page.getByRole("button", { name: "提交整份答卷" }).click();
    await page.getByRole("button", { name: "确认提交整份答卷" }).click();

    await expect(page.getByTestId("assessment-submitted")).toBeVisible();
    await expect(page.getByText("答卷已提交").first()).toBeVisible();
    const confirmation = await page.locator("body").innerText();
    // The page may *say* it withholds these; it must never present them.
    expect(confirmation).not.toMatch(/参考诊断[:：]|标准答案[:：]|总分[:：]?\s*\d/);
    expect(confirmation).toContain("不显示正确答案");

    // The submitted payload carries no answer key either.
    const final = await page.evaluate(async (id) => {
      const response = await fetch(`/api/assessments/my/${id}`, { credentials: "include" });
      return await response.json();
    }, sittingId);
    expect(final.status).toBe("submitted");
    expect(JSON.stringify(final)).not.toContain("answer_key");
  });

  test("a blinded rater scores without identity and is locked after submit", async ({ page }) => {
    const raterUser = process.env.E2E_RATER_USERNAME;
    const raterPassword = process.env.E2E_RATER_PASSWORD;
    test.skip(!raterUser || !raterPassword, "Set E2E_RATER_USERNAME / E2E_RATER_PASSWORD to score a submitted answer.");

    await login(page, raterUser!, raterPassword!);
    await page.goto("/teacher/assessments");
    await expect(page.getByRole("heading", { name: "盲评与分歧裁决" })).toBeVisible();

    // Same settle wait: the queue is fetched after mount.
    await expect(
      page.getByRole("button", { name: /匿名答卷/ }).first().or(page.getByText("当前没有分配给你的匿名答卷")),
    ).toBeVisible();
    const pending = page.getByRole("button", { name: /待评分/ }).first();
    const entry =
      (await pending.count()) > 0 ? pending : page.getByRole("button", { name: /第 1 份匿名答卷/ }).first();
    if ((await entry.count()) === 0) {
      test.skip(true, "No submitted answer is assigned to this rater.");
      return;
    }
    await entry.click();
    // Either the scoring form or the locked notice must appear; a rerun finds the latter.
    await expect(page.getByText(/六维独立评分（0–100）|你已提交并锁定本答卷评分/)).toBeVisible();
    if (await page.getByText("你已提交并锁定本答卷评分").count()) {
      await expect(page.getByText("系统不回显已锁定的评分记录")).toBeVisible();
      return;
    }

    // The rating payload itself must not carry student identity or the other score.
    const blindCode = await page.evaluate(async () => {
      const response = await fetch("/api/assessments/blind/queue", { credentials: "include" });
      const queue = await response.json();
      return queue[0]?.blind_code ?? null;
    });
    expect(blindCode).toBeTruthy();
    const detail = await page.evaluate(async (code) => {
      const response = await fetch(`/api/assessments/blind/${encodeURIComponent(code as string)}`, {
        credentials: "include",
      });
      return await response.json();
    }, blindCode);
    const keys = Object.keys(detail);
    for (const forbidden of ["student_id", "student_name", "study_group", "timepoint", "other_score", "cohort_code"]) {
      expect(keys, `blind detail must not expose ${forbidden}`).not.toContain(forbidden);
    }

    for (const label of ["医学知识", "关键信息提取", "鉴别诊断", "证据整合", "临床决策", "循证安全"]) {
      await page.getByLabel(`${label}评分`).fill("75");
    }
    await page.getByRole("button", { name: "提交独立评分" }).click();
    await page.getByRole("button", { name: "确认提交并锁定" }).click();
    await expect(page.getByText(/评分已锁定/)).toBeVisible();
  });
});
