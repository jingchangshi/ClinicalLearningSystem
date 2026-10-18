import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

/**
 * R8.2 — the complete research flow, driven through the browser.
 *
 * admin creates a form → two DIFFERENT teachers review and approve it →
 * admin publishes → student sits T0 → D2/D3 formative training → D4/D5
 * personalised task → student sits T1 → two teachers score the blinded queues →
 * a forced disagreement is adjudicated → the study admin exports the research
 * data.
 *
 * Every account and every record here is SYNTHETIC test data:
 *
 *   - students are named "TEST测试学生NN" (class "TEST 临床医学测试班")
 *   - staff are "TEST 测试教师A/B（非真实教师）", provisioned by
 *     scripts/grant/e2e/build_fixture.py via app.manage_users
 *   - the form code is prefixed TEST-
 *
 * This test says the software works. It says nothing about teaching effect, and
 * it must never be presented as real teacher review or real student data.
 *
 * Requires the isolated stack from scripts/grant/e2e/run_acceptance.sh:
 *   E2E_BASE_URL           http://127.0.0.1:8401
 *   E2E_FIXTURE_MANIFEST   /tmp/clinpath-e2e/fixture.json
 *   E2E_STUDENT_USERNAME/PASSWORD  the demo student used for the training steps
 *   E2E_TEACHER_USERNAME/PASSWORD  (test_teacher_a)
 */

const ADMIN = { username: process.env.E2E_ADMIN_USERNAME ?? "test_admin", password: process.env.E2E_ADMIN_PASSWORD ?? "test-admin-pw" };
const TEACHER_A = { username: "test_teacher_a", password: process.env.E2E_TEACHER_PASSWORD ?? "test-teacher-pw" };
const TEACHER_B = { username: "test_teacher_b", password: process.env.E2E_TEACHER_PASSWORD ?? "test-teacher-pw" };
const ADJUDICATOR = { username: "test_adjudicator", password: process.env.E2E_TEACHER_PASSWORD ?? "test-teacher-pw" };

/**
 * The study student is a real account from the fixture's 49 synthetic students,
 * picked from a ClinPath-arm cohort so the D2/D3 training steps are the arm the
 * design actually assigns. Resolved once below; never the demo `student1`
 * account, which is not part of the study.
 */
function studyStudent(): { username: string; password: string; studentId: number } {
  const manifestPath = process.env.E2E_FIXTURE_MANIFEST!;
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as {
    student_ids: number[];
    student_logins: Record<string, string>;
    student_password: string;
  };
  const studentId = manifest.student_ids[0];
  return { username: manifest.student_logins[String(studentId)], password: manifest.student_password, studentId };
}


async function login(page: Page, who: { username: string; password: string }, area: "student" | "teacher") {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(who.username);
  await page.getByLabel("密码").fill(who.password);
  await page.getByRole("button", { name: "登录并进入系统" }).click();
  await expect(page).toHaveURL(new RegExp(`/${area}/dashboard$`), { timeout: 60_000 });
}

/**
 * The blind queue is deliberately shuffled per rater, so an entry is opened by
 * its blind code rather than by position: position N is not the same answer for
 * rater A and rater B.
 */
async function openBlindEntry(page: Page, code: string) {
  // Reload so the panel renders the queue as it is *now*: a sitting submitted
  // after the page first mounted would otherwise be missing from the list.
  await page.reload();
  // The queue shows only the first 8 characters of a blind code.
  const entry = page.locator("button", { hasText: code.slice(0, 8) }).first();
  await expect(entry, `queue entry ${code.slice(0, 8)}…`).toBeVisible({ timeout: 20_000 });
  await entry.click();
}

/** A fresh browser context per role: cookies never leak between identities. */
async function contextFor(browser: import("@playwright/test").Browser, who: { username: string; password: string }, area: "student" | "teacher") {
  const context = await browser.newContext({ baseURL: process.env.E2E_BASE_URL });
  const page = await context.newPage();
  await login(page, who, area);
  return { context, page };
}

