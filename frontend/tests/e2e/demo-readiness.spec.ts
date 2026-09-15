/**
 * The demo-video acceptance path: what a clinical teacher reads on screen.
 *
 * The rule these tests enforce is not "the page is Chinese" — it is that no
 * surface asks a teacher to understand `stage_1_basic_recognition`, `case`,
 * `medical_knowledge`, `module_type` or `student_code`, and that the learner can
 * come back to a finished case and see their own reasoning and tutor dialogue.
 *
 * Production browser acceptance runs against https://clinpath.1031989.xyz via
 * E2E_BASE_URL; without a real browser tool in the session, Chromium + Playwright
 * is the formal fallback documented in the goal.
 */

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const teacher = {
  username: process.env.E2E_TEACHER_USERNAME,
  password: process.env.E2E_TEACHER_PASSWORD,
};

const student = {
  username: process.env.E2E_STUDENT_USERNAME ?? "student1",
  password: process.env.E2E_STUDENT_PASSWORD ?? "student123",
};

type Recorder = {
  consoleErrors: string[];
  pageErrors: string[];
  serverErrors: string[];
  unauthorizedMe: number;
};

function record(page: Page): Recorder {
  const recorder: Recorder = { consoleErrors: [], pageErrors: [], serverErrors: [], unauthorizedMe: 0 };
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    const source = message.location()?.url ?? "";
    // The login page probes /api/auth/me before a session exists.
    if (text.includes("Failed to load resource") && source.endsWith("/api/auth/me")) return;
    recorder.consoleErrors.push(`${text} @ ${source}`);
  });
  page.on("pageerror", (error) => recorder.pageErrors.push(String(error)));
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith("/api/")) return;
    if (response.status() >= 500) recorder.serverErrors.push(`${response.status()} ${url.pathname}`);
    if (url.pathname === "/api/auth/me" && response.status() === 401) recorder.unauthorizedMe += 1;
  });
  return recorder;
}

async function loginTeacher(page: Page) {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(teacher.username!);
  await page.getByLabel("密码").fill(teacher.password!);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/teacher\/dashboard$/, { timeout: 60_000 });
}

async function loginStudent(page: Page) {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(student.username);
  await page.getByLabel("密码").fill(student.password);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/student\/dashboard$/, { timeout: 60_000 });
}

/** Text a teacher must never be shown as if it were a business label. */
const DEVELOPER_FIELDS = [
  "stage_1_basic_recognition",
  "stage_2_differential_reasoning",
  "stage_3_clinical_decision",
  "stage_4_evidence_based_learning",
  "module_type",
  "student_code",
  "class_name",
  "created_at",
];

async function expectNoDeveloperFields(page: Page, where: string) {
  const body = await page.locator("body").innerText();
  for (const field of DEVELOPER_FIELDS) {
    expect(body, `${where} must not print the raw field ${field}`).not.toContain(field);
  }
}

