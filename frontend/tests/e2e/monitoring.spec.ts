import { expect, test } from "@playwright/test";

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

function record(page: import("@playwright/test").Page): Recorder {
  const recorder: Recorder = { consoleErrors: [], pageErrors: [], serverErrors: [], unauthorizedMe: 0 };
  page.on("console", (message) => {
    if (message.type() === "error") recorder.consoleErrors.push(message.text());
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

test("anonymous首页、登录页、学生导航：无 console 报错、无 5xx", async ({ page }) => {
  const recorder = record(page);

  await page.goto("/");
  await expect(page.locator("body")).toBeVisible();
  await expect(page.getByRole("link", { name: /登录|Login/ }).first()).toBeVisible();

  await page.goto("/login");
  await expect(page.getByRole("button", { name: "登录并进入系统" })).toBeVisible();

  await page.getByLabel("用户名").fill(student.username);
  await page.getByLabel("密码").fill(student.password);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/student\/dashboard$/, { timeout: 15_000 });

  for (const [label, path] of [
    ["学习首页", /\/student\/dashboard$/],
    ["学习路径", /\/student\/pathway$/],
    ["知识学习", /\/student\/knowledge$/],
    ["能力画像", /\/student\/profile$/],
    ["学习记录", /\/student\/history$/],
  ] as const) {
    await page.getByRole("link", { name: label }).click();
    // /student/pathway is server-rendered and its recommendation reason is a real
    // model call: measured 11.6-14.1s, so the old 15s budget sat on the edge.
    await expect(page).toHaveURL(path, { timeout: 60_000 });
  }

  await page.reload();
  await expect(page).toHaveURL(/\/student\/history$/, { timeout: 15_000 });

  expect(recorder.pageErrors, `uncaught page errors: ${recorder.pageErrors.join(" | ")}`).toEqual([]);
  expect(recorder.serverErrors, `unexpected 5xx: ${recorder.serverErrors.join(" | ")}`).toEqual([]);
  expect(recorder.unauthorizedMe, "an authenticated session must not loop on /api/auth/me").toBeLessThan(3);
});

test("学习路径与训练页在当前部署上可用", async ({ page }) => {
  const recorder = record(page);

  await page.goto("/login");
  await page.getByLabel("用户名").fill(student.username);
  await page.getByLabel("密码").fill(student.password);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/student\/dashboard$/);

  // The pathway view is where the rule-based planner explains itself.
  await page.goto("/student/pathway");
  await expect(page.getByText("推荐").first()).toBeVisible({ timeout: 15_000 });

  await page.goto("/student/case/1");
  await expect(page.locator("textarea")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "提交病例并生成反馈" })).toBeVisible();

  expect(recorder.serverErrors, `unexpected 5xx: ${recorder.serverErrors.join(" | ")}`).toEqual([]);
});
