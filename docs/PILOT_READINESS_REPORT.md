# ClinPath 试点就绪报告（Pilot Readiness Report）

本文件是**证据**，不是设计文档：每条数字都注明是怎么测出来的、在哪个环境测的。
未实测的项目不会被写成结论。架构不变量在 `docs/ARCH.md`；本文件的结论已经被回写进
§5.5 / §11 / §12 / §13 / §16。

复现命令集中在本文件 §11。

---

## 1. Baseline

起点是上一阶段的评审基线，工作树干净：

```text
starting SHA      d67e9d6ea15e69d70cb7c76cf419b1fe272b069e
git status        clean（只有本次改动之后才不再干净）
verify_deploy.sh  exit 0
schema           20260915_05
services         clinical-backend.service / clinical-frontend.service 均 active
backend          单进程 uvicorn（无 --workers）
provider         deepseek / deepseek-flash，thinking=on，effort=high，
                 max_tokens=8192，timeout=60s，retries=1
```

页面延迟基线（`scripts/measure_page_latency.py --samples 3`，经公网入口
`http://129.153.118.58:8101`，真实登录）：

| endpoint | min | median | max |
| --- | --- | --- | --- |
| `/api/student/dashboard` | 35ms | 37ms | 42ms |
| `/api/student/pathway` | **15958ms** | **18524ms** | **19676ms** |
| `/api/student/competency` | 7ms | 7ms | 8ms |
| `/api/teacher/dashboard` | 3491ms | 3744ms | 4171ms |
| `/api/teacher/students/1/learning-profile` | 3363ms | 7549ms | 8009ms |

基线 AI 延迟（同一部署，真实 DeepSeek）：病例评测单次 15–29s（本阶段复测见表 §4）。

> `/api/student/dashboard` 当时看起来只有 35ms：该学生已有
> `learning_recommendations` 行，所以没走到模型那一步。**没有**这一行的学生会同步
> 触发一次 provider 调用——这是「读路径依赖模型」的典型形态：延迟取决于数据状态。

---

## 2. LLM 调用清单（改造前 → 改造后）

| task | caller / endpoint | method | 角色 | 改造前 | 改造后 |
| --- | --- | --- | --- | --- | --- |
| `case_evaluation` | `POST /api/sessions/{id}/submit` → `scoring_llm` | POST | student | 同步阻塞（正确性必需） | 不变（仍同步） |
| `tutor_question` | `POST /api/sessions/{id}/tutor`、`/coach` → `tutor_service` | POST | student | 同步阻塞 | 不变，但预算下调 |
| `recommendation_explanation` | 曾挂在 `GET /student/pathway`、`GET /student/dashboard`、`GET /teacher/students/{id}/learning-profile` | GET | student/teacher | **读路径同步调用** | 改为「学习事件后 / 教师显式刷新」生成 + `ai_enrichments` 缓存 |
| `teacher_insight` | 曾挂在 `GET /teacher/dashboard` | GET | teacher | **读路径同步调用** | 读缓存；`POST /api/teacher/dashboard/refresh-insight` 显式生成 |
| `guideline_rationale` | `POST /api/guidelines/{id}/pico` | POST | student | 同步阻塞 | 不变，预算下调 |
| `sp_patient` | `POST /api/sp-sessions/{id}/message` | POST | student | 同步阻塞 | 不变，预算下调 |
| `sp_evaluation` | `POST /api/sp-sessions/{id}/submit` | POST | student | 同步阻塞 | 不变 |
| `skill_feedback` | `POST /api/skill-sessions/{id}/submit` | POST | student | 同步阻塞 | 不变 |
| `case_generation` | `POST /api/case-generation/generate` | POST | teacher | 同步阻塞 | 不变 |
| `ai_probe` | `POST /api/system/ai-probe` | POST | teacher | 极简探测 | 不变（策略显式化） |

分类（本阶段据此制定策略）：

```text
A. 正确性关键的同步 AI   case_evaluation（保留完整推理预算）
B. 有用的交互式 AI       tutor_question、sp_patient、sp_evaluation、guideline_rationale、skill_feedback
C. 装饰性/增强 AI        recommendation_explanation、teacher_insight
D. 可后台/可预计算        上述 C 类的生成时机（学习事件后、教师刷新）
```

---

## 3. 架构改动

### 3.1 pathway：确定性优先，AI 解释可选

