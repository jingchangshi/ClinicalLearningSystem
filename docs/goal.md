# 🚨 当前真实问题总结（必须修）

## ❌ 问题1：LLM系统未完全可用 / 未统一 DeepSeek V4

* LLM可能仍存在分散调用
* prompt不统一
* 部分模块未接入 LLMService
* fallback逻辑可能覆盖真实调用

---

## ❌ 问题2：页面无页边距 + UI不统一

* layout 没有统一 container
* 学生/教师页面紧贴边缘
* demo vs main style 不一致

---

## ❌ 问题3：学生端 Navbar 丢失 Pathway

* route group 重构后 navbar config 未同步
* role-based menu 渲染不完整
* student menu 缺失 pathway entry

---

# 🧠 Codex 必须理解的系统状态

当前架构是：

```text
AuthProvider (main only)
   ↓
/api/auth/me (cookie)
   ↓
role-based navbar
   ↓
student / teacher / admin pages
   ↓
LLMService (DeepSeek v4)
```

但问题是：

> ❗ LLM层未“统一收敛”
> ❗ UI layout 未“设计系统化”
> ❗ Navbar config 不完整

---

# 🚀 FINAL CODEX PROMPT（强约束修复版）

---

# 🎯 TASK: Final System Stabilization (LLM + UI + Navbar Fix)

---

# 🧠 Step 1：统一 DeepSeek V4 LLM 架构（关键修复）

## 必须执行：

### 1. 确保只有一个 LLM 入口

路径必须统一：

```text
backend/app/services/llm_service.py
```

❌ 禁止：

* 各模块直接调用 deepseek
* 重复 client
* prompt scattered

---

## 2. 强制 DeepSeek V4 client 标准化

```python
class DeepSeekClient:
    def __init__(self):
        self.base_url = os.getenv("DEEPSEEK_BASE_URL")
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.model = "deepseek-chat"

    def chat(self, messages):
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        ).chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3
        )
```

---

## 3. 必须统一 LLM 调用入口

### 所有模块必须改为：

```text
CaseService → LLMService
PathwayService → LLMService
FeedbackService → LLMService
TeacherInsight → LLMService
```

---

## 4. prompt必须结构化（禁止散写）

必须新增：

```text
backend/app/llm/prompts/
    case_generation.py
    pathway.py
    evaluation.py
    insight.py
```

---

# 🧠 Step 2：修复 UI 页边距（全局设计系统）

---

## ❗问题

当前页面：

* 内容贴边
* 没有统一 container
* demo/main style 不一致

---

## ✅ 强制修复：

### 1. 新增全局 layout wrapper

```tsx
<div className="app-container">
```

---

### 2. 全局 CSS 必须加入：

```css
.app-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.page-container {
  padding: 24px 32px;
}
```

---

### 3. 所有页面必须统一：

* student pages
* teacher pages
* dashboard pages

全部包裹：

```tsx
<div className="page-container">
```

---

# 🧠 Step 3：修复 Navbar 丢失 Pathway（关键bug）

---

## ❗问题

student role menu missing:

* Pathway route 丢失
* route-group restructure 未同步 navbar config

---

## ✅ 必须修复：

### student navbar config 必须为：

```ts
studentMenu = [
  "Dashboard",
  "Pathway",   ← 必须恢复
  "Knowledge",
  "Profile"
]
```

---

### 路由必须映射：

```text
/student/pathway → existing page or restore page
```

---

### 如果页面缺失：

必须补：

```text
frontend/app/student/pathway/page.tsx
```

---

# 🧠 Step 4：统一 Navbar 生成逻辑（非常重要）

---

## ❗禁止静态 navbar

必须：

```ts
const menu = getMenuByRole(user.role)
```

---

## role mapping：

### student

* Dashboard
* Pathway
* Profile
* Logout

### teacher

* Dashboard
* Students
* Analytics
* Logout

### admin

* Dashboard
* System
* Users
* Logout

---

# 🧠 Step 5：端到端验证（必须执行 Playwright）

---

## Test A：LLM验证

* case generation → DeepSeek v4 response
* pathway generation → structured output
* fallback only if API key missing

---

## Test B：UI layout

* all pages have padding
* no edge-to-edge content
* consistent width

---

## Test C：Navbar

student login:

* Pathway visible ✔
* Dashboard works ✔

teacher login:

* correct menu ✔

---

## Test D：routing

* direct /student/pathway works
* navbar click works
* refresh preserved

---

# 🧨 禁止行为（非常重要）

* ❌ 不允许 demo UI 改动影响 main
* ❌ 不允许多个 LLM client
* ❌ 不允许 inline prompt scattered
* ❌ 不允许 navbar hardcoded
* ❌ 不允许页面无 container

---

# 🏁 成功标准

必须全部满足：

## LLM

✔ DeepSeek v4 single entry
✔ structured prompt system
✔ all modules unified

## UI

✔ consistent padding
✔ centered layout
✔ professional dashboard spacing

## Navbar

✔ Pathway restored
✔ role-based correct menu
✔ no missing routes

