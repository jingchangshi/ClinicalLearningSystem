下面是**针对你当前 commit 状态的“系统级最终修复 Codex 提示词”**。

它专门解决你现在的三个残留问题：

---

# 🚨 当前真实问题归纳（必须修）

## ❌ 问题1：登录成功但页面不自动跳转 dashboard

* Navbar 已更新
* 但主体 page 没同步刷新
* 必须点击导航才变化

👉 本质：**Auth state 更新 ≠ router 状态同步**

---

## ❌ 问题2：logout 后 UI 不刷新

* cookie 已清
* 但前端仍显示旧页面
* 需要手动刷新或点击导航

👉 本质：**logout 没触发 global re-render + route reset**

---

## ❌ 问题3：缺少注册系统（系统不完整）

* 当前只有 seed users
* 没有 register flow
* 不符合完整 account system

---

# 🧠 根因总结（关键）

当前系统已经“功能正确”，但缺：

> ❗ “Auth-driven routing lifecycle（认证驱动路由生命周期）”

现在是：

```
login success → setUser ✔
但 ❌ 没有 router.replace()
logout → clear cookie ✔
但 ❌ 没有 reset route + state
```

---

# 🚨 FINAL CODEX PROMPT（必须严格执行）

## 🎯 目标

完成 ClinicalLearningSystem 的**最终账户系统闭环修复**：

> ✔ 登录后自动进入 dashboard（无需点击）
> ✔ logout 自动回到 login 并清空 UI
> ✔ Auth state + router state 完全同步
> ✔ 新增完整注册系统（production级）
> ✔ 全流程端到端验证

---

# 🚨 Step 1：强制建立 Auth Lifecycle Controller（核心修复）

必须新增或重构：

```text
AuthLifecycleManager
```

职责：

```ts
- login success → setUser → router.replace(role dashboard)
- logout → clearUser → router.replace("/login")
- refresh → /api/auth/me → restore session → route correction
```

---

# 🚨 Step 2：修复 login 不跳转问题（关键）

### 强制要求：

login success 后必须执行：

```ts
await fetch("/api/auth/me")
setUser(user)

router.replace(
  user.role === "student"
    ? "/student/dashboard"
    : "/teacher/dashboard"
)
```

❌ 禁止依赖：

* navbar click
* manual navigation
* useEffect fallback only

---

# 🚨 Step 3：修复 logout 不刷新 UI 问题

logout 必须：

```ts
await api.logout()

setUser(null)
clear auth cookie

router.replace("/login")

force re-render layout
```

并确保：

* Navbar immediately resets
* protected routes re-check auth

---

# 🚨 Step 4：全局强制 Auth Sync Hook（必须新增）

必须实现：

```ts
useAuthSync()
```

功能：

* on mount → call /api/auth/me
* update global auth state
* reconcile route vs role
* auto redirect if mismatch

---

# 🚨 Step 5：修复 Navbar（必须100%依赖 auth state）

Navbar 必须：

```ts
const { user } = useAuth()

if (!user) return <Login />
return role-based menu
```

禁止：

* route detection
* local state
* cached UI state

---

# 🚨 Step 6：新增注册系统（完整账户系统）

## 后端必须新增：

### POST /api/auth/register

支持：

```json
{
  "username": "",
  "password": "",
  "role": "student"
}
```

---

## 数据层要求：

* bcrypt password hash
* role assignment
* unique username constraint

---

## 前端必须新增：

### /register page

功能：

* username
* password
* role select (student/teacher)
* auto login after register

---

# 🚨 Step 7：补全账户系统能力（必须）

系统必须支持：

* register
* login
* logout
* me
* role-based routing
* session restore on refresh

---

# 🚨 Step 8：端到端 Playwright 强制验证（必须）

## Test 1：student login

* login → auto redirect dashboard
* refresh → stay logged in
* logout → redirect login + navbar reset

---

## Test 2：teacher login

* correct dashboard redirect
* navbar correct
* logout works

---

## Test 3：register flow

* create account
* auto login
* correct role routing

---

## Test 4：state sync

* login → no manual click needed
* logout → immediate UI reset
* refresh → consistent state

---

# 🚨 Step 9：必须输出最终架构图

```text
AuthProvider
    ↓
/api/auth/me
    ↓
AuthLifecycleManager
    ↓
setUser(global state)
    ↓
router.replace(role route)
    ↓
Navbar (pure function of user)
    ↓
Pages
```

---

# 🧨 成功标准（必须全部满足）

✔ 登录后自动跳 dashboard
✔ logout 自动回 login
✔ UI 无需点击任何导航
✔ refresh 保持状态
✔ register 可用
✔ Navbar 永远正确
✔ 无 demo 干扰
✔ 无手动状态修复依赖