- `recommendation_service.build_learning_pathway()` / `choose_recommendation()`
  **不再包含任何模型调用**；四个阶段（LearnerGap → Candidate → Constraint → Ranker）
  保持不变，每项任务自带 `REASON_TEMPLATES` 规则理由。
- 新增 `app/services/ai_enrichment.py`：`ai_enrichments(kind, cache_key, payload_json,
  prompt_version, provider, model, source_fingerprint, fallback_used, generated_at)`，
  `backend/alembic/versions/20260915_06_ai_enrichments.py` 建表。
- 读接口只做：确定性结果 + `fingerprint` 仍然匹配的缓存解释，输出
  `explanation_source` / 每任务 `reason_source`。**过期即退回规则理由**，不冒充当前解释。

### 3.2 失效规则

```text
student fingerprint = sha256(student_id, competency_profile.updated_at, max(learning_evidence_events.id))
class   fingerprint = sha256(max(learning_evidence_events.id), count(learning_evidence_events))
```

任何一次有意义的学习事件（病例提交、知识测验、技能、SP、指南 PICO、教师确认复核）都会
改变 fingerprint，从而使旧解释失效。失效事件清单与实现一致，不依赖定时器。

生产实测（部署后，学生完成一次病例训练触发）：

```text
ai_enrichments 行：pathway(student:1) + teacher_insight(class)
GET /api/student/pathway → explanation_source = ai
  case:1 / guideline:1 / knowledge_unit:1 → reason_source = ai
  推荐病例 id=8（该病例没有缓存解释）→ recommendation_reason_source = rule  ← 预期行为
```

### 3.3 teacher dashboard 与 learning profile

- dashboard 基础响应全部确定性；`teaching_insight_summary` 来自缓存，
  `teaching_insight_source ∈ {ai, rule}`，GET 不触发 provider。
- 新增 `POST /api/teacher/dashboard/refresh-insight`：显式、会写库、失败时返回
  `degraded: true` + 规则建议（`build_teacher_insight_text` 通过
  `invocation.fallback_used` 判定「模型到底答没答」，规则输出**不会**被存成 AI 洞察）。
- 教师端 learning profile 与学生学习路径共用同一个
  `pathway_context.load_pathway_catalog()`，不再各拼一份目录（旧实现里教师视角的指南
  条目字段更少，同一个学生可能被推荐不同的指南任务）。

### 3.4 顺带修掉的读路径开销

pathway 页面每条 `session.case` / `session.score` 都是一次 lazy load：

```text
改造前  /api/student/pathway      161 条 SQL   47.4ms（进程内）
改造后  /api/student/pathway       18 条 SQL   13.3ms
改造前  /api/student/dashboard     73 条 SQL   26.4ms
改造后  /api/student/dashboard     16 条 SQL   13.4ms
```

### 3.5 读路径不再调用 provider（永久门禁）

`backend/tests/test_read_paths_never_call_provider.py` 替换 provider 边界并断言
`provider_call_count == 0`：`/student/pathway`、`/student/dashboard`、
`/student/competency`、`/teacher/dashboard`、`/teacher/students/{id}/learning-profile`。
它同时断言这些读请求**不产生 AI 审计事件**（缓存读取不得写假的 `ai_invocations`），
以及缓存过期时展示规则理由而不是触发生成。

---

## 4. Task-aware 策略与质量基准

策略唯一定义在 `backend/app/core/ai_policy.py`；路由只表达任务语义。
下表「实测」列来自 `backend/tools/ai_benchmark.py`（真实 DeepSeek，deepseek-flash，
`runs=2–4`，固定合成输入，非敏感）。**baseline 列 = 本阶段之前那套全局配置**
（thinking=on / effort=high / 8192 tokens）。

