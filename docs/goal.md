目标：在 jingchangshi/ClinicalLearningSystem 当前 commit 5fe8bbf8ce5d72542dfe8593911b995c50491948 基础上，完成“账户系统 + 权限系统 + 安全重构 + 一致性修复”，将系统升级为可真实部署的 AI 辅助医学教育平台。

---

一、核心新增目标：账户系统（必须实现）

1. 新增 User 模型：

- id
- username（唯一）
- password_hash（bcrypt）
- role: student / teacher / admin
- student_id（nullable）
- teacher_id（nullable）
- created_at

2. 新增认证系统：

- POST /auth/register
- POST /auth/login
- GET /auth/me

使用 JWT Token。

3. 登录后行为：

学生：
- 只能访问自己的 student dashboard / pathway / sessions

教师：
- 可访问 teacher dashboard / students / research

admin：
- 可访问全部 API

---

二、权限系统（必须实现）

1. 新增 auth dependency：

- get_current_user()
- require_role(["student"])
- require_role(["teacher", "admin"])

2. 所有 API 必须加权限：

学生接口：
- /api/students/*
必须验证 user.student_id 与 path student_id 一致

教师接口：
- /api/teacher/*
必须 teacher or admin

---

三、修复当前系统安全问题

1. 禁止前端传 student_id 直接访问数据
→ 改为 token 推导 student_id

2. teacher dashboard API 增加权限保护

3. sessions / pathway / dashboard 全部校验 user identity

---

四、修复数据一致性问题

1. weak_abilities：
- 必须 use_expanded=True
- 纳入八维能力模型

2. class_heatmap：
- 扩展为八维（新增 communication, humanistic_care, skill_operation）

3. average_improvement：
- 改为真实计算：
  - 最近 session score vs 历史 baseline

---

五、统一学习证据系统（必须严格执行）

1. 所有模块必须写入 LearningEvidenceEvent：

- knowledge quiz submit
- skill session submit
- case submit
- guideline submit
- SP submit

2. competency_update_service 必须统一调用：

- update_competency_from_knowledge
- update_competency_from_skill
- update_competency_from_case
- update_competency_from_guideline
- update_competency_from_sp

3. 禁止任何旧 _update_competency 逻辑残留

---

六、推荐系统修复

1. recommended_tasks 必须全部后端生成

2. 返回字段必须包括：

- type
- id
- title
- reason
- priority
- target_abilities
- source_evidence
- expected_lift
- difficulty_label
- next_step_label

3. 前端不得再根据 type 推断能力

---

七、账户系统与Student模型解耦（重要）

1. Student 不再代表用户身份
2. User 表是唯一登录实体
3. Student = 学习数据实体

关系：

User 1—1 Student
User 1—1 Teacher

---

八、前端适配修改

1. 登录后保存 token
2. 所有 API 自动带 Authorization header
3. 移除 studentId query-based trust
4. 改为 /me 获取 student context

---

九、验收标准

必须满足：

1. 用户可以注册/登录
2. student 只能访问自己的数据
3. teacher 可以查看所有学生
4. admin 可访问全部系统
5. 所有 competency 更新写入 event
6. 八维能力画像稳定更新
7. 推荐路径一致且可解释
8. npm run build 通过
9. 后端可启动无权限漏洞

