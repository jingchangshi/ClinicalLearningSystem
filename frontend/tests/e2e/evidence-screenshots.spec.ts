/**
 * E2 evidence screenshots — captured from the ACTUALLY RUNNING isolated build.
 *
 * Not an assertion suite: it drives the real UI and saves PNGs. Each file name
 * states what it shows; the companion markdown records the commit SHA, ports and
 * UTC capture time. A screenshot is only evidence of the screen it shows — it is
 * never evidence of teaching effect, and every account here is a TEST account.
 *
 *   E2E_BASE_URL=http://127.0.0.1:8401 E2E_SHOTS_DIR=/abs/path npx playwright test tests/e2e/evidence-screenshots.spec.ts
 */
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Browser, Page } from "@playwright/test";

const SHOTS = process.env.E2E_SHOTS_DIR;
const ADMIN = { username: process.env.E2E_ADMIN_USERNAME ?? "test_admin", password: process.env.E2E_ADMIN_PASSWORD ?? "test-admin-pw" };
const TEACHER_A = { username: "test_teacher_a", password: process.env.E2E_TEACHER_PASSWORD ?? "test-teacher-pw" };
const TEACHER_B = { username: "test_teacher_b", password: process.env.E2E_TEACHER_PASSWORD ?? "test-teacher-pw" };

async function shot(page: Page, name: string) {
  mkdirSync(SHOTS!, { recursive: true });
  await page.waitForTimeout(400); // let a fetched panel finish painting
  await page.screenshot({ path: join(SHOTS!, `${name}.png`), fullPage: true });
}

