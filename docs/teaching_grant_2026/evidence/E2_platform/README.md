# E2 平台基础（技术证据）

> 状态：**已收集，可复查**。所有条目都指向仓库内实际文件或可复现命令。

## 已具备

| 编号 | 证据 | 位置 |
| --- | --- | --- |
| E2-01 | 运行版本与 schema | `GET /api/system/version`；生产当时 `1d4ef48` / `20260915_06` |
| E2-02 | 部署一致性 | `./scripts/verify_deploy.sh`（当前工作树未部署，生产仍为 HEAD，脚本对未部署状态会报 FAIL，这是预期行为） |
| E2-03 | 后端测试 | 228 passed（`cd backend && uv run --python 3.11 --with-requirements requirements.txt pytest -q`） |
| E2-04 | 前端类型/风格/构建 | `npm run typecheck`、`npm run lint`、`npm run build` 均通过 |
| E2-05 | 浏览器 E2E | `tests/e2e/teacher.spec.ts` 3/3、`research-demo.spec.ts` 3/3 |
| E2-06 | 页面截图 | `workpackages/C_workflow/C04_screenshots/`（17 张）、`workpackages/D_research_demo/D01_screenshots/`（6 张） |
| E2-07 | 功能核查与演示说明 | `workpackages/C_workflow/C01_demo_walkthrough.md`、`C02_run_record.md` |
| E2-08 | 研发文档 | `docs/ARCH.md`（含新增 §18）、`docs/PILOT_READINESS_REPORT.md` |

## 仍需外部确认

| 项目 | 说明 |
| --- | --- |
| 展示授权 | 由院系/单位确认可在申报材料中使用系统截图 |
| 教师实际演示反馈 | 需真实教师观摩后填写（见 C04 §4） |
