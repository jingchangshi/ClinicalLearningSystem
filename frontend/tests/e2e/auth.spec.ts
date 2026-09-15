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

test("login lands on the dashboard without a manual refresh", async ({ page }) => {
  await login(page);
  // No reload, no second click: the landing URL itself must be the dashboard.
  await expect(page).toHaveURL(/\/student\/dashboard$/, { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /学习|Dashboard|ClinPath/ }).first()).toBeVisible();
});

test("the public login page never publishes teacher credentials", async ({ page }) => {
  await page.goto("/login");
  const body = (await page.locator("body").innerText()).toLowerCase();
  expect(body).not.toContain("teacher123");
  expect(body).not.toContain("admin123");

  // The only prefilled shortcut is the restricted student demo account.
  const demoButtons = page.getByRole("button", { name: /student1/ });
  await expect(demoButtons).toHaveCount(1);
  await demoButtons.click();
  await expect(page.getByLabel("用户名")).toHaveValue("student1");
});

test("protected routes send anonymous visitors to login with a next target", async ({ page }) => {
  await page.goto("/student/dashboard");
  await expect(page).toHaveURL(/\/login\?next=%2Fstudent%2Fdashboard/);
  await page.goto("/teacher/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

const forgedTokens = {
  "bad signature": () => {
    const header = encode({ alg: "HS256", typ: "JWT" });
    const payload = encode(teacherClaims());
    return `${header}.${payload}.not-a-valid-signature`;
  },
  "alg != HS256": () => {
    const header = encode({ alg: "RS256", typ: "JWT" });
    const payload = encode(teacherClaims());
    return `${header}.${payload}.${"A".repeat(43)}`;
  },
  "expired token": () => {
    const header = encode({ alg: "HS256", typ: "JWT" });
    const payload = encode({
      sub: "1",
      username: "student1",
      role: "teacher",
      exp: Math.floor(Date.now() / 1000) - 60,
    });
    return `${header}.${payload}.${"A".repeat(43)}`;
  },
  "no signature segment": () => `${encode({ alg: "HS256", typ: "JWT" })}.${encode(teacherClaims())}.`,
  "unsigned alg=none": () => {
    const header = encode({ alg: "none", typ: "JWT" });
    const payload = encode(teacherClaims());
    return `${header}.${payload}.`;
  },
};

function teacherClaims() {
  return {
    sub: "1",
    username: "student1",
    role: "teacher",
    exp: Math.floor(Date.now() / 1000) + 3600,
  };
}

for (const [label, build] of Object.entries(forgedTokens)) {
  test(`a token with ${label} cannot claim the teacher role`, async ({ page, context, baseURL }) => {
    const host = new URL(baseURL ?? "http://127.0.0.1:8101").hostname;
    await context.addCookies([{ name: "access_token", value: build(), domain: host, path: "/" }]);

    await page.goto("/teacher/dashboard");
    await expect(page).toHaveURL(/\/login/);
    await page.goto("/student/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
}

test("an authenticated student token still reaches only the student area", async ({ page, context, baseURL }) => {
  // A real login produces a genuinely signed cookie; the proxy must accept it and
  // still route by the verified role.
  await login(page);
  await expect(page).toHaveURL(/\/student\/dashboard$/);
  const cookies = await context.cookies();
  expect(cookies.some((cookie) => cookie.name === "access_token")).toBe(true);
  expect(new URL(baseURL ?? "http://127.0.0.1:8101").hostname).toBeTruthy();
  await page.goto("/teacher/dashboard");
  await expect(page).toHaveURL(/\/student\/dashboard$/);
});

test("a student in the teacher area is routed to their own dashboard", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/student\/dashboard$/);
  await page.goto("/teacher/dashboard");
  await expect(page).toHaveURL(/\/student\/dashboard$/);
});

function encode(value: unknown): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}
