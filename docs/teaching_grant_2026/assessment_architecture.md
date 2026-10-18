# ClinPath independent assessment / training separation

## Product status

Feature branch: `feat/clinpath-independent-assessment-2026`.
Source basis: `teaching-grant-2026-wpd@25a9177`.
Status: implemented as code, **not locally test-executed by ChatGPT**, not deployed, medical content unapproved.

## Trust boundaries

- Training: existing `Case`, `CaseSession`, `StudentAnswer`, `Score`, `CompetencyProfile`, `LearningRecommendation`, tutor and teacher intervention APIs unchanged.
- Assessment: separate `AssessmentForm`, `AssessmentFormReview`, `AssessmentSitting`, `AssessmentAnswer`, `AssessmentReview` tables.
- Assessment endpoints never import training scoring or AI coach, cannot write `Score`, `CaseSession`, `CompetencyProfile` or `LearningRecommendation`.
- Teacher-review endpoints show no student name, cohort, group or T0/T1, but cannot eliminate identity voluntarily typed into an answer. Student instructions must prohibit personally identifying details.
- Answer key, rubric, and staged information available only to independently authenticated teachers/admins. Students see only the active stage.
- Administrator alone connects blind codes to group, cohort and timepoint for research export. Export contains sensitive linkage and must remain in a controlled environment.

## Usage

1. Apply migrations through `20261018_08` on an isolated database copy; do not auto-migrate production.
2. Admin opens `/teacher/assessment-admin`, creates a new five-stage AssessmentForm from reviewed JSON.
3. Two genuinely different teacher accounts open `/teacher/assessment-forms` and independently approve it, commenting on medical facts/rubric. Admin finalizes form approval only after both have approved.
4. Admin schedules a sitting for each student and timepoint with `student_id`, `cohort_code`, `study_group`, `form_id`, 2 assigned rater user IDs and UTC window.
5. Student opens `/student/assessments` only during the permitted window; answers each stage once without AI coaching or feedback.
6. Assigned raters open `/teacher/assessments`; blind codes have no group/timepoint/student details. Each scorer's six scores are locked and separate from the other.
7. Admin exports research-linked records. A separate analysis process can compute agreement and resolve disagreements; **automatic third-rater adjudication and lock-based final dataset freeze are not yet implemented**.

## Known unfinished acceptance work

- Automated test suite, typecheck, production-like role test, migration upgrade/downgrade and isolated end-to-end browser tests **have not yet been run by ChatGPT**.
- Admin scheduling currently supports one sitting at a time, not batch scheduling. Research randomization and X/Y form assignment must be recorded separately; current form-assign UI is basic.
- Final grade adjudication, rater-overlap checks at longitudinal blinded dataset level, revocation/resit workflow, autosave/interruption resilience, and dataset lock have not been implemented.
- User input is not sanitized for accidental identification inside answers; exam instructions and human review are required.
- Current form review approvals are teacher-account attestations; authentic human review and signature provenance must be established by the institution.
- Rubric dimensions currently share preliminary 10/20/25/15/20/10 weights pending expert signoff.
- All A01/A02 medical cards remain PENDING_REAL_REVIEW. A02 no longer contains AOSD; old AOSD form should never be approved for this trial.
- D research-demo's simulated 60 students remain isolated, unrelated to this new real assessment workflow.
