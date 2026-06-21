目标：
在当前仓库 jingchangshi/ClinicalLearningSystem（commit 84e02ad06e70a665ae1cf81e780b3ef1f6fb3063）基础上，
修复登录接口 404 问题，统一前后端 API 路由体系，确保认证系统完全可用，并在系统中规范接入 LLM 服务（通过环境变量配置 API Key），用于关键教学智能模块。

---

# 一、核心问题修复：登录 404（最高优先级）

## 当前现象
- 页面：http://129.153.118.58:8101/login?next=/student/dashboard
- 登录时报错：API request failed: 404

---

## 需要系统性排查并修复以下问题：

### 1. 前端 API 路径错误（高概率根因）

检查前端登录请求：

- login request 是否为：
  ❌ /auth/login
  ❌ /api/auth/login
  ❌ /v1/auth/login

必须与后端实际路由完全一致。

👉 要求：
- 统一 API baseURL 管理（axios/fetch封装）
- 检查是否缺少 `/api` 前缀

---

### 2. 后端路由挂载路径不一致

检查 FastAPI：

- auth router 是否为：
  ```python
  app.include_router(auth_router, prefix="/auth")
````

或是否被挂载为：

❌ /api/auth
❌ /auth
❌ /api/v1/auth

👉 必须统一为：

* 标准方案（推荐）：
  /api/auth/login
  /api/auth/register
  /api/auth/me

---

### 3. Nginx / 反向代理路径丢失问题（非常关键）

如果存在 nginx 或 proxy：

检查是否存在：

* /api 被 rewrite 掉
* /auth 被直接转发到 frontend

👉 修复规则：

确保：

* /api/* → backend
* /* → frontend

---

### 4. 前端 API client 统一重构（必须做）

新增或修复：

/frontend/src/lib/api.ts 或 axios instance：

```ts
baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api"
```

所有请求必须使用统一 client：

* login
* register
* me
* student APIs
* teacher APIs

禁止硬编码路径。

---

### 5. 增加后端调试能力（用于避免未来问题）

新增 middleware：

* log all incoming request paths
* log 404 routes

输出：

* request path
* method
* matched route or not

---

### 6. 增加 health check endpoint（用于验证部署）

新增：

GET /api/health

返回：

```json
{ "status": "ok" }
```

---

# 二、认证系统完整性校验（必须复查）

确保以下逻辑完全正确：

## 1. login response 必须统一格式

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "role": "student"
  }
}
```

---

## 2. 前端 token 存储一致性

检查：

* localStorage
* cookie
* memory state

必须统一：

* Authorization: Bearer <token>

---

## 3. /auth/me 必须可用

用于前端刷新态：

* 页面刷新 → 自动恢复用户身份

---

## 4. student_id 不得再从 query 获取

必须全部改为：

* token → user → student_id

---

# 三、LLM 模型接入系统设计（新增核心能力）

## 目标

在系统中引入 LLM 能力，用于：

* 病例生成
* 学习路径解释
* 推荐理由生成
* guideline 分析
* 教学反馈生成

---

## 1. 新增 LLM Config（必须）

新增文件：

/app/core/llm_config.py

```python
import os

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
```

---

## 2. 新增统一 LLM Client

/ app/services/llm_client.py

必须支持：

* chat completion
* retry机制
* timeout
* fallback（key不存在时返回 mock）

---

## 3. 环境变量要求

新增：

```
LLM_API_KEY=xxx
LLM_BASE_URL=optional
LLM_MODEL=optional
```

---

## 4. LLM 接入模块清单（必须改造）

### （1）病例生成

* case_generator_service

👉 用 LLM 优化 case complexity & realism

---

### （2）学习路径解释（关键）

* recommendation_service

新增：

* explain_recommendation_with_llm()

输出：

* 为什么推荐该任务
* 对应能力缺口解释
* 下一步学习策略

---

### （3）guideline scoring解释

* guideline_scoring.py

增加：

* LLM生成 scoring rationale

---

### （4）SP / skill反馈增强

* SP feedback
* skill session feedback

增加：

* structured narrative feedback

---

## 5. LLM 使用规则（重要）

必须遵守：

* 无 API Key → fallback deterministic logic
* 有 API Key → LLM增强输出
* 不允许阻塞主流程（必须 async-safe 或 degrade gracefully）

---

# 四、系统一致性修复（必须执行）

## 1. API路径统一

必须统一为：

```
/api/auth/*
/api/student/*
/api/teacher/*
```

---

## 2. 前端 API 调用统一入口

禁止：

* fetch("/auth/login")
* fetch("/login")

必须：

* apiClient.post("/auth/login")

---

## 3. 登录错误必须可追踪

前端必须打印：

* request URL
* status code
* response body

---

# 五、验收标准

必须满足：

## 登录系统

* [ ] login 不再 404
* [ ] register 正常
* [ ] me 正常
* [ ] token 可持久化

## 权限系统

* [ ] student 不能访问 teacher API
* [ ] teacher 可访问 dashboard
* [ ] admin 全权限

## 路由一致性

* [ ] API prefix 全部统一
* [ ] 无 /auth vs /api/auth 混乱

## LLM系统

* [ ] API Key 可配置
* [ ] 至少3个模块接入 LLM
* [ ] 无 Key 时系统可运行

## 稳定性

* [ ] npm run build 通过
* [ ] backend 无 404 hidden route
* [ ] 前后端路径完全一致

---

# 六、最终目标状态

系统必须达到：

1. 登录系统稳定可用（无 404）
2. 权限系统完全隔离
3. API 路由完全统一
4. LLM 成为增强层（非核心依赖）
5. 教学路径解释具备“可发表论文级文本生成能力”

