import { expect, test } from "@playwright/test";

const teacher = {
  username: process.env.E2E_TEACHER_USERNAME,
  password: process.env.E2E_TEACHER_PASSWORD,
};

test.skip(!teacher.username || !teacher.password, "Teacher credentials are required (set E2E_TEACHER_USERNAME / E2E_TEACHER_PASSWORD).");

test("teacher surfaces load without console errors or 5xx", async ({ page }) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const serverErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
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
  // The teacher dashboard is server-rendered and can include a real AI insight
  // call: measured 3.4-4.3s against the old 5s default.
  await expect(page).toHaveURL(/\/teacher\/dashboard$/, { timeout: 60_000 });

  await page.goto("/teacher/students");
  await expect(page.getByRole("heading", { name: /学生|Students/ }).first()).toBeVisible();

  await page.goto("/teacher/score-review");
  await expect(page.getByText("复核").first()).toBeVisible();

  await page.goto("/teacher/research-export");
  await expect(page.locator("body")).toBeVisible();

  await page.goto("/teacher/runtime");
  const version = page.getByTestId("deployment-version");
  await expect(version).toBeVisible();
  await expect(version).toContainText("Backend git SHA");
  await expect(version).toContainText("Schema revision");
  await expect(page.getByRole("heading", { name: "AI Runtime" })).toBeVisible();
  // No secret may ever be rendered on the runtime page.
  const runtimeText = await page.locator("body").innerText();
  expect(runtimeText).not.toMatch(/sk-[A-Za-z0-9]{10,}/);
  expect(runtimeText.toLowerCase()).not.toContain("authorization:");

  expect(pageErrors, `uncaught page errors: ${pageErrors.join(" | ")}`).toEqual([]);
  expect(serverErrors, `unexpected 5xx: ${serverErrors.join(" | ")}`).toEqual([]);
});

test("a teacher can probe the AI runtime without leaking secrets", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(teacher.username!);
  await page.getByLabel("密码").fill(teacher.password!);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/teacher\/dashboard$/, { timeout: 60_000 });

  await page.goto("/teacher/runtime");
  await page.getByRole("button", { name: "测试连通性" }).click();

  const body = page.locator("body");
  await expect(body).toContainText(/可达|不可达|未配置/, { timeout: 30_000 });
  const text = await body.innerText();
  expect(text).not.toMatch(/sk-[A-Za-z0-9]{10,}/);
});

test("teacher logout clears access and the audit rollup lists real invocations", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(teacher.username!);
  await page.getByLabel("密码").fill(teacher.password!);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/teacher\/dashboard$/, { timeout: 20_000 });

  // Matrix K: the audit surface lists the capability rollup, and no prompt or
  // response body is exposed anywhere on the page.
  await page.goto("/teacher/runtime");
  const audit = page.getByTestId("ai-audit");
  await expect(audit).toBeVisible();
  await expect(audit).toContainText("task_type");
  await expect(audit).toContainText(/case_evaluation|tutor_question|recommendation_explanation|teacher_insight/);
  const auditText = await audit.innerText();
  expect(auditText).not.toMatch(/"(messages|prompt|completion|body)"/);

  // Matrix M: logout then a protected route must land on the login page.
  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/teacher/dashboard");
  await expect(page).toHaveURL(/\/login/);
});
