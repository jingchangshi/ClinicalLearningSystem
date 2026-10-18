# 测试报告（TEST_REPORT）

> **最终版**（2026-10-18，牵头成员在集成后以最终 SHA 重跑并填写）。
> 只记录**实际执行**的检查及其真实输出。未执行的项目一律写「未执行」，**不得视为通过**。
> 交付 SHA：`f2b32d8`（分支 `feat/clinpath-final-2026`，worktree `/home/jcshi/workspace/clinpath-final`）。

## 1. 后端全量测试（已执行，最终）

| 项 | 值 |
| --- | --- |
| 命令 | `cd backend && uv run --python 3.11 --with-requirements requirements.txt pytest -q -p no:cacheprovider` |
| 结果 | **425 passed，0 failed**，1 warning（既有 starlette TestClient 弃用告警），465.99 s |
| 时间 | 2026-10-18 17:0x UTC |
| 日志 | `../evidence/E2_platform/test_runs/backend_pytest_f2b32d8.log` |
| 稳定性 | 运行期间 `backend/` 无改动（`git diff --stat b471463..f2b32d8 -- backend/` 为空），计数属于该树 |

### 1.1 历史运行（保留作对比，均已被上面取代）

| SHA | 结果 | 说明 |
| --- | --- | --- |
| `47f7e6d` | 307 passed / 5 failed / 1 xfailed | 早期；失败含测试自身 `NameError` 与过期迁移断言 |
| `f7f737c` | 329 passed / 1 failed / 1 xfailed | `test_version_endpoint` 的 `schema_revision=None` |
| `2fd5558` | 416 passed | 后端成员报告；**不含** staff/my-forms 接口 |
| `28c8081` | 424 passed | 含接口与驾驶舱修复 |
| `a653662` | 424 passed | 干净树复跑 |
| `f2b32d8` | **425 passed** | 最终 |

> 说明：`xfail` 已全部移除（`grep -rn "xfail\|skip" backend/tests/` 无标记）。
> 旧 `xfail`「考核会话不进入形成性画像」已由**正向**隔离测试取代，见 §1.2。

### 1.2 隔离性正向证明（R8.1）

`backend/tests/test_assessment_isolation.py` 5 项，全部通过：

- 完整考核生命周期后，训练表与 `ai_invocations` 均无新增；
- 训练提交不产生任何 `assessment_*` 行；
- 考核题本无法经普通病例/会话 API 读取；
- 学生响应中不含参考答案、量表与分数；
- **结构证明**：在 `python -I` 隔离子进程中导入考核模块，断言 `app.services`、`app.llm`、
  `app.routes.sessions`、`app.core.ai_*` 等训练/AI 模块**从未被加载**。

### 1.3 角色权限矩阵与越权（R1.3、R8.1）

`tests/test_assessment_permissions.py`（含 `design/assignments`、`design/schedule`、
`forms/mine`、`admin/staff` 四个新增行的角色断言）、`tests/test_assessment_directory.py`
（4 项：目录仅管理员、字段集精确、学生不出现、作者之间互不可见）、
`tests/test_assessment_forms.py`（两名不同教师、管理员不可伪造、未审核不可发布）全部通过。

### 1.4 考试可靠性、双评与裁决（R2.3、R3）

`test_assessment_student_exam.py`（11）、`test_assessment_blind_scoring.py`（15）、
`test_assessment_scheduling.py`、`test_assessment_study_schedule.py`（15）全部通过，
覆盖草稿/断网恢复、幂等重复提交、窗口与时区、超时与中断、受控重考、
盲评身份脱敏与锁分、分歧阈值与裁决记录、以及「未经裁决的分歧不得被悄悄覆盖」
（`finalize` 在分歧超阈值且无裁决时返回 409 `adjudication_required`）。

### 1.5 7 批 49 人批量编排（R4）

`test_assessment_study_schedule.py`：一次调用为 7 批 × 7 人创建 **98 份考次**；
每人 T0/T1 严格按其冻结的 X/Y 顺序；批内约 4/3；**两处真实的中途失败**证明
不留下部分考次与部分审计行；重复执行幂等、任何差异返回 `schedule_conflict`；
未发布题本被拒且不写入；真实与合成来源分离。

## 2. 前端门禁（已执行，最终树）

| 命令 | 结果 |
| --- | --- |
| `npx tsc --noEmit` | 退出码 0，无输出 |
| `npm run lint`（`eslint . --max-warnings=0`） | 退出码 0，无输出 |
| `npm run build` | 退出码 0：`✓ Compiled successfully in 20.7s`、`Finished TypeScript in 12.5s`、27/27 静态页 |

## 3. 浏览器 E2E（已执行，隔离栈）

隔离栈：后端 `127.0.0.1:8400`、前端 `127.0.0.1:8401`、`/tmp` 一次性 SQLite、
独立 `NEXT_DIST_DIR`，构建期烘焙 `INTERNAL_API_BASE_URL=http://127.0.0.1:8400/api`
（每次运行后核验 `routes-manifest.json`）。完整记录见
`../evidence/E4_validation/RUN_RECORD_2026-10-18.md`。