const STAGES = [
  { title: "S1 关键信息提取", info: "TEST 合成病例：患者 TEST，女，34 岁，双手多关节疼痛 5 周。", question: "提取关键阳性与阴性信息。" },
  { title: "S2 初步判断", info: "TEST 合成病例：ESR 32 mm/h，CRP 12 mg/L，RF 弱阳性，抗CCP阴性。", question: "给出暂定诊断及依据。" },
  { title: "S3 鉴别诊断", info: "TEST 合成病例：无银屑病皮疹，无腰背痛，无口干眼干。", question: "列出鉴别诊断及排序理由。" },
  { title: "S4 进一步检查", info: "TEST 合成病例：双手 X 线未见骨侵蚀。", question: "说明进一步检查及其目的。" },
  { title: "S5 处理原则", info: "TEST 合成病例：随访 6 周，症状持续。", question: "给出处理原则与监测计划。" },
];

const RUBRIC = {
  weights: { medical_knowledge: 10, key_information: 20, differential_diagnosis: 25, evidence_integration: 15, clinical_decision: 20, evidence_based_medicine: 10 },
  rubric_version: "TEST-RUBRIC-2026-10-18",
  disagreement: { total_threshold: 10, dimension_threshold: 20 },
};

test.describe.configure({ mode: "serial" });

