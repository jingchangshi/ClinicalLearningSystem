目标：
修复 ClinicalLearningSystem 当前 commit 1fdf9d8fd4277fcf1e08895b60de4f2b4235afd0 中存在的“登录成功后页面回跳 /login 问题”，并统一认证存储机制，同时规范 LLM 调用架构为服务层。

---

# 一、核心问题修复：登录后重定向循环（最高优先级）

## 问题现象
- login API 成功
- token 保存成功（localStorage）
- router.push 成功跳转 /teacher/dashboard
- 页面立即回到 /login

## 根本原因
Next.js middleware / server auth guard 无法读取 localStorage token，导致误判未登录。

---

# 二、必须统一认证机制（必须实现）

## 方案：改为 HttpOnly Cookie（推荐）

### 1. 后端修改 /auth/login

在返回 token 的同时：

- 设置 cookie：

access_token=<jwt>

属性：
- httpOnly = true
- sameSite = lax
- path = /

---

### 2. 前端修改

删除：

- saveAuthToken(localStorage)

改为：

- 依赖 cookie 自动携带
- axios/fetch 必须带 credentials: "include"

---

### 3. middleware.ts 修复

必须改为：

- 从 request.cookies 读取 access_token
- 不再读取 localStorage（server无法访问）

---

### 4. 路由守卫统一

规则：

- /login → 永远可访问
- /student/* → require student cookie token
- /teacher/* → require teacher/admin role
- /demo → public

---

# 三、前端登录流程修复

修改 LoginClient.tsx：

1. 删除 saveAuthToken
2. login API 必须：

fetch('/api/auth/login', {
  credentials: 'include'
})

3. login success 后：

router.push(next || role-based route)

---

# 四、API client 修复

frontend/lib/api.ts：

统一：

- credentials: "include"
- 不依赖 localStorage token

---

# 五、后端认证统一检查

确保：

- /api/auth/login
- /api/auth/register
- /api/auth/me

全部基于 cookie 或 Authorization header（二选一，必须统一 cookie）

---

# 六、LLM 架构重构（新增要求）

## 目标：统一 LLM 服务层

---

## 1. 新增 LLMService（必须）

backend/app/services/llm_service.py

统一入口：

- chat_completion()
- generate_case()
- explain_recommendation()
- generate_sp_feedback()
- generate_guideline_rationale()

---

## 2. 环境变量

必须支持：

LLM_API_KEY
LLM_BASE_URL
LLM_MODEL

---

## 3. 禁止直接调用 client

所有模块必须：

❌ 直接调用 openai / http
✔ 通过 LLMService

---

## 4. fallback机制

没有 API key：

- 使用 deterministic template
- 系统不可崩溃

---

# 七、必须接入 LLM 的模块

1. recommendation_service → explanation
2. case_generator_service → case generation
3. SP feedback → narrative feedback
4. guideline scoring → rationale explanation
5. teacher dashboard → teaching insight summary

---

# 八、验收标准

必须满足：

1. login 后不再跳回 /login
2. teacher/student 正常跳转
3. middleware 正确识别登录态
4. cookie 方式生效
5. localStorage 不再作为认证依据
6. LLMService 可统一调用
7. 无 API 404 / redirect loop
8. npm run build 通过
