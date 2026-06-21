当前问题已经非常明确，不再是“认证没通”，而是：

> ❗ Codex 仍在做“功能叠加修复”，但没有解决“主系统 vs demo系统冲突 + 前端状态机断裂”

---

# 一、你当前系统的真实状态（关键诊断）

结合你描述 + commit 状态，可以还原出系统已经变成：

## 🧠 现在其实有两套系统在并行运行

### ① Demo体系（Codex持续在维护）

* /demo
* demo login flow
* demo navbar
* demo auth state（可能仍残留）
* 用于展示/验证

### ② 主账户体系（你真正需要的）

* /login
* /student/*
* /teacher/*
* /admin/*
* AuthProvider
* cookie session

---

# 二、核心问题（根因级别）

## ❌ Root Cause 1：存在“双入口认证体系竞争”

典型表现：

```
login 成功
→ cookie 已写
→ AuthProvider 正常

BUT
→ demo router / legacy login flow 仍在 intercept
→ 或 layout 仍引用旧 navbar /旧 auth state
→ UI 不更新 or 被重置
```

---

## ❌ Root Cause 2：Auth state 被 demo 层覆盖或重置

你现在非常像这种结构：

```text
App
 ├── DemoLayout（有自己的 auth / navbar）
 ├── MainLayout（新的 AuthProvider）
```

👉 结果：

* login 成功后 state 更新 ✔
* demo layout 又 mount ✔
* state 被覆盖 ❌

---

## ❌ Root Cause 3：登录成功没有“统一路由出口”

现在 likely 状态：

* student login → handled
* teacher login → partially broken
* admin login → UI fallback

原因：

👉 **role-based redirect 没有统一决策层**

---

## ❌ Root Cause 4：Navbar 仍是“混合遗产结构”

你截图里仍出现：

```
Dashboard | Pathway | Profile | Logout
Login
```

说明：

* Navbar 不是单一 auth state driven
* 而是“路由 + 静态菜单混合”

---

# 三、关键结论（非常重要）

你现在的问题已经不是 bug，而是：

> ❗ “认证系统已经完成实现，但系统架构存在双体系竞争（demo vs production）”

---

# 四、必须做的修复策略（结构级，不是代码级）

## 🧩 Strategy 1：强制“Single Auth Source of Truth”

必须统一为：

```
AuthProvider（唯一）
  ↓
/api/auth/me（唯一）
  ↓
role-based router（唯一）
```

---

## 🧩 Strategy 2：彻底隔离 demo 系统

必须：

* demo 不参与 auth state
* demo 不挂 AuthProvider
* demo 不使用 navbar auth logic
* demo route 必须 sandbox

---

## 🧩 Strategy 3：强制“登录后状态机”

必须定义唯一流程：

```
login success
  ↓
/api/auth/me
  ↓
setUser
  ↓
router.replace(role dashboard)
  ↓
navbar re-render
```

---

## 🧩 Strategy 4：Navbar 重构为纯函数组件

必须：

```
UI = f(authState)
```

不能依赖：

* route
* local state
* demo flags
* static menu

---

# 五、给 Codex 的最终修复提示词（强约束版）

下面这份是你下一步必须直接用的 prompt（重点：强制“系统级收敛”，禁止 demo 干扰）

---

# ✅ FINAL CODEX PROMPT（系统级收敛 + 认证闭环修复）

## 🎯 目标

彻底修复 ClinicalLearningSystem 当前：

> “demo系统与主认证系统并存导致 UI 状态混乱 + 登录后不稳定 + Navbar 不一致”

并建立：

> ✔ 单一认证系统
> ✔ 单一 UI 状态源
> ✔ 单一路由决策层
> ✔ demo完全隔离

---

# 🚨 Step 1：系统架构审计（必须执行）

Codex 必须输出：

```text
AUTH ARCHITECTURE MAP:
- all login entry points
- all AuthProvider instances
- all navbar implementations
- all /demo dependencies
- all routing guards
```

---

# 🚨 Step 2：强制删除/隔离 demo 认证影响

## 必须：

* /demo 不使用 AuthProvider
* /demo 不触发 /api/auth/me
* /demo 不参与 navbar state
* /demo layout 必须独立 shell

---

# 🚨 Step 3：统一认证源（唯一）

必须保证：

```ts
AuthProvider:
  source = /api/auth/me ONLY
  state = user | null | loading
```

禁止：

* localStorage auth
* demo auth state
* secondary auth hooks

---

# 🚨 Step 4：重写登录流程（强制闭环）

```ts
login flow MUST be:

POST /api/auth/login
→ await /api/auth/me
→ setUser(global state)
→ router.replace(role dashboard)
→ navbar re-render must happen
```

---

# 🚨 Step 5：Navbar 强制重构（关键）

Navbar 必须：

```ts
const { user } = useAuth()

if (!user) return LoginButton
if (user.role === student) return StudentNav
if (user.role === teacher) return TeacherNav
if (user.role === admin) return AdminNav
```

禁止：

* route-based rendering
* static menus
* demo flags

---

# 🚨 Step 6：路由系统统一守卫

必须实现：

```
/student/* → only student
/teacher/* → only teacher/admin
/demo → no auth dependency
/login → public only
```

---

# 🚨 Step 7：端到端真实浏览器验证（必须）

Codex 必须用 Playwright：

## Test A：student

* login
* redirect dashboard
* refresh persist login
* navbar correct

## Test B：teacher

* login success
* no freeze
* correct dashboard

## Test C：admin

* full access

## Test D：demo isolation

* /demo login does NOT affect auth state
* switching demo ↔ main does NOT reset user

---

# 🚨 Step 8：必须输出最终架构图

Codex 必须输出：

```
FINAL ARCHITECTURE:

AuthProvider (single source)
        ↓
   /api/auth/me
        ↓
 global user state
        ↓
 role router
        ↓
 navbar render
        ↓
 pages
```

---

# 🧨 成功标准（非常关键）

系统必须满足：

* 登录后 UI 必然变化
* navbar 永远正确
* demo 不影响任何状态
* refresh 保持登录
* 不存在“双 auth 系统”

---