| 套件 | 结果 |
| --- | --- |
| R8.2 完整研究流程（`research-flow.spec.ts`，单独运行） | **9 passed / 0 failed** |
| 既有 Playwright 套件 | 26 passed，**3 failed**，11 skipped |
| 截图套件 | 4 passed |

R8.2 九步全部在浏览器中跑通：管理员建题本 → 两名不同教师各自审核批准 → 管理员发布 →
学生 T0 → D2/D3 形成性训练 → D4/D5 个性化 → 学生 T1 → 双教师盲评 → 分歧裁决 → 研究导出。

**3 项失败如实记录，未隐藏、未跳过**：`demo-readiness.spec.ts` 的增长趋势图、
≥3 名学生导出预览、学生学习历史表——它们断言一个**预置演示数据集**，而全新 `seed_data`
没有任何已完成的训练；重建该数据集（`scripts/prepare_presentation_data.py`）需要真实模型密钥，
与本轮**刻意无密钥**的设定冲突。

## 4. 7 批 49 人 × 98 份答卷批量流程（已执行）

`scripts/grant/e2e/verify_study_invariants.py` **读取产品自身记录**（而非 fixture 算术）核对：

| 不变量 | 结果 |
| --- | --- |
| I1 7 批 × 7 人 = 49 名互异学生 | 成立 |
| I2 每批同一研究臂；3 ClinPath + 4 CBL；合法整批分配索引 ∈ C(7,3)=35 | 成立 |
| I3 题本顺序冻结时间（16:16:22.101596）**早于**教学组抽取（16:16:22.119085），哈希绑定 | 成立 |
| I4 98 份考次，无 `(学生, 时点)` 重复 | 成立 |
| I5 T0/T1 使用不同题本且遵循各自冻结的 X/Y | 成立 |
| I6 每批内部 X/Y 约 4/3 | 成立 |
| I7 导出 98 行，仅含研究编码，`data_origin=['pilot_test']` | 成立 |

## 5. 数据库迁移验收（已执行）

详见 `../evidence/E2_platform/MIGRATION_ACCEPTANCE.md`。

- 隔离临时库：`upgrade head` → `downgrade 20261018_07` → `upgrade head`；
  **14/14 训练表在每一步逐字节一致**；16 张考核/研究表被删除并重建；
  再升级后的表结构与全新 `create_all` **52 个对象、0 处差异**。
- **生产数据库的只读副本**（revision `20260915_06`，含 816 条 `ai_invocations` 等真实数据）：
  25 张表内容不变；07→head→07→head 往返逐字节一致。副本经 `mode=ro` + `Connection.backup` 取得，
  源文件 `mtime` 保持 `2026-09-15 16:27:09`。
- **发现并修复真实缺陷** `d117899`：`20261018_09` 曾把 `assessment_sittings.created_at`
  建为可空且未恢复 `NOT NULL`，降级再升级后 schema 弱于 ORM；回归测试
  `test_migration_down_up_cycle.py` 在移除修复后确实失败。
- **生产库本身未迁移、未写入**；生产 `/api/system/version` 的 `schema_revision` 全程为 `20260915_06`。

## 6. 申报与病例检查脚本（已执行）

| 脚本 | 结果 |
| --- | --- |
| `check_application_text.py` | 退出码 0；六栏 488/370/900/223/446/619（限 600/600/1000/300/600/800）；23 项内容检查全 PASS |
| `check_protocol_consistency.py` | 退出码 0 |
| `check_case_cards.py` | 退出码 0（88/88） |
| `validate_assessment_payloads.py` | 退出码 0（**30/30**） |
| `audit_exam_leakage.py` | 退出码 0 |

检查脚本自测：`tests/test_grant_checkers.py`（51）+ `tests/test_case_payload_validation.py`（20）
= **71 passed**。

## 7. 未执行（不得视为通过）

| 项 | 原因 |
| --- | --- |
| `training.spec.ts`（8 项）与考核变更类用例 | 需 `E2E_RUN_MUTATING`，本轮未开 |
| 教师干预、数据集冻结的浏览器用例 | 同上 |
| 真实断网（物理断网）恢复 | 仅验证了服务端草稿/恢复语义与前端本地备份 |
| 真实 AI 评分 | 本轮**刻意无模型密钥**；已验证 `rule_fallback` 显式降级路径 |
| `demo-readiness.spec.ts` 3 项 | 需真实模型密钥重建演示数据集（见 §3） |
| 生产部署与部署后浏览器 smoke（R8.4） | 未部署，需申请人明确授权 |
| `./scripts/verify_deploy.sh` | 其前提是「运行源码 == 本检出、schema 在 head」；本轮不部署，故不适用 |

## 8. 重新运行

```bash
# 后端
cd backend && uv run --python 3.11 --with-requirements requirements.txt pytest -q

# 前端门禁
cd frontend && npm ci && npm run typecheck && npm run lint && npm run build

# 隔离栈完整验收（含 E2E、7×49 不变量、截图）
./scripts/grant/e2e/run_full_acceptance.sh final

# 申报/病例检查
python3 scripts/grant/check_application_text.py
python3 scripts/grant/check_protocol_consistency.py
python3 scripts/grant/check_case_cards.py
python3 scripts/grant/validate_assessment_payloads.py
```