async function open(browser: Browser, who: { username: string; password: string }, area: "student" | "teacher") {
  const context = await browser.newContext({ baseURL: process.env.E2E_BASE_URL, viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByLabel("用户名").fill(who.username);
  await page.getByLabel("密码").fill(who.password);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(new RegExp(`/${area}/dashboard$`), { timeout: 60_000 });
  return { context, page };
}

test.describe.configure({ mode: "serial" });

test.describe("E2 evidence screenshots (TEST accounts only)", () => {
  test.skip(!SHOTS, "Set E2E_SHOTS_DIR to capture evidence screenshots.");

  test("study admin: design, schedule and dataset surfaces", async ({ browser }) => {
    const { context, page } = await open(browser, ADMIN, "teacher");
    try {
      await page.goto("/teacher/assessment-admin");
      await expect(page.getByRole("heading", { name: "独立考核管理" })).toBeVisible();
      await shot(page, "01_study_admin_sittings_overview");

      await page.getByRole("button", { name: "批次与入组" }).click();
      await shot(page, "02_study_admin_cohorts_7batches_x7");

      await page.getByRole("button", { name: "分配冻结" }).click();
      await shot(page, "03_study_admin_frozen_form_order_and_cluster_allocation");

      await page.getByRole("button", { name: "批量排考" }).click();
      await shot(page, "04_study_admin_bulk_schedule_98_sittings");

      await page.getByRole("button", { name: "数据集与一致性" }).click();
      await page.getByRole("button", { name: "生成工作数据集" }).click();
      await shot(page, "05_study_admin_research_export_working_dataset");

      await page.getByRole("button", { name: "审计日志" }).click();
      await shot(page, "06_study_admin_audit_log");
    } finally {
      await context.close();
    }
  });

  test("teacher: form review and blinded rater view", async ({ browser }) => {
    const { context, page } = await open(browser, TEACHER_A, "teacher");
    try {
      await page.goto("/teacher/assessment-forms");
      await page.getByRole("button", { name: "待我审核" }).click();
      await shot(page, "07_teacher_form_review_queue");

      await page.getByRole("button", { name: "创建题本 / 新版本" }).click();
      await shot(page, "08_teacher_form_authoring_panel");
    } finally {
      await context.close();
    }

    const rater = await open(browser, TEACHER_B, "teacher");
    try {
      await rater.page.goto("/teacher/assessments");
      await expect(rater.page.getByRole("heading", { name: "盲评与分歧裁决" })).toBeVisible();
      await shot(rater.page, "09_blinded_rater_queue_no_identity");
      // Prefer an UNSCORED answer: a scored one opens the locked notice instead of
      // the six-dimension form we want to show.
      const queue = await rater.page.evaluate(async () => {
        const response = await fetch("/api/assessments/blind/queue", { credentials: "include" });
        return (await response.json()) as { blind_code: string; reviewed: boolean }[];
      });
      const pending = queue.find((row) => !row.reviewed) ?? queue[0];
      if (pending) {
        await rater.page.getByRole("button", { name: new RegExp(`第 \\d+ 份匿名答卷`) }).first().click();
        const scoring = rater.page.getByText("六维独立评分（0–100）");
        const locked = rater.page.getByText("你已提交并锁定本答卷评分");
        await expect(scoring.or(locked)).toBeVisible({ timeout: 20_000 });
        await shot(rater.page, "10_blinded_rater_six_dimension_form_no_identity");
      }
    } finally {
      await rater.context.close();
    }
  });

  test("study admin: form publish gate and adjudication queue", async ({ browser }) => {
    const { context, page } = await open(browser, ADMIN, "teacher");
    try {
      await page.goto("/teacher/assessment-forms");
      await page.getByRole("button", { name: "题本审核状态与发布" }).click();
      await shot(page, "11_admin_form_review_status_and_publish_gate");
    } finally {
      await context.close();
    }

    const adjudicator = await open(browser, { username: "test_adjudicator", password: TEACHER_A.password }, "teacher");
    try {
      await adjudicator.page.goto("/teacher/assessments");
      await adjudicator.page.getByRole("button", { name: "分歧裁决" }).click();
      await shot(adjudicator.page, "12_adjudication_queue_flagged_disagreement");
    } finally {
      await adjudicator.context.close();
    }
  });

  test("student: list, a stage in progress, submitted confirmation with no score", async ({ browser }) => {
    const manifest = JSON.parse(
      (await import("node:fs")).readFileSync(process.env.E2E_FIXTURE_MANIFEST!, "utf8"),
    ) as { student_ids: number[]; student_logins: Record<string, string>; student_password: string };
    const studentId = manifest.student_ids[0];
    const student = { username: manifest.student_logins[String(studentId)], password: manifest.student_password };

    const { context, page } = await open(browser, student, "student");
    try {
      await page.goto("/student/assessments");
      await expect(page.getByRole("heading", { name: "我的独立考核" })).toBeVisible();
      await shot(page, "13_student_assessment_list");

      const sittings = await page.evaluate(async () => {
        const response = await fetch("/api/assessments/my", { credentials: "include" });
        return (await response.json()) as { id: number; status: string; timepoint: string }[];
      });
      const submitted = sittings.find((row) => row.status === "submitted");
      if (submitted) {
        await page.goto(`/student/assessments/${submitted.id}`);
        await expect(page.getByTestId("assessment-submitted")).toBeVisible();
        await shot(page, "14_student_submitted_confirmation_no_score");
      }
    } finally {
      await context.close();
    }

    // A different, untouched TEST student for the in-progress stage: the first
    // student has already used both timepoints in the R8.2 flow.
    for (const candidateId of manifest.student_ids.slice(1, 12)) {
      const other = { username: manifest.student_logins[String(candidateId)], password: manifest.student_password };
      const fresh = await open(browser, other, "student");
      try {
        const sittings = await fresh.page.evaluate(async () => {
          const response = await fetch("/api/assessments/my", { credentials: "include" });
          return (await response.json()) as { id: number; status: string }[];
        });
        const live = sittings.find((row) => row.status === "assigned" || row.status === "in_progress");
        if (!live) continue;
        await fresh.page.goto(`/student/assessments/${live.id}`);
        await expect(
          fresh.page
            .getByTestId("assessment-instructions")
            .or(fresh.page.getByTestId("assessment-exam"))
            .or(fresh.page.getByTestId("assessment-expired")),
        ).toBeVisible({ timeout: 20_000 });
        if (await fresh.page.getByTestId("assessment-expired").count()) continue;
        if (await fresh.page.getByTestId("assessment-instructions").count()) {
          await shot(fresh.page, "15a_student_exam_instructions");
          await fresh.page.getByRole("button", { name: "开始考核" }).click();
        }
        await expect(fresh.page.getByTestId("assessment-exam")).toBeVisible({ timeout: 20_000 });
        await fresh.page
          .getByLabel("本阶段作答")
          .fill("TEST 合成作答：关键信息提取与初步判断（截图用，非真实学生）。");
        await fresh.page.getByRole("button", { name: "立即保存草稿" }).click();
        await expect(fresh.page.getByText(/草稿已保存到服务器/).first()).toBeVisible();
        await shot(fresh.page, "15b_student_exam_stage_in_progress_draft_saved");
        return;
      } finally {
        await fresh.context.close();
      }
    }
    throw new Error("no untouched TEST student had a live sitting for the in-progress screenshot");
  });
});
