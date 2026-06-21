# ✅ CODEx PROMPT（端到端认证闭环修复）

## 🎯 目标

修复 ClinicalLearningSystem 当前“登录后不跳转 / UI 不刷新 / 状态不一致”问题，并完成完整：

> Authentication Lifecycle + UI State + Routing 三位一体闭环

---

# 🧠 Step 1：必须做完整登录链路追踪（禁止猜测）

Codex 必须打印：

```
LOGIN FLOW TRACE:
1. request sent
2. backend response
3. cookie set check
4. /api/auth/me result
5. auth state update
6. router transition
7. navbar rerender trigger
```

---

# 🔧 Step 2：强制修复 Auth Lifecycle（核心）

## 必须统一为以下流程：

```ts id="auth-flow"
login() {
  setLoading(true)

  await POST /api/auth/login

  if success:
    await fetch("/api/auth/me")   ← 必须
    setAuth(user)                 ← 必须
    router.replace(role dashboard)← 必须

  setLoading(false)
}
```

---

# 🔧 Step 3：修复 AuthProvider（关键）

必须保证：

```ts id="auth-provider"
onMount:
  fetch("/api/auth/me")
    → setUser()
    → setLoading(false)
```

并且：

* cookie 是唯一来源
* local state 必须可恢复

---

# 🔧 Step 4：修复 Navbar 状态源（关键UI bug）

Navbar 必须：

❌ 不允许：

* 静态判断路由
* 静态按钮
* 不依赖 auth state

✔ 必须：

```ts
const { user, loading } = useAuth()
```

渲染规则：

* user == null → Login
* user.role == student → student menu
* user.role == teacher/admin → admin menu

---

# 🔧 Step 5：修复 login 卡住问题

必须保证：

* loading 永远 finally 关闭
* error 必须 catch
* router 必须 always execute or fallback

---

# 🔧 Step 6：强制端到端测试（必须模拟真实浏览器行为）

Codex 必须执行：

## Test 1：student login

* login → dashboard
* refresh → still logged in
* navbar correct

## Test 2：teacher login

* login → teacher dashboard
* navbar updates

## Test 3：admin login

* full access verified

## Test 4：logout

* cookie cleared
* auth state reset
* UI resets

---

# 🧪 Step 7：必须输出“失败链路定位”

Codex 必须明确回答：

* 为什么 login 页面没跳转
* 为什么 state 没更新
* 为什么 navbar 没变化

禁止只说“已修复”

---

# 🚫 禁止行为

* ❌ 不允许只改 backend
* ❌ 不允许只改 proxy
* ❌ 不允许只说 build success
* ❌ 不允许不做 /api/auth/me 链路验证
* ❌ 不允许 UI 静态判断

---

# 🏁 成功标准（非常关键）

## 登录行为必须一致：

### 任意角色：

```
login → auth state updated → redirect → UI changed → navbar correct
```

---

## UI必须满足：

* 登录前：Login
* 登录后：Role-based navbar
* 刷新后：仍保持登录状态

