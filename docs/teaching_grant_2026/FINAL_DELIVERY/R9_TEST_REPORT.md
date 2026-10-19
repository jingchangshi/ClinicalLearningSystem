# R9_TEST_REPORT——实际运行测试、失败与未执行项

> 记录时间：2026-10-19。分支 `feat/clinpath-r9-finalization`。
> 只记录**实际执行**的检查及其真实输出。**未执行的一律标注，不得视为通过。**
> 所有验收均在隔离环境执行：独立 worktree、独立端口（8400/8401/8402）、一次性 `/tmp` SQLite、
> 独立 `NEXT_DIST_DIR`、构建期烘焙 API 目标；**未触碰生产 8100/8101、生产库与生产密钥**。

## 0. 冻结与基线

| 项 | 值 |
| --- | --- |
| R9 分支 | `feat/clinpath-r9-finalization` |
| 起点 | `47d191e`（任务书给出的已核实远端 HEAD） |
| 后端验收 SHA | `49f6b9a`（其上仅 `55d44e6` 改 E2E 脚本，不影响后端计数） |
| R9 前基线 | 后端 **425 passed**；前端三门禁通过；R8.2 **9/9**；既有 Playwright **26/3/11**；7×49 不变量 **7/7** |

## 1. 后端全量测试

| 项 | 值 |
| --- | --- |
| 命令 | `cd backend && uv run --python 3.11 --with-requirements requirements.txt pytest -q -p no:cacheprovider` |
| 结果 | **527 passed，0 failed，1 skipped**，584.35 s |
| 日志 | `/tmp/r9-final-backend.log` |
| 相对基线 | 425 → 527（本轮新增 **102** 项） |

**唯一的 skipped**：`tests/test_grant_official_forms.py:28` —— 该模块用 `importorskip("docx")`，
因为 `python-docx` **不是**后端运行时依赖（它只用于申报 Word 产出的核验）。
用 `uv run --with python-docx` 时该文件 **38 项全部通过**（含 11 项 ZIP 专项）。
**这是刻意的**：不接受为了"全绿"而把仅测试期需要的包塞进生产 `requirements.txt`。

## 2. 前端门禁

| 命令 | 结果 |
| --- | --- |
| `npx tsc --noEmit` | 退出码 0 |
| `npm run lint`（`--max-warnings=0`） | 退出码 0 |
| `npm run build` | 退出码 0，`✓ Compiled successfully` |

## 3. 浏览器 E2E（隔离栈，`run_full_acceptance.sh`）

| 套件 | 基线 | 本轮结果 |
| --- | --- | --- |
| 既有 Playwright 套件 | 26 通过 / **3 失败** / 11 跳过 | **40 通过 / 0 失败 / 0 跳过** |
| R8.2 完整研究流程 | 9/9 | **9 通过** |
| E2 证据截图 | 通过 | **通过** |

R8.2 九步全部在浏览器中跑通：管理员建题本 → 两名不同教师各自批准 → 发布 → 学生 T0 →
D2/D3 形成性训练 → D4/D5 个性化 → 学生 T1 → 双教师盲评 → 分歧裁决 → 研究导出。

**3 项原有失败已分类并离线修复**（详见 `R9_PLAYWRIGHT_CLASSIFICATION.md`）：三项全部属于
「可用固定数据离线验证」，**无一项真正依赖模型，也无一项是产品缺陷**。共同根因是验收栈
从未生成演示教学数据集。上一轮"需要真实模型密钥"的前提**对本数据集不成立**。
11 个跳过中 9 个改为真实运行（含把"无 `JWT_SECRET` 时失败关闭"从跳过改为起一台无密钥前端真实观察 503）。

### 3.1 本轮发现并修复的验收可复现性缺陷（重要）

最后一次集成验收时，同一冻结 SHA 上出现 **37 通过 / 3 失败**，与先前报告的 40/0/0 不一致。
查明原因并**不是**随机失败：

- 验收栈内运行的命令（fixture、演示数据集、Playwright）此前拿到的是 `dict(os.environ, …)`，
  因此**继承了操作者的 shell**。本机 shell 导出了真实的 `DEEPSEEK_API_KEY`；
- 后果一：演示数据集生成器按设计**拒绝**在有模型密钥时构建规则回退数据集，于是 3 项
  demo-readiness 用例失败——**看起来像产品缺陷，实际是环境依赖**；
- 后果二：被判分的进程**带着生产凭据**运行，违反任务书 §8.5「不使用生产密钥」。
- 修复（`55d44e6`）：`stack.py` 新增 `keyless()`，栈内命令同样剔除 provider 密钥。
  重跑后 **ALL STEPS PASSED**，且该性质现在由**测试框架**保证，不再靠环境恰好干净。

## 4. 7 批 49 人 × 98 份答卷批量流程

`verify_study_invariants.py` 读取**产品自身记录**核对：**7/7 全部成立**。

