import { expect, test } from "@playwright/test";

test.skip(!process.env.E2E_RUN_MUTATING, "Set E2E_RUN_MUTATING=1 to run a training flow against a disposable deployment.");

test("student completes a case with Coach and receives formative feedback", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(process.env.E2E_STUDENT_USERNAME ?? "student1");
  await page.getByLabel("密码").fill(process.env.E2E_STUDENT_PASSWORD ?? "student123");
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(/\/student\/dashboard$/);
  await page.goto("/student/case/1");
  await page.locator("textarea").fill("发热、皮疹和ANA阳性，需评估器官受累并排除感染。");
  await page.getByRole("button", { name: "保存回答" }).click();
  await expect(page.getByRole("button", { name: "获取追问" })).toBeEnabled();
  await page.getByRole("button", { name: "获取追问" }).click();
  await expect(page.getByText("系统追问")).toBeVisible();
  for (const step of ["初步诊断及依据", "鉴别诊断", "进一步检查", "治疗方案"]) {
    await page.getByRole("button", { name: step }).click();
    await page.locator("textarea").fill(`${step}：结合病例证据、鉴别排除和患者安全风险制定下一步策略。`);
    await page.getByRole("button", { name: "保存回答" }).click();
    await expect(page.getByRole("button", { name: "获取追问" })).toBeEnabled();
  }
  const submit = page.getByRole("button", { name: "提交病例并生成反馈" });
  await expect(submit).toBeEnabled();
  const submission = page.waitForResponse((response) => response.url().includes("/api/sessions/") && response.url().endsWith("/submit"));
  await submit.click();
  expect((await submission).status()).toBe(200);
  await expect(page).toHaveURL(/\/student\/result\//);
  await expect(page.getByText("AI形成性评价，仅供教学参考")).toBeVisible();
  await expect(page.getByText("更新后的能力画像")).toBeVisible();
  await page.getByRole("link", { name: "返回学习路径" }).click();
  await expect(page).toHaveURL(/\/student\/pathway$/);
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