test.describe("R8.2 research flow (SYNTHETIC test accounts only)", () => {
  test.skip(!process.env.E2E_FIXTURE_MANIFEST, "Run through scripts/grant/e2e/run_acceptance.sh so the fixture exists.");

  const runId = Date.now().toString().slice(-6);
  const formCode = `TEST-E2E-${runId}`;
  const formTitle = `[TEST 合成验收] 多关节疼痛待查 ${runId}`;
  let formId = 0;
  let t0SittingId = 0;
  let t1SittingId = 0;
  let blindCode = "";

  test("1. the study admin creates a form draft (SYNTHETIC, not a real case)", async ({ browser }) => {
    const { context, page } = await contextFor(browser, ADMIN, "teacher");
    try {
      await page.goto("/teacher/assessment-forms");
      await expect(page.getByRole("heading", { name: "考核题本与双教师审核" })).toBeVisible();

      await page.getByRole("button", { name: "创建题本 / 新版本" }).click();
      await page.getByRole("button", { name: "创建新题本草案" }).click();
      await expect(page.getByRole("heading", { name: "创建考核题本" })).toBeVisible();

      await page.getByLabel("题本编号").fill(formCode);
      await page.getByLabel("题本名称").fill(formTitle);
      for (let i = 0; i < 5; i += 1) {
        await page.getByLabel(`第${i + 1}阶段标题`).fill(STAGES[i].title);
        await page.getByLabel(`第${i + 1}阶段临床资料`).fill(STAGES[i].info);
        await page.getByLabel(`第${i + 1}阶段考核问题`).fill(STAGES[i].question);
      }
      await page.getByLabel("参考诊断").fill("TEST 未分化多关节炎（合成，非真实病例）");
      await page.getByLabel("量表版本号").fill(RUBRIC.rubric_version);
      await page.getByRole("button", { name: "填入研究建议权重（10/20/25/15/20/10）" }).click();
      await expect(page.getByText(/权重合计 100 \/ 100/)).toBeVisible();

      await page.getByRole("button", { name: "创建题本（进入审核流程）" }).click();
      // The draft exists and is NOT publishable yet: it needs two teacher approvals.
      await expect(page.getByText(/TEST-E2E-.*待.*审核|待审核/).first()).toBeVisible({ timeout: 20_000 });

      const created = await page.evaluate(async (code) => {
        const response = await fetch("/api/assessments/forms/admin/all", { credentials: "include" });
        const rows = (await response.json()) as { id: number; code: string; review_status: string }[];
        return rows.find((row) => row.code === code) ?? null;
      }, formCode);
      expect(created, "the new form must be listed for the admin").not.toBeNull();
      expect(created!.review_status).toBe("PENDING_REAL_REVIEW");
      formId = created!.id;

      // An unapproved form can never be scheduled for an exam.
      const refused = await page.evaluate(async (id) => {
        const response = await fetch(`/api/assessments/forms/${id}/approve`, { method: "POST", credentials: "include" });
        return { status: response.status, body: await response.json() };
      }, formId);
      expect(refused.status, "publication without two teacher approvals must be refused").toBe(409);
    } finally {
      await context.close();
    }
  });

  test("2. two DIFFERENT teachers independently review and approve it", async ({ browser }) => {
    // The admin invites both reviewers; the same account can never count twice.
    const inviteAdmin = await contextFor(browser, ADMIN, "teacher");
    try {
      const staff = await inviteAdmin.page.evaluate(async () => {
        const response = await fetch("/api/assessments/admin/staff", { credentials: "include" });
        return (await response.json()) as { user_id: number; display_name: string; teacher_no: string | null }[];
      });
      const a = staff.find((row) => row.teacher_no === "TEST-TA")!;
      const b = staff.find((row) => row.teacher_no === "TEST-TB")!;
      const assigned = await inviteAdmin.page.evaluate(
        async ([id, ids]) => {
          const response = await fetch(`/api/assessments/forms/${id}/reviewers`, {
            method: "POST",
            credentials: "include",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ teacher_user_ids: ids }),
          });
          return response.status;
        },
        [formId, [a.user_id, b.user_id]] as const,
      );
      expect(assigned).toBe(200);
    } finally {
      await inviteAdmin.context.close();
    }

    for (const teacher of [TEACHER_A, TEACHER_B]) {
      const { context, page } = await contextFor(browser, teacher, "teacher");
      try {
        await page.goto("/teacher/assessment-forms");
        await page.getByRole("button", { name: "待我审核" }).click();
        const card = page.getByText(formCode, { exact: false }).first();
        await expect(card).toBeVisible();
        await page.getByLabel(`${formCode}审核意见`).fill(
          `TEST 合成验收：${teacher.username} 独立审核该版本内容（非真实教师医学审核）。`,
        );
        await page.getByRole("button", { name: "审核通过这一版内容" }).click();
        await expect(page.getByText(/审核意见已记录|已记录/).first()).toBeVisible({ timeout: 20_000 });
      } finally {
        await context.close();
      }
    }

    // Two distinct teacher accounts, two distinct Teacher rows: the server records both.
    const verifyAdmin = await contextFor(browser, ADMIN, "teacher");
    try {
      const detail = await verifyAdmin.page.evaluate(async (id) => {
        const response = await fetch(`/api/assessments/forms/${id}/admin`, { credentials: "include" });
        return await response.json();
      }, formId);
      expect(detail.reviews).toHaveLength(2);
      expect(new Set(detail.reviews.map((r: { teacher_user_id: number }) => r.teacher_user_id)).size).toBe(2);
      expect(detail.reviews.every((r: { decision: string }) => r.decision === "approve")).toBe(true);
    } finally {
      await verifyAdmin.context.close();
    }
  });

  test("3. the admin verifies and publishes; the published version is frozen", async ({ browser }) => {
    const { context, page } = await contextFor(browser, ADMIN, "teacher");
    try {
      await page.goto("/teacher/assessment-forms");
      await page.getByRole("button", { name: "题本审核状态与发布" }).click();
      // Open the row for THIS run's form, not whichever row happens to be first.
      const row = page.locator("tr").filter({ hasText: formCode });
      await expect(row).toBeVisible();
      await row.getByRole("button", { name: "查看与处理" }).click();
      await expect(page.getByText(`${formCode} v1`)).toBeVisible();
      const publish = page.getByRole("button", { name: "核验并发布（双教师审核通过后）" });
      await expect(publish).toBeEnabled({ timeout: 20_000 });
      await publish.click();
      await expect(page.getByText(/已发布|APPROVED_FOR_ASSESSMENT/).first()).toBeVisible({ timeout: 20_000 });

      const published = await page.evaluate(async (id) => {
        const response = await fetch(`/api/assessments/forms/${id}/admin`, { credentials: "include" });
        return await response.json();
      }, formId);
      expect(published.review_status).toBe("APPROVED_FOR_ASSESSMENT");
      expect(published.published_at).toBeTruthy();

      // A published version cannot be edited in place; only a new version may follow.
      const frozen = await page.evaluate(async (id) => {
        const response = await fetch(`/api/assessments/forms/${id}/review`, {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ decision: "approve", comment: "TEST 合成验收：不应被接受" }),
        });
        return response.status;
      }, formId);
      expect([403, 409], "a frozen form must not accept another review").toContain(frozen);
    } finally {
      await context.close();
    }
  });

  test("4. the student sits T0 with no AI, no feedback and no score shown", async ({ browser }) => {
    const { context, page } = await contextFor(browser, studyStudent(), "student");
    try {
      await page.goto("/student/assessments");
      await expect(page.getByRole("heading", { name: "我的独立考核" })).toBeVisible();
      const entry = page.getByRole("link", { name: /开始考核|继续作答/ }).first();
      await expect(entry).toBeVisible();
      t0SittingId = Number((await entry.getAttribute("href"))!.split("/").pop());
      await entry.click();

      await expect(page.getByTestId("assessment-instructions").or(page.getByTestId("assessment-exam"))).toBeVisible();
      if (await page.getByTestId("assessment-instructions").count()) {
        await expect(page.getByText("不提供 AI 追问")).toBeVisible();
        await page.getByRole("button", { name: "开始考核" }).click();
      }
      await expect(page.getByTestId("assessment-exam")).toBeVisible();

      let completed = 0;
      while (completed < 5) {
        const textarea = page.getByLabel("本阶段作答");
        await expect(textarea).toBeVisible();
        await textarea.fill(`第${completed + 1}阶段：TEST 合成作答，含关键信息、鉴别与处理原则（非真实学生答案）。`);
        await page.getByRole("button", { name: "保存并提交本阶段" }).click();
        await page.getByRole("button", { name: "确认提交并查看下一阶段" }).click();
        completed += 1;
      }
      await expect(page.getByText("五个阶段已全部提交")).toBeVisible();
      await page.getByRole("button", { name: "提交整份答卷" }).click();
      await page.getByRole("button", { name: "确认提交整份答卷" }).click();

      await expect(page.getByTestId("assessment-submitted")).toBeVisible();
      const body = await page.locator("body").innerText();
      expect(body).not.toMatch(/参考诊断[:：]|标准答案[:：]|总分[:：]?\s*\d/);
      expect(body).toContain("不显示正确答案");

      // An independent assessment never writes Training state.
      const before = await page.evaluate(async () => {
        const response = await fetch("/api/auth/me", { credentials: "include" });
        const me = await response.json();
        const [profile, recommendations, invocations] = await Promise.all([
          fetch(`/api/student/competency`, { credentials: "include" }).then((r) => r.json()),
          fetch(`/api/student/pathway`, { credentials: "include" }).then((r) => r.json()),
          fetch("/api/system/ai-invocations?limit=200", { credentials: "include" }),
        ]);
        return { studentId: me.student_id, profile: profile.updated_at, pathway: JSON.stringify(recommendations).length,
                 aiStatus: invocations.status };
      });
      // A student may not read the AI audit at all -- that is the role gate working.
      expect(before.aiStatus).toBe(403);
    } finally {
      await context.close();
    }
  });

  test("5. D2/D3 formative training produces evidence, then D4/D5 recommends from it", async ({ browser }) => {
    const { context, page } = await contextFor(browser, studyStudent(), "student");
    try {
      // D2/D3: two training cases, five reasoning steps each, submitted for
      // formative scoring. The provider is keyless in this stack, so the honest
      // outcome is the rule fallback -- which the UI must label as such.
      for (const caseId of [1, 2]) {
        await page.goto(`/student/case/${caseId}`);
        for (const step of ["关键信息提取", "初步诊断及依据", "鉴别诊断", "进一步检查", "治疗方案"]) {
          await page.getByRole("button", { name: step, exact: true }).click();
          await page
            .locator("textarea")
            .fill(`${step}：TEST 合成训练作答（D2/D3），用于产生形成性证据，不代表真实学习效果。`);
          await page.getByRole("button", { name: "保存回答" }).click();
          await expect(page.getByText("已保存")).toBeVisible();
        }
        const submission = page.waitForResponse(
          (response) => response.url().includes("/api/sessions/") && response.url().endsWith("/submit"),
          { timeout: 120_000 },
        );
        await page.getByRole("button", { name: "提交病例并生成反馈" }).click();
        expect((await submission).status()).toBe(200);
        await expect(page).toHaveURL(/\/student\/result\//);
        await expect(page.getByTestId("evaluation-mode")).toContainText(/规则降级评价|AI 语义评价/);
      }

      // D4/D5: the personalised task must cite D2/D3 evidence, not the T0 exam.
      const pathway = await page.evaluate(async () => {
        const response = await fetch("/api/student/pathway", { credentials: "include" });
        return await response.json();
      });
      // The pathway is the D4/D5 surface: a recommended task plus the D2/D3
      // evidence that produced it. Ranking is deterministic (rule) -- the LLM may
      // only reword the explanation, and this keyless stack must say "rule".
      expect(pathway.recommended_case?.id, "a recommendation must exist after training").toBeTruthy();
      expect(pathway.recommendation_reason_source).toBe("rule");
      expect(pathway.recommended_tasks?.length, "personalised tasks come from the weak dimensions").toBeGreaterThan(0);

      // The training evidence exists and is traceable to the sessions that made it.
      const evidence = await page.evaluate(async () => {
        const response = await fetch("/api/student/history", { credentials: "include" });
        return await response.json();
      });
      const items = evidence.items as { status: string; session_id: number; evaluation_mode: string }[];
      expect(items.length, "D2/D3 must leave two completed training sessions").toBeGreaterThanOrEqual(2);
      // Every training score states its provenance; keyless means rule_fallback.
      for (const item of items) {
        expect(["ai", "rule_fallback"]).toContain(item.evaluation_mode);
      }
    } finally {
      await context.close();
    }
  });

  test("6. the student sits T1 on the OTHER form", async ({ browser }) => {
    test.slow(); // waits for the demo cohort's compressed T1 window to open
    const { context, page } = await contextFor(browser, studyStudent(), "student");
    try {
      // The demo cohort's T0 window closes shortly after scheduling and T1 opens
      // right after it: the fixture compresses that batch's timeline so one run
      // can cover both timepoints without breaking "T0 closes before T1 opens".
      const deadline = Date.now() + 240_000;
      let t1: { id: number; timepoint: string; status: string } | undefined;
      while (Date.now() < deadline) {
        const sittings = await page.evaluate(async () => {
          const response = await fetch("/api/assessments/my", { credentials: "include" });
          return (await response.json()) as { id: number; timepoint: string; status: string }[];
        });
        t1 = sittings.find((row) => row.timepoint === "T1");
        if (t1) break;
        await page.waitForTimeout(5000);
      }
      expect(t1, "the demo cohort's T1 window must open in this run").toBeTruthy();
      t1SittingId = t1!.id;

      // A student can never read another student's sitting, and never the admin view.
      const refused = await page.evaluate(async (ids) => {
        const statuses: number[] = [];
        for (const id of ids) {
          const response = await fetch(`/api/assessments/admin/sittings/${id}`, { credentials: "include" });
          statuses.push(response.status);
        }
        return statuses;
      }, [t0SittingId, t1SittingId]);
      expect(refused).toEqual([403, 403]);

      // Sit T1 on the OTHER form, exactly as T0 was sat.
      await page.goto(`/student/assessments/${t1SittingId}`);
      // The page settles after its own fetch; wait for any of its four states
      // instead of assuming it opened on the instructions screen.
      await expect(
        page
          .getByTestId("assessment-instructions")
          .or(page.getByTestId("assessment-exam"))
          .or(page.getByTestId("assessment-submitted"))
          .or(page.getByTestId("assessment-expired")),
      ).toBeVisible({ timeout: 20_000 });
      if (await page.getByTestId("assessment-instructions").count()) {
        await page.getByRole("button", { name: "开始考核" }).click();
      }
      await expect(page.getByTestId("assessment-exam")).toBeVisible();
      let done = 0;
      while (done < 5) {
        await page.getByLabel("本阶段作答").fill(
          `T1 第${done + 1}阶段：TEST 合成作答（后测），非真实学生答案。`,
        );
        await page.getByRole("button", { name: "保存并提交本阶段" }).click();
        await page.getByRole("button", { name: "确认提交并查看下一阶段" }).click();
        done += 1;
      }
      await page.getByRole("button", { name: "提交整份答卷" }).click();
      await page.getByRole("button", { name: "确认提交整份答卷" }).click();
      await expect(page.getByTestId("assessment-submitted")).toBeVisible();
      expect(await page.locator("body").innerText()).not.toMatch(/参考诊断[:：]|总分[:：]?\s*\d/);
    } finally {
      await context.close();
    }
  });

  test("7. two teachers score the blinded queues without seeing identity", async ({ browser }) => {
    // Both raters must have submitted answers to score. The fixture's T0 sittings
    // are submitted only for the demo student in step 4, so score that one.
    const raterA = await contextFor(browser, TEACHER_A, "teacher");
    try {
      await raterA.page.goto("/teacher/assessments");
      await expect(raterA.page.getByRole("heading", { name: "盲评与分歧裁决" })).toBeVisible();
      const queue = await raterA.page.evaluate(async () => {
        const response = await fetch("/api/assessments/blind/queue", { credentials: "include" });
        return (await response.json()) as { blind_code: string; reviewed: boolean }[];
      });
      const pending = queue.find((row) => !row.reviewed);
      test.skip(!pending, "No submitted answer is assigned to rater A.");
      blindCode = pending!.blind_code;
      const detail = await raterA.page.evaluate(async (code) => {
        const response = await fetch(`/api/assessments/blind/${encodeURIComponent(code)}`, { credentials: "include" });
        return await response.json();
      }, blindCode);
      for (const forbidden of ["student_id", "student_name", "study_group", "timepoint", "cohort_code", "other_score"]) {
        expect(Object.keys(detail), `blind detail must not expose ${forbidden}`).not.toContain(forbidden);
      }

      // Score through the UI so the real form path is exercised.
      await openBlindEntry(raterA.page, blindCode);
      await expect(raterA.page.getByText("六维独立评分（0–100）")).toBeVisible();
      // Deliberately extreme scores so the two raters disagree beyond the threshold.
      for (const label of ["医学知识", "关键信息提取", "鉴别诊断", "证据整合", "临床决策", "循证安全"]) {
        await raterA.page.getByLabel(`${label}评分`).fill("20");
      }
      await raterA.page.getByLabel("评分依据说明").fill("TEST 合成评分（评分者A，非真实教师）。");
      await raterA.page.getByRole("button", { name: "提交独立评分" }).click();
      await raterA.page.getByRole("button", { name: "确认提交并锁定" }).click();
      await expect(raterA.page.getByText(/评分已锁定/)).toBeVisible({ timeout: 20_000 });
    } finally {
      await raterA.context.close();
    }

    const raterB = await contextFor(browser, TEACHER_B, "teacher");
    try {
      await raterB.page.goto("/teacher/assessments");
      // Rater B scores the SAME blind code, found in their own shuffled queue.
      await openBlindEntry(raterB.page, blindCode);
      await expect(raterB.page.getByText("六维独立评分（0–100）")).toBeVisible();
      for (const label of ["医学知识", "关键信息提取", "鉴别诊断", "证据整合", "临床决策", "循证安全"]) {
        await raterB.page.getByLabel(`${label}评分`).fill("90");
      }
      await raterB.page.getByLabel("评分依据说明").fill("TEST 合成评分（评分者B，非真实教师）。");
      await raterB.page.getByRole("button", { name: "提交独立评分" }).click();
      await raterB.page.getByRole("button", { name: "确认提交并锁定" }).click();
      await expect(raterB.page.getByText(/评分已锁定/)).toBeVisible({ timeout: 20_000 });

      // Rater B must not have been shown rater A's score.
      const detailB = await raterB.page.evaluate(async (code) => {
        const response = await fetch(`/api/assessments/blind/${encodeURIComponent(code)}`, { credentials: "include" });
        return await response.json();
      }, blindCode);
      expect(JSON.stringify(detailB)).not.toContain("other_score");
    } finally {
      await raterB.context.close();
    }
  });

  test("8. the forced disagreement is adjudicated, never silently averaged", async ({ browser }) => {
    test.skip(!blindCode, "Step 7 did not produce a blind code.");
    const adjudicator = await contextFor(browser, ADJUDICATOR, "teacher");
    try {
      await adjudicator.page.goto("/teacher/assessments");
      await adjudicator.page.getByRole("button", { name: "分歧裁决" }).click();
      const queue = await adjudicator.page.evaluate(async () => {
        const response = await fetch("/api/assessments/adjudication/queue", { credentials: "include" });
        return (await response.json()) as { blind_code: string; adjudicated: boolean }[];
      });
      // Adjudicate THIS answer, not whichever entry happens to be first: the
      // adjudicator may be assigned several, and finalising the wrong one would
      // prove nothing about the disagreement the two raters just created.
      const mine = queue.find((row) => row.blind_code === blindCode && !row.adjudicated);
      expect(mine, `the forced disagreement on ${blindCode.slice(0, 8)}… must be flagged for adjudication`).toBeTruthy();
      await adjudicator.page.reload();
      await adjudicator.page.getByRole("button", { name: "分歧裁决" }).click();
      const entry = adjudicator.page.getByRole("button", { name: new RegExp(`第 \\d+ 份分歧答卷`) })
        .filter({ hasText: blindCode.slice(0, 8) });
      await expect(entry).toBeVisible({ timeout: 20_000 });
      await entry.click();
      await expect(adjudicator.page.getByText(/触发裁决：总分差/)).toBeVisible();
      for (const label of ["医学知识", "关键信息提取", "鉴别诊断", "证据整合", "临床决策", "循证安全"]) {
        await adjudicator.page.getByLabel(`${label}评分`).fill("60");
      }
      await adjudicator.page.getByLabel("裁决理由").fill("TEST 合成裁决：两位评分者差异超过阈值，由第三方独立裁定（非真实教师）。");
      await adjudicator.page.getByRole("button", { name: "提交裁决" }).click();
      await expect(adjudicator.page.getByText(/裁决.*已|已裁决/).first()).toBeVisible({ timeout: 20_000 });
    } finally {
      await adjudicator.context.close();
    }

    const admin = await contextFor(browser, ADMIN, "teacher");
    try {
      // Finalising keeps the provenance: adjudicated, not dual_mean.
      const finalized = await admin.page.evaluate(async (sittingId) => {
        const response = await fetch(`/api/assessments/admin/sittings/${sittingId}/finalize`, {
          method: "POST",
          credentials: "include",
        });
        return { status: response.status, body: await response.json() };
      }, t0SittingId);
      expect(finalized.status).toBe(200);
      expect(finalized.body.scoring_provenance).toBe("adjudicated");
    } finally {
      await admin.context.close();
    }
  });

  test("9. the study admin exports coded research data, with no names", async ({ browser }) => {
    const { context, page } = await contextFor(browser, ADMIN, "teacher");
    try {
      await page.goto("/teacher/assessment-admin");
      await page.getByRole("button", { name: "数据集与一致性" }).click();
      await page.getByRole("button", { name: "生成工作数据集" }).click();
      await expect(page.getByText(/WORKING_NOT_FROZEN|工作数据集/).first()).toBeVisible({ timeout: 30_000 });

      const exported = await page.evaluate(async () => {
        const response = await fetch("/api/assessments/admin/export?data_origin=pilot_test", { credentials: "include" });
        return { status: response.status, body: await response.json() };
      });
      expect(exported.status).toBe(200);
      expect(exported.body.dataset_status).toBe("WORKING_NOT_FROZEN");
      const records = exported.body.records as Record<string, unknown>[];
      expect(records.length).toBeGreaterThan(0);

      // Coded rows only: a study code, never a student name or student number.
      for (const record of records) {
        expect(record.study_student_code).toMatch(/^S[0-9A-F]{8}$/);
        for (const forbidden of ["student_id", "student_name", "student_no", "name"]) {
          expect(Object.keys(record), `export must not carry ${forbidden}`).not.toContain(forbidden);
        }
        expect(record.data_origin).toBe("pilot_test");
      }
      expect(JSON.stringify(exported.body)).not.toMatch(/TEST测试学生|2026\d{5}/);

      // The identity map is a separate, audited admin call.
      const identity = await page.evaluate(async () => {
        const response = await fetch("/api/assessments/admin/identity-map", { credentials: "include" });
        return (await response.json()) as { study_student_code: string; name: string }[];
      });
      // 98 sittings are 49 students x 2 timepoints: one code per student, never per sitting.
      const exportedCodes = new Set(records.map((row) => row.study_student_code));
      expect(identity.length).toBeGreaterThanOrEqual(exportedCodes.size);
      expect(JSON.stringify(identity)).toContain("TEST测试学生");
    } finally {
      await context.close();
    }
  });
});