| task | thinking | effort | max_tokens | timeout | 实测 p50（本策略 vs 旧全局） | schema | 质量门禁 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `case_evaluation` | ✅ | high | 8192 | 60s | 17859ms vs 16095ms | 2/2 | 2/2 |
| `case_generation` | ✅ | high | 8192 | 60s | 23586ms vs 14109ms（同配置，方差大） | 2/2 | 2/2 |
| `tutor_question` | ❌ | — | 600 | 25s | **1079ms** vs 1894ms（旧全局）/ 4672ms（thinking+900） | 3/3 | 3/3 |
| `sp_patient` | ❌ | — | 600 | 25s | **1218ms** vs 1960ms / 3252ms | 3/3 | 3/3 |
| `sp_evaluation` | ❌ | — | 2600 | 40s | 1525ms vs 4504ms | 2/2 | 2/2 |
| `guideline_rationale` | ❌ | — | 1200 | 30s | 1286ms vs 5717ms | 2/2 | 2/2（旧全局 1/2 不合格） |
| `skill_feedback` | ❌ | — | 700 | 25s | 1295ms vs 2694ms | 2/2 | 2/2 |
| `recommendation_explanation` | ❌ | — | 900 | 25s | 1204ms vs 2889ms | 3/3 | 3/3 |
| `teacher_insight` | ❌ | — | 600 | 25s | 1650ms vs 3967ms | 3/3 | 3/3 |
| `ai_probe` | ❌ | — | 16 | 15s | 880ms vs 1013ms | 3/3 | 3/3 |

质量门禁（`tools/ai_benchmark.py` 内）：用例评测校验 6 维 JSON、score/confidence/
evidence/missing_points/feedback/safety_flags 齐全；tutor 校验「是一个提问、简洁、
**不泄露隐藏诊断与治疗方案**」；SP 患者校验「非空、简洁、不跳出角色」；
推荐解释校验「命中的是真实能力缺口、不编造学习增益」；教师洞察校验「引用了真实短板」。

### 记录在案的两个判断

1. **tutor / sp_patient 关掉 thinking 是测出来的，不是猜的。** thinking=on + effort=low +
   900 tokens 反而最慢（p50 4672ms）：推理轨迹先把预算吃掉，答案被截断成空内容并触发重试。
   关闭 thinking 后 p50 963–1218ms，质量门禁全部通过，人工对比的苏格拉底式提问质量相当
   （合成输入下两者都要求「支持证据 + 反证 + 排序」）。
2. **`case_evaluation` 保留 thinking=high，尽管关闭后可快 4.6×。** 实测
   `no_thinking_3k` p50 3906ms、schema 2/2、质量门禁 2/2——按本阶段定义的门禁它"通过"了。
   但这是直接产出形成性评价、并被投影进 competency 的教学判定，2 次运行不足以证明
   证据质量没有下降。因此**不改**：正确性优先，把「异步化」列为下一步（§9），
   把「评测质量对照实验」列为后续验证。

---

## 5. 页面延迟：改造前 vs 改造后

同一脚本 `scripts/measure_page_latency.py --samples 3`；「改造后」在
`https://clinpath.1031989.xyz`（4 worker、公网 HTTPS）实测：

| endpoint | before（d67e9d6，HTTP 直连，1 worker） | after（源站直连，4 worker） | after（经 HTTPS 边缘，4 worker） |
| --- | --- | --- | --- |
| `/api/student/dashboard` | 35–42ms | 23–93ms | 96–173ms |
| `/api/student/pathway` | **15958–19676ms** | **23–29ms** | **102–185ms** |
| `/api/student/competency` | 7–8ms | 8–9ms | 95–125ms |
| `/api/teacher/dashboard` | 3491–4171ms | 38–110ms | 108–123ms |
| `/api/teacher/students/1/learning-profile` | 3363–8009ms | 34–122ms | 109–197ms |

两列 after 都是真话，量的是不同路径：源站直连（优化后的确定性读路径本身）与经 HTTPS
边缘（用户实际路径，含 Cloudflare 边缘 + 隧道往返；本次测量从 VPS 自身发出，
`cf-ray` 显示走 LAX 边缘，因此这 100ms 量级主要是我方测量路径的往返，不代表远端学生
的绝对体验）。改造前 pathway 慢 16–20 秒，**与走哪条路无关**，因为瓶颈是模型而不是网络。

### provider 完全不可达时的导航（staging，路径全部 200）

```text
/api/student/dashboard   35ms        /api/knowledge            4ms
/api/student/pathway      31ms        /api/cases                4ms
/api/student/competency    5ms        /api/skills               4ms
/api/teacher/dashboard   108ms        /api/guidelines           4ms
/api/teacher/students/1/learning-profile  48ms
```

AI 动作仍然可用但诚实降级：tutor 返回规则追问（HTTP 200，0.54s）；
提交返回 `evaluation_mode=rule_fallback`、`degraded=true`、`ai_score=null`。

---

## 6. 容量结果

