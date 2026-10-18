# CASE-A02 replacement review checklist

Replaced the AOSD/MAS case with a new draft on unresolved sicca symptoms and suspected Sjögren disease. Neither is currently approved. Two qualified real rheumatology teachers must review this draft and CASE-A01 for medical correctness, difficulty matching, discriminating power, unbiased scoring anchors and handling of incomplete evidence.

The original AOSD case remains in Git history but is **superseded and excluded from the active independent assessment set**. Do not copy it into the new AssessmentForm.

The two assessors should check that the actual current training catalog, SP sessions, guideline exercises, and student-visible cases do not disclose this specific assessment scenario. Do not claim disease-level nonoverlap merely from the 4 draft teaching cards.

## 2026-10-18 technical/medical DRAFT re-check (AI; NOT teacher approval)

Changes made to the r1 sicca draft, and why (details in `A01_assessment_sicca.md` and `review_forms/REVISION_REREVIEW_LOG.md`):

- Student-visible title and stage questions rewritten to be neutral. r1 put "疑似原发性干燥综合征" in the title and "不能仅凭目前证据做最终判断" / "解释阴性抗SSA的局限" in the questions, which handed students the hypothesis and the key reasoning.
- S5 no longer says the lip biopsy "has not been performed" (a cue that biopsy is the answer); the biopsy and salivary flow decision is now left to the student.
- HCV exclusion: r1 said "no known HCV infection". The 2016 exclusion is *active* HCV (PCR-confirmed), so the case now gives anti-HCV and HIV antibody results.
- Ocular staining was unquantified, so criteria could not be scored; now OSS 5/4. Scoring now shows 2 known points (Schirmer 1 + OSS 1, anti-SSA 0, saliva and biopsy not assessed), below the threshold of 4. With anti-SSA negative, non-invasive testing can reach at most 3, so lip biopsy (or a repeat positive anti-SSA) is decisive.
- Added the main confounders and negatives needed for a consistent picture: 3-month antihistamine washout, regular menses, normal glucose/HbA1c/TSH, normal urinalysis, normal C3/C4, mildly raised ESR and IgG (non-specific, not criteria items).
- Parotid ultrasound is kept as a non-criteria adjunct and labelled as such.
- Rubric anchors added to the payload (high/mid/low per dimension); weights 10/20/25/15/20/10 remain pending teacher confirmation.
- Citations: 2016 ACR/EULAR (ARD and Arthritis Rheumatol versions), EULAR 2020 management, AECG 2002, Daniels 2011, TFOS DEWS II verified as bibliographic records; the Chinese 2020 guideline, ESSDAI original and any seronegative-SjD figures are marked UNVERIFIED.

Technical status: independent assessment backend is under development on the feature branch; don't label this case approved until authentic signed review artifacts are received.