test.describe("teacher demo surfaces", () => {
  test.skip(!teacher.username || !teacher.password, "Teacher credentials are required.");

  test("学生画像 → 教学驾驶舱 is a real navigation with a visible current page", async ({ page }) => {
    const recorder = record(page);
    await loginTeacher(page);

    await page.getByRole("link", { name: "学生画像" }).click();
    await expect(page).toHaveURL(/\/teacher\/students$/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { name: /学生总览/ })).toBeVisible();

    // The reported "clicking Dashboard does nothing" must be impossible to read
    // that way: the clicked section is highlighted and marked as the current page.
    await page.getByRole("link", { name: "教学驾驶舱" }).click();
    await expect(page).toHaveURL(/\/teacher\/dashboard$/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "教师精准教学驾驶舱" })).toBeVisible();
    const current = page.getByRole("link", { name: "教学驾驶舱" });
    await expect(current).toHaveAttribute("aria-current", "page");

    expect(recorder.pageErrors, `uncaught page errors: ${recorder.pageErrors.join(" | ")}`).toEqual([]);
    expect(recorder.serverErrors, `unexpected 5xx: ${recorder.serverErrors.join(" | ")}`).toEqual([]);
  });

  test("学生总览 shows teaching language, not enum keys", async ({ page }) => {
    const recorder = record(page);
    await loginTeacher(page);
    await page.goto("/teacher/students");

    await expect(page.getByRole("heading", { name: "学生总览" })).toBeVisible();
    const body = await page.locator("body").innerText();

    expect(body).toMatch(/阶段[1-4]：/);
    for (const field of [
      "stage_1_basic_recognition",
      "stage_1_basic_knowledge",
      "stage_2_differential_reasoning",
      "stage_3_clinical_decision",
      "stage_4_evidence_based_learning",
    ]) {
      expect(body, `学生总览 must not print ${field}`).not.toContain(field);
    }
    // The synthetic E2E account is normalised away; a student called "test" is
    // not something a teacher should ever have to explain to a reviewer.
    expect(body).not.toMatch(/(^|\s)test(\s|$)/);
    expect(body).toContain("李明");

    expect(recorder.serverErrors, `unexpected 5xx: ${recorder.serverErrors.join(" | ")}`).toEqual([]);
  });

  test("班级能力画像 is below a full-width heatmap at 1440x900 and 1920x1080", async ({ page }) => {
    await loginTeacher(page);

    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 1920, height: 1080 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto("/teacher/dashboard");
      await expect(page.getByRole("heading", { name: "教师精准教学驾驶舱" })).toBeVisible();

      const heatmap = page.getByTestId("class-heatmap");
      const profile = page.getByTestId("class-competency-profile");
      await expect(heatmap).toBeVisible();
      await expect(profile).toBeVisible();

      const heatmapBox = await heatmap.boundingBox();
      const profileBox = await profile.boundingBox();
      expect(heatmapBox && profileBox).toBeTruthy();

      // The class profile starts below the heatmap, not in a narrow right column.
      expect(profileBox!.y).toBeGreaterThanOrEqual(heatmapBox!.y + heatmapBox!.height - 1);
      // ...and it uses the content width, so the heatmap is not left with a
      // large empty area under a short right-hand card.
      expect(profileBox!.width).toBeGreaterThan(heatmapBox!.width * 0.95);

      // No horizontal scrolling on the demo viewport.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `viewport ${viewport.width}x${viewport.height} must not scroll sideways`).toBeLessThanOrEqual(1);
    }
  });

  test("李明 profile explains the trend and the evidence in teaching language", async ({ page }) => {
    const recorder = record(page);
    await loginTeacher(page);
    await page.goto("/teacher/students");
    await page.getByRole("link", { name: "查看详情" }).first().click();
    await expect(page).toHaveURL(/\/teacher\/students\/\d+$/);
    await expect(page.getByRole("heading", { name: /学习画像/ })).toBeVisible();

    await expect(page.getByText("阶段性学习表现趋势")).toBeVisible();
    await expect(page.getByTestId("growth-trend-chart")).toBeVisible();
    await expect(page.getByRole("heading", { name: "学习证据事件" })).toBeVisible();

    await expectNoDeveloperFields(page, "学生画像");
    const body = await page.locator("body").innerText();
    expect(body).toMatch(/医学知识|鉴别诊断|证据整合|临床决策|循证医学/);
    expect(body).toMatch(/基础知识学习|病例推理训练|临床技能训练|指南循证学习|SP模拟问诊/);
    expect(body).toMatch(/→/); // a competency change is shown as before → after

    expect(recorder.pageErrors).toEqual([]);
    expect(recorder.serverErrors.join(" | ")).toBe("");
  });

  test("研究数据 preview is readable, honest about its size, and diverse", async ({ page }) => {
    const recorder = record(page);
    await loginTeacher(page);
    await page.goto("/teacher/research-export");

    await expect(page.getByRole("heading", { name: "匿名化研究数据", exact: true })).toBeVisible();
    const headers = await page.locator("table thead th").allInnerTexts();
    expect(headers).toEqual(["匿名学生编号", "班级", "学习模块", "训练得分", "记录时间"]);

    const body = await page.locator("body").innerText();
    expect(body).not.toContain("student_code");
    expect(body).not.toContain("module_type");
    expect(body).not.toContain("created_at");
    // The preview must say how much of the dataset it is showing.
    expect(body).toMatch(/当前显示 \d+ \/ 筛选后 \d+ 条 · 完整研究数据共 \d+ 条/);

    // A demo dataset must describe a class: several students, modules and dates.
    const codes = new Set(await page.locator("tbody tr td:nth-child(1)").allInnerTexts());
    const modules = new Set(await page.locator("tbody tr td:nth-child(3)").allInnerTexts());
    const dates = new Set(
      (await page.locator("tbody tr td:nth-child(5)").allInnerTexts()).map((value) => value.slice(0, 10)),
    );
    expect(codes.size).toBeGreaterThanOrEqual(3);
    expect(modules.size).toBeGreaterThanOrEqual(3);
    expect(dates.size).toBeGreaterThanOrEqual(3);

    // The download is the complete dataset, and it really is a CSV a teacher can
    // open (the page's own link, exercised through the same proxy and cookie).
    const csv = await page.request.get("/api/teacher/export/research-data.csv");
    expect(csv.status()).toBe(200);
    expect(csv.headers()["content-type"]).toContain("text/csv");
    const csvBody = await csv.text();
    expect(csvBody.startsWith("\ufeff")).toBe(true);
    expect(csvBody).toContain("匿名学生编号,班级,学习模块,训练得分,记录时间");

    expect(recorder.serverErrors.join(" | ")).toBe("");
  });
});

