# AGENTS.md — ClinPath working agreement

Operational rules for any agent (or human) changing this repository. Deep design
lives in `docs/ARCH.md`; this file is the short version you read first.

## Repository mission

ClinPath / 诊途 is a clinical **learning** system, not a medical chatbot and not a
clinical decision tool. The loop it exists to serve:

```
Clinical learning evidence
        ↓
Reasoning / skills / knowledge / guideline / SP training
        ↓
Formative assessment
        ↓
Learning evidence
        ↓
Competency model
        ↓
Adaptive recommendation
        ↓
Teacher review
        ↓
Updated learner model
```

Every change should make that loop more reliable, more traceable, or more honest
about what actually happened.

## Source-of-truth routing

```
Architecture / invariants        → docs/ARCH.md
Product quick start / deployment → README.md
Backend API / business logic     → backend/app/
Frontend UX                      → frontend/
Database evolution               → backend/alembic/
Tests                            → backend/tests/, frontend/tests/e2e/
Deployment                       → deploy/, scripts/
```

- Read `docs/ARCH.md` before changing architecture.
- Architecture changes must update `docs/ARCH.md` in the same change.
- `README.md` documents how to run things; it must not contradict real configuration.
- `docs/goal.md` is a historical task brief, **not** an architecture source of truth.
  Never re-implement something because an old TODO still mentions it.

## Development invariants

1. The FastAPI backend is the final authority for authentication and authorization.
   The Next.js proxy may only do coarse routing; it must verify the JWT before
   trusting any claim, and it must never be the only check.
2. Students must never receive hidden answers: `standard_diagnosis`,
   `treatment_plan`, `rubric`, hidden SP history.
3. AI may be unavailable — falling back to rules is allowed, but the result must be
   explicitly marked `degraded` / `rule_fallback`. Never present rule output as AI.
   Every AI capability must leave an `ai_invocations` audit event (metadata and an
   evidence reference only — never prompt or response bodies).
4. Teacher-confirmed assessments keep their provenance (who, when, what, original AI
   and rule scores).
5. Never evolve the database by resetting it. Migrations only, with a **timestamped
   SQLite backup before any schema or data change**; `seed_data --reset` is forbidden
   in production.
6. Never commit or print API keys, JWT secrets, or `.env` contents.
7. One logical answer per `(session, step)`; a training event must never be counted
   into competency twice.
8. Learning evidence must stay traceable back to the session that produced it.
9. Every production change is tested before deployment, and deployment ends with a
   real browser verification.

## Definition of Done

```
implementation
+ backend tests            (uv run --python 3.11 --with-requirements requirements.txt pytest -q)
+ frontend typecheck/lint  (npm run typecheck && npm run lint)
+ frontend build           (npm run build)
+ Playwright               (npx playwright test)
+ production deployment    (systemd user units on the VPS)
+ real browser smoke test  (login → training → result → logout)
+ console/network inspection
+ architecture docs updated
+ ./scripts/verify_deploy.sh green (running source == this checkout, schema at head)
```

A task is not done because tests pass in isolation or because a page "should" work.
Report only what you actually observed, and say which SHA was running.
