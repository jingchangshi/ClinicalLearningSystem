import { expect, test } from "@playwright/test";

const student = {
  username: process.env.E2E_STUDENT_USERNAME ?? "student1",
  password: process.env.E2E_STUDENT_PASSWORD ?? "student123",
};

async function login(page: import("@playwright/test").Page, next?: string) {
  await page.goto(`/login${next ? `?next=${encodeURIComponent(next)}` : ""}`);
  await page.getByLabel("用户名").fill(student.username);
  await page.getByLabel("密码").fill(student.password);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
}

test("student login, refresh, wrong-role next, and logout", async ({ page }) => {
  await login(page, "/teacher/dashboard");
  await expect(page).toHaveURL(/\/student\/dashboard$/);
  await page.reload();
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/student/dashboard");
  await expect(page).toHaveURL(/\/login/);
});
