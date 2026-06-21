# ✅ Codex Goal Prompt：认证系统与登录问题自动诊断修复（ClinPath）

## 🎯 目标

对仓库 `ClinicalLearningSystem` 当前版本进行**端到端自动诊断与修复**，重点解决：

### 核心问题

1. 登录接口偶发 `405 Method Not Allowed`
2. 前后端 auth 路由可能存在版本不一致（/auth vs /api/auth）
3. 登录成功但前端行为异常（跳转 /login 或无状态更新）
4. cookie / credentials / proxy / middleware 鉴权链不一致风险
5. API 路由存在历史遗留冲突（多版本 auth 实现）

---

## 🧠 必须执行的诊断流程（Codex必须按顺序做）

### Step 1：完整扫描认证链路

定位以下文件并逐个分析：

* backend auth router（login/register/me）
* frontend login page
* frontend api client（axios/fetch封装）
* middleware / proxy.ts
* nginx / vite / next proxy（如存在）

输出：

* 当前 login endpoint 实际路径
* 当前 HTTP method（POST/GET）
* cookie 写入位置
* token读取位置

---

### Step 2：构建“真实请求路径图”

必须生成：

```
Frontend login request → Proxy → Backend route → Response → Cookie → Middleware check → Dashboard
```

并标出：

* 哪一环可能 mismatch
* 哪一环存在 legacy logic

---

### Step 3：自动验证（必须执行）

Codex必须模拟或检查以下一致性：

#### 1. 路由一致性检查

确保：

* frontend login URL == backend login route
* method == POST
* prefix一致（/api/auth/login 或 /auth/login 只能保留一个）

---

#### 2. Cookie一致性检查

检查：

* Set-Cookie 是否存在
* SameSite / Path / Domain 是否合理
* credentials: include 是否全局启用

---

#### 3. Middleware检查

验证：

* 是否正确读取 access_token cookie
* 是否存在双系统（token + cookie混用）
* 是否存在错误 redirect loop

---

### Step 4：运行级修复策略（必须执行）

Codex必须自动执行以下修复策略：

#### A. 路由统一（强制）

统一为：

```
/api/auth/login
/api/auth/register
/api/auth/me
```

删除或废弃旧路径。

---

#### B. 前端统一 API client

确保：

* baseURL = /api
* 所有 auth 请求走同一封装
* 禁止 hardcoded /auth 或 /api/auth 混用

---

#### C. cookie策略统一

确保：

* HttpOnly enabled
* SameSite=Lax 或 None（根据实际）
* credentials: include 全局开启

---

#### D. middleware 修复

必须保证：

* /login /demo public
* /student/* requires student
* /teacher/* requires teacher/admin
* token 从 cookie 读取唯一来源

---

### Step 5：自动回归验证（必须）

Codex必须验证：

#### 登录链路：

1. POST /api/auth/login → 200
2. Set-Cookie 存在
3. /api/auth/me → 200
4. /student/dashboard → 200（student）
5. /teacher/dashboard → 200（teacher）
6. role mismatch → redirect /login

---

## ⚠️ 强约束规则

* 不允许新增第二套 auth system
* 不允许同时存在 /auth 和 /api/auth
* 不允许 token + cookie 双轨并存
* 不允许前后端路径不一致
* 不允许“临时兼容代码”

---

## 📦 输出要求

Codex必须输出：

1. 问题列表（root cause）
2. 修改文件清单
3. 每个修改的原因
4. 最终验证结果（必须逐条列出）
5. 如果失败，继续循环直到通过

---

## 🔥 成功标准

系统必须满足：

* 登录不再出现 404 / 405
* 登录后不会跳回 /login
* cookie 驱动完整 session
* role guard 稳定
* 前后端 API 完全一致

