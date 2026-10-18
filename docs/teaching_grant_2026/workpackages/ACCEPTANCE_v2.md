# 第二轮独立验收（ACCEPTANCE v2）

> 环境：**隔离验收栈**，非生产。生产 `8100/8101` 与 `backend/clinical_learning.db` **未被触碰**。
> 日期：2026-10-18
>
> **两段运行，都保留**：
> §1–§6 是**旧验收栈**（8201/8202、`verify-r2.db`，数据 1/1/1），`demo-readiness`
> 因数据前置条件失败；**§7 是满足前置条件后的重跑（新栈 8204/8205 + 一次性数据集），
> 三个 spec 合计 12/12 通过**。保留两段是为了让评审者看清"失败是因为数据，不是代码"。

## 1. 验收环境

| 项目 | 值 |
| --- | --- |
| 分支 | `teaching-grant-2026-wpd`（未合并、未部署） |
| 后端 | `uvicorn 127.0.0.1:8201`，`DATABASE_URL=/tmp/clinpath-demo-verify/verify-r2.db` |
| 前端 | `next start 127.0.0.1:8202`，`NEXT_DIST_DIR=.next-accept`（**独立构建目录**） |
| schema | `20261018_07`（含本轮新增迁移） |
| 账号 | `verify_teacher`（一次性库中创建）、`student1`（seed 演示账号） |
| 生产 | 仍运行 `1d4ef48`，`/api/health` 正常，`frontend/.next` 未改动 |

### 为什么用独立 `NEXT_DIST_DIR`

第一轮曾因在仓库内直接 `npm run build` 覆盖了生产服务读取的 `frontend/.next`，
导致公网入口短暂 502。本轮验收强制使用 `.next-accept`（已被 `.gitignore` 的
`frontend/.next*/` 覆盖），验收结束后可整体删除，生产构建产物零接触。

## 2. 数据集前置条件

`demo-readiness.spec.ts` 的「研究数据预览」用例要求至少 3 名学生、3 个模块、3 个日期。
一次性验证库只有 1/1/1，因此该用例在第一轮失败。

本轮处理：把上一轮已产生的真实学习记录（1 次病例训练、1 次教师复核、2 条证据事件、
6 条 AI 调用审计）复制进迁移后的新库，并额外补入 AI 审计行。
**仍未满足 3/3/3**——本轮没有为了"让测试变绿"而伪造 3 名学生 × 3 模块的学习记录。
该用例的失败被如实记录在 §3，而不是用合成数据掩盖。

复现脚本：`scripts/grant/make_acceptance_dataset.py`
（只允许写 `/tmp` 下的文件；拒绝 `backend/clinical_learning.db` 与任何非 `/tmp` 路径）。

## 3. 测试结果（真实输出）

```text
cd frontend
E2E_BASE_URL=http://127.0.0.1:8202 \
E2E_TEACHER_USERNAME=verify_teacher E2E_TEACHER_PASSWORD=... \
npx playwright test tests/e2e/teacher.spec.ts tests/e2e/research-demo.spec.ts
```

```text
Running 6 tests using 1 worker
  ✓ teacher surfaces load without console errors or 5xx
  ✓ a teacher can probe the AI runtime without leaking secrets
  ✓ teacher logout clears access and the audit rollup lists real invocations
  ✓ a teacher sees the synthetic banner and downloads the SYNTHETIC CSV
  ✓ a student is redirected away and the API answers 403
  ✓ the real research export is unchanged and still offers its own CSV
  6 passed (10.1s)
```

| 规格 | 通过 | 失败 | 说明 |
| --- | --- | --- | --- |
| `research-demo.spec.ts` | 3 | 0 | 合成横幅、CSV 标记、学生 403、真实导出分离 |
| `teacher.spec.ts` | 3 | 0 | 页面无 5xx、运行状态无密钥、登出与审计 |
| `demo-readiness.spec.ts` | 5 | 1 | 失败项为数据量前置条件（见 §2），**不是代码回归** |
| 后端 `pytest` | 235 | 0 | 含本轮新增 7 个评分来源用例 |
| `check_case_cards.py` | 88/88 | 0 | 六份病例卡结构校验 |
| `check_application_text.py` | 6/6 栏 | 0 | 申报书六栏字数 |
| `rubric_agreement.py`（空真实表） | — | exit 2 | 护栏：无真实评分时拒绝出数 |