| 不变量 | 结果 |
| --- | --- |
| I1 7 批 × 7 人 = 49 名互异学生 | 成立 |
| I2 每批同一研究臂，3 ClinPath + 4 CBL，合法整批分配 | 成立 |
| I3 题本顺序**先冻结**再做教学组抽取，且哈希绑定 | 成立 |
| I4 98 份考次，无 `(学生, 时点)` 重复 | 成立 |
| I5 T0/T1 使用不同题本并遵循各自冻结的 X/Y | 成立（49 名学生 0 处不符） |
| I6 每批内部 X/Y 约 4/3 | 成立（7 批逐一核对） |
| I7 导出 98 行，仅含研究编码，`data_origin=['pilot_test']` | 成立 |

## 5. R9 新增功能的测试

| 功能 | 测试文件 | 项数 | 结果 |
| --- | --- | --- | --- |
| CBL 组训练访问隔离（§3） | `tests/test_study_access_isolation.py` | 13 | **全通过** |
| Research↔Training 只读关联（§4） | `tests/test_research_training_linkage.py` | 13（＋导出槽位端到端） | **全通过** |
| 离线演示数据集守卫 | `tests/test_demo_dataset_offline.py` | 9 | **全通过** |
| 发布前保密扫描 | `tests/test_publish_safety_scan.py` | 27 | **全通过** |
| 泄漏审计五渠道 | `tests/test_exam_leakage_audit.py` | 见文件 | **全通过** |
| 官方 DOCX 填写与核验 | `tests/test_grant_official_forms.py` | 38 | **全通过**（需 `--with python-docx`） |
| §9 一致性与交付物 | `tests/test_grant_checkers.py` | 见文件 | **全通过** |

**关键负面测试**（不是只测正常路径）：CBL 不能启动受限训练、不能调用 AI 导师、
**不能经旧会话绕过**（先在窗口关闭期完整训练并提交，再开窗断言每条续接路径被拒）、
拒绝信息不含组别/批次/研究编码（子串扫描）、管理员不可伪造双教师审核、
未裁决分歧不可被覆盖、发布扫描对植入样本确实 BLOCK。

## 6. 数据库迁移验收

`./scripts/verify_migration_cycle.sh`（隔离临时库）：`upgrade head` → `downgrade` → `upgrade head`；
**52 个对象，0 处差异，schema 等价**。生产库**只读副本**的同循环见 `MIGRATION_ACCEPTANCE.md`；
**生产库本身未迁移、未写入**。

## 7. 检查脚本

| 脚本 | 结果 |
| --- | --- |
| `check_application_text.py` | 退出码 0；六栏 **522 / 370 / 900 / 223 / 446 / 619**（限 600/600/1000/300/600/800） |
| `check_protocol_consistency.py` | 退出码 0（§9 一致性 41 条配对、R9 交付物清单齐备） |
| `check_case_cards.py` | 退出码 0 |
| `validate_assessment_payloads.py` | 退出码 0（30/30） |
| `audit_exam_leakage.py` | 退出码 0；五渠道分别标注，**渠道 P 仍为 NOT INSPECTED** |
| `publish_safety_scan.py` | 退出码 0（BLOCK=0）；植入验证时 BLOCK=6 / exit 1 |

## 8. 未执行（不得视为通过）

| 项 | 原因 |
| --- | --- |
| 真实模型评分的浏览器验收（`E2E_EXPECT_REAL_AI=1`） | 本栈**按设计无密钥**；需人工在有真实密钥的环境执行，命令与判据见 `R9_PLAYWRIGHT_CLASSIFICATION.md` §6 |
| 官方 Word 的**版式与分页目视检查** | 本机无 Word / LibreOffice / pandoc（已实测），流水线固定标 SKIPPED 并给出人工命令 |
| 官方模板的实际填写 | **官方原件不在本机**（见 §9） |
| `prepare_presentation_data.py --apply`（真实演示库） | 本轮离线生成器只服务验收栈，未对任何真实/生产库执行 |
| 生产部署与部署后浏览器 smoke | 未部署，需申请人明确授权 |
| `./scripts/verify_deploy.sh` | 其前提是「运行源码 == 本检出、schema 在 head」；不部署故不适用 |

## 9. 阻塞项（非测试问题）

1. **官方原件 ZIP 不在本机**：`ClinPath_2026_Official_Source_Templates.zip` 经全盘查找未找到。
   填写与核验流水线**已就绪并测试**，ZIP 到位后是一条命令的事；缺失时脚本退出码 2 且
   **不生成任何替代模板**。放置路径见 `OFFICIAL_APPLICATION_VALIDATION.md` §3。
2. **生产实际病例目录（泄漏渠道 P）未核查**：需一份脱敏导出。
3. **真实人员事实缺失**：见 `R9_HUMAN_ACTION_CHECKLIST.md`（H01—H22）。

> 本报告只证明**软件与脚本**；医学审核、伦理与教学组织不在其范围内，也不由测试通过所推断。