环境：单台 Oracle VPS（4 vCPU，24GB，SQLite WAL，4 backend workers），k6 v0.55.2，
staging 是**生产库的 sqlite 备份副本**（`scripts/start_staging_8200.sh`），
不写生产数据。

### 6.1 场景 A：100 并发非 AI 用户

```text
请求总时长/并发   2m45s ramping 到 100 VU，每个 VU 登录一次后复用会话
requests          42,620（254.8 req/s）
read latency      avg 37.0ms   p50 16.2ms   p90 89.4ms   p95 139.0ms   max 1.06s
login latency     p95 264ms（bcrypt，一次性）
HTTP 失败          0.00%（0 个 5xx，0 个 429，0 个超时）
iterations        4,252 完成 / 0 中断

复跑（60s hold）：read p95 123.8ms，25,100 请求，0% 失败
CPU（4 worker）   峰值 2.31 / 4 核，稳态 ≈2.0 核
内存（4 worker）   RSS 合计 ≈ 655MB（每 worker ≈155MB）
SQLite 写入       同负载下 1,283 次写入：0 失败，p50 1ms / p95 2ms / max 5ms
```

### 6.2 worker 数：实测对比

```text
1 worker   read p95 1.28s / 1.16s，median ≈259ms（同负载，同代码）
4 workers  read p95 139ms / 124ms，median ≈15ms
```

（单进程 100 并发时 p95 6–10s 的更差观测出现在连接池修复前，见 §7。）

### 6.3 场景 B：导航 + 并发 AI（mock provider，不花额度）

```text
8s 慢 provider + 10 tutor + 5 scoring：导航 p95 206ms，0% 失败，AI p50 8.06s
15s 慢 provider + 20 tutor + 5 scoring：导航 p95 326ms，0% 失败，AI p50 15.07s
provider 全部 429：导航 p95 615ms，0% 失败；
  「tutor/submit 降级而不是失败」检查 100% 通过
```

结论：AI 失败被限制在 AI 任务内部；普通导航在 25 个 15 秒级并发 AI 请求下仍然可用。

### 6.4 场景 C：有界真实 DeepSeek 并发

```text
tutor_question     并发 2：p50 980ms   max 1112ms   0 降级
                   并发 5：p50 5834ms  max 10107ms  0 降级
                   并发 10：p50 5718ms max 13590ms  0 降级
case_evaluation    并发 2：p50 17637ms max 23295ms  0 降级
                   并发 5：p50 18795ms max 61705ms  0 降级
                   并发 10：p50 20305ms p95 28255ms max 29075ms  0 降级
所有级别：0 个 429、0 个 5xx、0 个传输错误
```

并发 5 的那次 61.7s 是单次生成偏慢，**没有**降级（说明它在后端 60s×2 的有界预算内完成）。

### 6.5 未实测项（如实说明）

- 前端（Next.js）在 100 并发下的 CPU/内存未单独测量：本阶段压的是 API 层，
  k6 未经过 8101。教师 dashboard 是 SSR 页面，其余页面由浏览器直接调 `/api`。
- 未做多机 / 多实例压测；结论只覆盖单 VPS。
- mock provider 的 429/500/空体/非法 JSON 通过 curl 级检查验证降级，未做长时压测。

---

## 7. 瓶颈定位

| 候选 | 结论 | 证据 |
| --- | --- | --- |
| SQLite 写锁 | **不是瓶颈** | 100 并发读的同时写 1,283 次，0 失败，p95 2ms |
| SQLite 读并发 | **不是瓶颈** | WAL；连接建立+PRAGMA+SELECT 并发 10 时 p50 6ms |
| 连接池（默认 5+10） | **是硬上限，已修** | 100 并发时 `QueuePool limit of size 5 overflow 10 reached, connection timed out`，13% 请求失败、p95 ≈60s；显式 20+40 后 0 失败 |
| 后端进程 / GIL | **是主要瓶颈** | 同步读接口一次只执行一个请求的 Python 工作：并发 10/20/40/100 的延迟几乎线性增长；同一进程上 `async` 的 `/api/health` 在并发 20 时仍是 5ms。1→4 worker 把 p95 从 1.28s 降到 0.14s |
| N+1 lazy load | **是次要瓶颈，已修** | pathway 161 条 SQL → 18 条；进程内 47.4ms → 13.3ms |
| DeepSeek | **不是导航瓶颈；是 AI 任务的延迟来源** | 病例评测 17–29s；provider 429 风暴下导航 p95 仅 615ms |
| 前端 | **未测**（见 §6.5） | — |
| 限流语义 | **会在单 IP 场景提前截断** | 登录默认 60 次/小时/身份；100 个 VU 从同一地址登录会全部 429（staging 压测时特意抬高，见 §11）。4 worker 下限流变为 per-process |