### `demo-readiness` 失败项的完整说明

```text
验证库 /tmp/clinpath-demo-verify/verify-r2.db
  有证据学生数 1   模块 ['case']   日期数 1
生产库 backend/clinical_learning.db（未用于验收）
  有证据学生数 4   模块 5 种        日期数 17
```

该用例的设计前提是演示库已被 `scripts/prepare_presentation_data.py` 填充，
或本身就是生产演示库。验收栈两者都不是。**未修改测试阈值来让它通过。**

## 4. 工作包 D 隔离仍然成立

```text
cd backend && uv run --python 3.11 --with-requirements requirements.txt \
  pytest -q tests/test_demo_research.py
```

```text
16 passed
```

- 合成数据仍在 `demo_research/synthetic_v1/`，未因本轮改动移动或改写。
- 路由与服务仍不 import ORM / DB 会话；调用 7 个端点前后业务表行数不变。
- 页面顶部合成横幅、CSV 文件名与逐行标记均保持。

## 5. 生产未被触碰的证明

| 检查 | 结果 |
| --- | --- |
| `curl http://127.0.0.1:8100/api/system/version` | `git_sha_short=1d4ef482`，`schema=20260915_06` |
| `curl https://clinpath.1031989.xyz/api/health` | `{"status":"ok"}` |
| `grep 127.0.0.1:8100 frontend/.next/routes-manifest.json` | 命中（生产构建产物仍指向生产后端） |
| `backend/clinical_learning.db` 行数 | 未变（未对其执行任何写入或迁移） |
| 生产迁移 | **未执行**；新迁移只在 `/tmp` 副本上验证过 |

## 6. 本轮未通过的项

| 项目 | 原因 | 处理 |
| --- | --- | --- |
| `demo-readiness` 数据量用例 | 验收库数据不足 | 如实记录；建议在部署后用生产演示库跑该用例 |
| 真实 AI 评分路径 | provider 在验收栈中超时 | 不作为本轮验收目标 |
| 生产部署验收 | 本轮明确不部署 | 由用户在复核后决定 |

---

## 7. 满足前置条件后的重跑（覆盖 §3、§6 中 demo-readiness 的结论）

### 7.1 新验收栈

| 项目 | 值 |
| --- | --- |
| 后端 | `uvicorn 127.0.0.1:8205`，`DATABASE_URL=/tmp/clinpath-accept/acceptance.db` |
| 前端 | `next start 127.0.0.1:8204`，独立构建目录 |
| schema | `20261018_07` |
| 账号 | `accept_teacher`（一次性库）、`student1`（seed 演示账号） |
| 数据集 | 由 `scripts/grant/make_acceptance_dataset.py` 通过**真实路由**创建 |

### 7.2 数据集前置条件（实测）

```text
students with evidence: 3
modules: ['case', 'knowledge', 'skill', 'guideline', 'sp']
distinct dates: 4
schema revision: 20261018_07
```

满足 `demo-readiness` 的「≥3 学生 / ≥3 模块 / ≥3 日期」要求。
数据集只存在于 `/tmp/clinpath-accept/`，脚本拒绝写入 `backend/clinical_learning.db`
或任何非 `/tmp` 路径。

### 7.3 测试结果（真实输出）

```text
cd frontend
E2E_BASE_URL=http://127.0.0.1:8204 \
E2E_TEACHER_USERNAME=accept_teacher E2E_TEACHER_PASSWORD=<throwaway> \
E2E_STUDENT_USERNAME=student1 E2E_STUDENT_PASSWORD=<throwaway> \
npx playwright test tests/e2e/demo-readiness.spec.ts tests/e2e/teacher.spec.ts \
  tests/e2e/research-demo.spec.ts
```

```text
Running 12 tests using 1 worker
  ✓ demo-readiness × 6   (含「研究数据 preview … diverse」)
  ✓ teacher × 3
  ✓ research-demo × 3
  12 passed (17.4s)
```

### 7.4 结论

- 上一轮失败的 `demo-readiness` 用例**在数据满足前置条件后通过**，
  证实失败原因是数据量而非代码回归。
- §3、§6 中"`demo-readiness` 未通过"的表述仅对旧验收栈成立。
- 生产仍未部署本批改动。
