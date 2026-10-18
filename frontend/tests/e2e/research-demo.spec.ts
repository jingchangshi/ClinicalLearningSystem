/**
 * Work package C: the teaching-loop demo surfaces.
 *
 * Two pages are easy to confuse, and confusing them is a research-integrity
 * problem rather than a cosmetic one:
 *
 *   /teacher/research-export  — real (anonymised) learning records.
 *   /teacher/research-demo    — the synthetic study dataset, no database access.
 *
 * This spec proves (a) a teacher sees the synthetic marker and can download the
 * SYNTHETIC CSV, (b) a student is redirected away in the browser *and* gets 403
 * from the API, and (c) the real export page is unchanged and still offers its
 * own CSV. It proves the system runs; it says nothing about teaching effect.
 */

import { expect, test } from "@playwright/test";

const teacher = {
  username: process.env.E2E_TEACHER_USERNAME,
  password: process.env.E2E_TEACHER_PASSWORD,
};

const student = {
  username: process.env.E2E_STUDENT_USERNAME ?? "student1",
  password: process.env.E2E_STUDENT_PASSWORD ?? "student123",
};

const SYNTHETIC_BANNER = /合成教学研究演示｜虚拟学生、虚拟评分者｜不代表真实教学成效/;

test.describe("synthetic teaching-research demo", () => {
  test.skip(!teacher.username || !teacher.password, "Teacher credentials are required (set E2E_TEACHER_USERNAME / E2E_TEACHER_PASSWORD).");

  test("a teacher sees the synthetic banner and downloads the SYNTHETIC CSV", async ({ page }) => {
    const pageErrors: string[] = [];
    const serverErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(String(error)));
    page.on("response", (response) => {
      const url = new URL(response.url());
      if (url.pathname.startsWith("/api/") && response.status() >= 500) {
        serverErrors.push(`${response.status()} ${url.pathname}`);
      }
    });

    await page.goto("/login");
    await page.getByLabel("用户名").fill(teacher.username!);
    await page.getByLabel("密码").fill(teacher.password!);
    await page.getByRole("button", { name: "登录并进入系统" }).click();
    await expect(page).toHaveURL(/\/teacher\/dashboard$/, { timeout: 60_000 });

    await page.goto("/teacher/research-demo");
    await expect(page.getByRole("heading", { name: "合成教学研究演示" })).toBeVisible();

    // The marker must be the first thing in the page body: a screenshot that
    // starts at the top can never show the numbers without it.
    const banner = page.getByTestId("demo-research-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(SYNTHETIC_BANNER);
    const firstBodyText = await page.locator("body").innerText();
    expect(firstBodyText.indexOf("合成教学研究演示｜虚拟学生")).toBeLessThan(
      firstBodyText.indexOf("两组均值与模拟效应"),
    );

    // The numbers on the page are the served dataset's, not a hand-written copy.
    await expect(page.getByText("虚拟学生", { exact: true })).toBeVisible();
    await expect(page.getByText("60", { exact: true }).first()).toBeVisible();

    // The synthetic CSV downloads, and the file itself carries the marker.
    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("demo-research-csv").click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain("SYNTHETIC");
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    const csv = Buffer.concat(chunks).toString("utf-8");
    expect(csv).toContain("SYNTHETIC_DEMO_NOT_REAL_STUDENTS");
    expect(csv).toContain("模拟数据，不代表真实教学成效");

    expect(pageErrors, `uncaught page errors: ${pageErrors.join(" | ")}`).toEqual([]);
    expect(serverErrors, `unexpected 5xx: ${serverErrors.join(" | ")}`).toEqual([]);
  });

  test("a student is redirected away and the API answers 403", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("用户名").fill(student.username);
    await page.getByLabel("密码").fill(student.password);
    await page.getByRole("button", { name: "登录并进入系统" }).click();
    await expect(page).toHaveURL(/\/student\/dashboard$/, { timeout: 60_000 });

    await page.goto("/teacher/research-demo");
    await expect(page).not.toHaveURL(/\/teacher\/research-demo$/);
    await expect(page.locator("body")).not.toContainText(SYNTHETIC_BANNER);

    // The backend is the final authority: the same page's data endpoints refuse
    // the student's own session cookie, whatever the browser rendered.
    for (const path of [
      "/api/teacher/demo-research/summary",
      "/api/teacher/demo-research/students",
      "/api/teacher/demo-research/export.csv",
    ]) {
      const response = await page.request.get(path);
      expect(response.status(), `${path} must refuse a student`).toBe(403);
    }
  });

  test("the real research export is unchanged and still offers its own CSV", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("用户名").fill(teacher.username!);
    await page.getByLabel("密码").fill(teacher.password!);
    await page.getByRole("button", { name: "登录并进入系统" }).click();
    await expect(page).toHaveURL(/\/teacher\/dashboard$/, { timeout: 60_000 });

    await page.goto("/teacher/research-export");
    await expect(page.getByRole("heading", { name: "匿名化研究数据", exact: true })).toBeVisible();
    await expect(page.getByTestId("research-csv-download")).toBeVisible();

    // The two pages must stay distinguishable: the real export must not be
    // wearing the synthetic marker, and it links to the demo rather than
    // silently replacing it.
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(SYNTHETIC_BANNER);
    expect(body).toContain("匿名化");
  });
});