---

## 8. 架构决策

| 决策点 | 结论 | 依据 |
| --- | --- | --- |
| SQLite | **KEEP** | 同负载下写 0 失败、p95 2ms；读写都不构成上限。迁移到 PostgreSQL 没有证据支持 |
| 后端进程数 | **增加到 4 worker**（4 vCPU） | 1 worker p95 1.28s → 4 worker p95 0.14s；峰值 2.31/4 核、RSS 655MB 仍有余量 |
| 共享限流器 | **暂不需要** | 单机多进程，限流是滥用防护而非配额账本；代价（有效上限 ×worker 数）已写进 ARCH §12。多机部署前必须重新评估 |
| 异步病例评测 | **下一步推荐（未实现）** | 实测 p50 17.6–20.3s、p95 28.3s、max 61.7s，稳定超过 §27 的 15–20s 阈值 |
| HTTPS | **已完成** | `https://clinpath.1031989.xyz`（Cloudflare 隧道终止 TLS），HTTP 307 → HTTPS，`COOKIE_SECURE=true`，公网 `:8101` 已不可达 |
| 逐任务 DeepSeek 策略 | 见 §4 表格 | 每个 task 都有 thinking/effort/tokens/timeout 的实测依据 |

---

## 9. 异步病例评测：设计决策（未实施）

评测本身无法在 20 秒内完成，而这 20 秒发生在学生点击「提交」之后。契约建议：

```text
POST /api/sessions/{id}/submit
    ↓ 冻结作答（现有 answer-integrity 约束不变）
    ↓ 202 + evaluation_pending（前端显示「正在生成形成性反馈…」）
    ↓ 后台用同一 service 评测（失败 → rule_fallback，仍写 scores 行）
    ↓ result ready（前端轮询 /sessions/{id}/result）
```

需要的耐久性比 enrichment 高：评测结果会进入 competency，不能丢。因此不能只靠
进程内线程；在本机形态下最小可行做法是「提交时先落一条 pending 行 + 启动时扫描未完成
评测」，而不是引入队列中间件（本阶段无证据支持增加运维组件）。

优先级：**先做**，它已经是学生可感知的主要等待，而且现在读路径已经干净，
不会与其它改动互相干扰。

---

## 10. HTTPS 状态

```text
domain           clinpath.1031989.xyz（用户已持有并已由其 Cloudflare 账号托管的域名）
TLS              Cloudflare 边缘终止；本机不新增监听端口
入口拓扑         Internet → HTTPS → cloudflared 隧道 → 127.0.0.1:8101 → 127.0.0.1:8100
HTTP → HTTPS     http://clinpath.1031989.xyz → 307 到 https（Next.js redirect，
                 只在收到 x-forwarded-proto: http 时触发）
COOKIE_SECURE    true（登录响应实测 Set-Cookie 带 Secure）
端口             :8101 只监听 127.0.0.1（公网 IP:8101 实测不可达）；:8100 仍为内部端口
回退             CLINPATH_FRONTEND_HOST=0.0.0.0 + COOKIE_SECURE=false（应急用，非目标形态）
```

未做（如实记录）：Cloudflare 控制台的 “Always Use HTTPS” 仍可开启，作为纵深防御；
本机 443 已被无关服务占用且无 sudo，因此没有采用自建 Caddy/Nginx + Let's Encrypt。
HSTS 头未设置（依赖边缘配置）。

---

## 11. 测试与复现

### 11.1 门禁结果（本阶段最后一次运行）

```text
backend pytest                                189 passed                       ~73s
frontend typecheck / lint                     clean
frontend build                                OK（26 条路由）
playwright（HTTPS，E2E_RUN_MUTATING=1,
            E2E_EXPECT_REAL_AI=1）             23 passed / 2 skipped            1.1m
E2E_EXPECT_NO_JWT_SECRET=1 / E2E_EXPECT_FALLBACK=1   跳过（需要单独的 keyless / 无密钥部署）
```

跳过说明：这两个门禁必须在另外的部署形态下运行（无 JWT_SECRET 的前端、无 provider key
的部署），本阶段没有搭建这两个一次性实例，因此如实记为 skipped，而不是 passed。

