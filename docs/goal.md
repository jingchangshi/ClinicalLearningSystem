# ✅ Codex Goal Prompt（最终修复 + 账户系统完整闭环）

## 🎯 项目目标

对 `ClinicalLearningSystem` 当前版本进行**账户系统最终收敛修复与UI闭环重构**，确保：

> 登录系统不仅“API正确”，而且“用户体验完整一致”。

---

# 🧠 一、必须先做的系统级诊断（强制）

Codex 必须执行以下分析并输出报告：

## 1. 登录失败路径分析（重点 teacher/admin）

检查：

* frontend login request payload
* login role 参数是否传递
* backend login route 是否正确解析 role
* teacher/admin 用户数据库字段
* JWT/cookie 是否正确写入 role
* proxy.ts 是否误判 role

输出：

```
- student login success chain
- teacher login failure point
- admin login failure point
```

---

## 2. UI 状态未更新原因分析

检查：

* auth context / global state
* cookie → frontend state hydration
* /api/auth/me 是否在登录后触发
* navbar 是否依赖 stale state
* 是否存在 hardcoded menu（student/teacher按钮）

---

## 3. 登录“卡住2秒恢复”的原因分析

重点检查：

* login loading state未正确 reset
* promise reject未 catch
* router push 未执行
* middleware redirect loop
* role mismatch silent fail

---

# 🔧 二、必须修复的问题（强制执行）

---

## ❗Fix 1：统一登录角色系统（核心修复）

### 要求：

backend login 必须：

```ts
return {
  id,
  username,
  role: "student" | "teacher" | "admin"
}
```

cookie 必须包含：

```
access_token (JWT with role embedded)
```

---

## ❗Fix 2：修复 teacher/admin 登录失败

必须检查并修复：

* 用户表 role 字段映射错误
* login service 忽略 role
* JWT encode 未包含 role
* frontend login 未传 role 或 selector

👉 要求：

✔ teacher login 必须成功
✔ admin login 必须成功
✔ student 不受影响

---

## ❗Fix 3：统一 Auth State（关键UI问题）

必须新增或修复：

### frontend auth state layer

```ts
auth.user
auth.role
auth.isAuthenticated
auth.loading
```

登录后必须：

1. 调用 `/api/auth/me`
2. 更新全局 state
3. 触发 navbar rerender

---

## ❗Fix 4：彻底重构 Navbar（UI闭环）

当前问题：

> 仍显示 student/teacher 登录按钮（旧系统残留）

必须改为：

### 未登录状态：

* Login

### student：

* Dashboard
* Pathway
* Profile
* Logout

### teacher/admin：

* Teacher Dashboard
* Class Analytics
* Students Overview
* Logout

---

## ❗Fix 5：登录流程修复（卡住问题）

必须保证：

```text
login click
→ setLoading(true)
→ POST /api/auth/login
→ success
→ call /api/auth/me
→ setUser()
→ router.push(role dashboard)
→ setLoading(false)
```

任何失败必须：

* setLoading(false)
* show error

---

## ❗Fix 6：middleware 统一修复

必须保证：

* /login 永远可访问
* /demo 永远可访问
* /student/* 仅 student
* /teacher/* 仅 teacher/admin
* role mismatch → redirect /login（不循环）

---

# 🧪 三、强制回归测试（Codex必须执行）

## 登录测试：

### student：

* login success
* dashboard OK
* navbar correct

### teacher：

* login success
* teacher dashboard OK
* navbar correct

### admin：

* login success
* full access OK

---

## UI测试：

* login → navbar变化
* refresh → state恢复
* logout → state清空
* no stale buttons

---

## API测试：

* /api/auth/login 200
* /api/auth/me 200
* role mismatch 403
* cookie persistent

---

# 🧹 四、禁止行为（非常重要）

Codex 不允许：

* ❌ 保留 student/teacher 混合导航旧UI
* ❌ 双 auth system（token + cookie）
* ❌ localStorage fallback
* ❌ role hardcode in frontend
* ❌ login success 但 UI 不更新
* ❌ 静默失败（必须可见错误）

---

# 📦 五、输出要求

Codex必须输出：

1. teacher/admin 登录失败 root cause
2. navbar 不更新 root cause
3. loading 卡住 root cause
4. 修改文件列表
5. 每个修复说明
6. 最终验证结果（逐条）

---

# 🏁 六、成功标准（非常关键）

系统必须达到：

## 认证层：

* 三类用户全部可登录
* role 完整贯通 backend → cookie → frontend

## UI层：

* navbar 完全动态
* 登录后立即变化
* 无旧系统残留

## 体验层：

* login 无卡顿
* 无“登录中停住”
* 无状态错乱