test.describe("student learning history", () => {
  test("学习记录 lists finished cases and the review keeps the whole reasoning", async ({ page }) => {
    const recorder = record(page);
    await loginStudent(page);

    await page.getByRole("link", { name: "学习记录" }).click();
    await expect(page).toHaveURL(/\/student\/history$/);
    await expect(page.getByRole("heading", { name: "我的病例学习记录" })).toBeVisible();

    const table = page.getByTestId("history-table");
    await expect(table).toBeVisible();
    await expect(page.locator("tbody tr").first()).toContainText("已完成");
    await expect(page.locator("tbody tr").first()).toContainText(/AI 语义评价|规则降级评价/);
    await expectNoDeveloperFields(page, "学习记录");

    await page.getByRole("link", { name: "查看学习过程" }).first().click();
    await expect(page).toHaveURL(/\/student\/result\/\d+$/);

    const review = page.getByTestId("reasoning-review");
    await expect(review).toBeVisible();
    for (const title of ["关键信息提取", "初步诊断及依据", "鉴别诊断", "进一步检查", "治疗方案"]) {
      await expect(review.getByText(title, { exact: false }).first()).toBeVisible();
    }
    await expect(review).toContainText("我的最终回答");
    await expectNoDeveloperFields(page, "病例复盘");

    // The record is server state, not React state: a hard reload keeps it.
    const url = page.url();
    await page.reload({ waitUntil: "networkidle" });
    await expect(page).toHaveURL(url);
    await expect(page.getByTestId("reasoning-review")).toBeVisible();
    await expect(page.getByTestId("reasoning-review")).toContainText("我的最终回答");

    expect(recorder.pageErrors, `uncaught page errors: ${recorder.pageErrors.join(" | ")}`).toEqual([]);
    expect(recorder.serverErrors, `unexpected 5xx: ${recorder.serverErrors.join(" | ")}`).toEqual([]);
    expect(recorder.consoleErrors, `critical console errors: ${recorder.consoleErrors.join(" | ")}`).toEqual([]);
    expect(recorder.unauthorizedMe, "an authenticated session must not loop on /api/auth/me").toBeLessThan(3);
  });
});