新增的永久门禁：

```text
tests/test_read_paths_never_call_provider.py   11 项：读路径 provider_call_count == 0
tests/test_ai_policy.py                        10 项：策略完整性与传输契约
tests/test_ai_enrichment.py                     4 项：worker 真的能产出两类 enrichment
                                                （这一条当场抓出了 teacher_insight 的 ImportError）
```

### 11.2 容量/延迟复现

```bash
# 页面延迟（只读）
python3 scripts/measure_page_latency.py --samples 3
# 注意：HTTPS 入口经 Cloudflare，默认的 Python-urllib UA 会被边缘拒绝（403）；
# 该脚本显式声明自己的 UA，而不是伪装成浏览器。

# 一次性 staging 后端：生产库副本 + 迁移到 head + 4 worker
./scripts/start_staging_8200.sh

# 场景 A：100 并发非 AI 用户
k6 run -e BASE_URL=http://127.0.0.1:8200 -e TARGET_VUS=100 -e HOLD=2m \
   -e USERS=student1,student2,student3,student4 loadtest/k6_navigation.js

# 场景 B：mock 慢 provider（另开终端）
python3 loadtest/mock_provider.py --port 8300 --mode slow --latency-ms 8000
CLINPATH_STAGING_LLM_BASE_URL=http://127.0.0.1:8300/v1 \
CLINPATH_STAGING_LLM_MODEL=mock-model \
CLINPATH_STAGING_LLM_PROVIDER=openai-compatible ./scripts/start_staging_8200.sh
k6 run -e BASE_URL=http://127.0.0.1:8200 -e AI_VUS=10 -e SCORING_VUS=5 loadtest/k6_mixed_ai.js

# 负载下的 SQLite 写健康
python3 loadtest/sqlite_write_probe.py --db ~/.local/state/clinpath-staging/staging.db --seconds 200

# 场景 C：有界真实 provider 并发（会消耗额度）
cd backend && python tools/ai_concurrency.py --task tutor --levels 2,5,10

# 策略基准（会消耗额度）
cd backend && python tools/ai_benchmark.py --tasks tutor_question,case_evaluation --runs 3
```

staging 会把限流阈值抬高（`CLINPATH_STAGING_ABUSE_LIMITS=1`），否则 100 个 VU 从同一
地址登录会在 60 次之后被 429 截断，压测会变成「测量限流器」。

---

## 12. 剩余债务

1. **同步病例评测**（P1）：p50 17.6–20.3s，见 §9。
2. 限流是进程内实现，而部署已是 4 worker：有效上限 ×4，已接受并记录；
   多机部署前必须替换。
3. `ai_runtime` 计数与最近 probe 状态是进程内的，`/teacher/runtime` 显示的是
   「某个 worker」的数字；持久事实以 `ai_invocations` 表为准。
4. 读接口仍是同步实现、GIL 受限：已用 4 worker + N+1 修复解决试点规模，
   继续增长时先做序列化开销优化而不是直接多机。
5. 学习材料 tags 仍由内容启发式推导，教师端还不能可视化维护。
6. tutor 仍只覆盖病例训练的 5 个推理步骤。
7. `ai_invocations` 仍是「一次任务一个事件」，没有逐次 attempt 粒度。
8. 前端在并发下的表现未测（§6.5）。
9. 未启用 HSTS；Cloudflare “Always Use HTTPS” 仍可选开启。

---

## 13. 下一个推荐目标

**A. 异步病例评测**（`POST submit → evaluation_pending → 后台评测 → result ready`）。

理由来自本阶段证据，而不是理论：

- 读路径已经不再依赖模型（§5），学生可感知的剩余等待集中在提交后的 17–29s（§6.4）；
- 后端对模型调用已有界（timeout × retries），还有 `proxyTimeout` 作为正确性上限，
  异步化不会引入新的不确定性；
- 其余候选缺少证据：PostgreSQL/多机在 SQLite 与 4 worker 下都没有被证明是瓶颈（§7/§8）；
  HTTPS 已完成（§10）；Tutor 扩展、教师可编辑元数据、learner-model v2 都是内容/模型演进，
  不影响试点可用性。

第二优先是 **C. 继续打磨 HTTPS/公网入口**（HSTS、Cloudflare 强制 HTTPS、8100 也收敛到
loopback），但它已经是可用状态，不再是阻塞项。
