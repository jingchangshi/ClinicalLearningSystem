"""Read-only teacher API for the synthetic teaching-research demo (work package D).

This router deliberately has **no database dependency**. It serves the versioned
files under ``demo_research/synthetic_v1`` through
``app.services.demo_research``, which means a request to any of these endpoints
can never read or write a real student, a real case session, or a real teacher
review. That is the whole isolation argument, and ``tests/test_demo_research.py``
asserts it (including that the production table row counts are unchanged).

The teacher role requirement matches the rest of ``/api/teacher``; students and
anonymous callers get 401/403 before any file is opened.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.auth import require_role
from app.services import demo_research

router = APIRouter(
    prefix="/api/teacher/demo-research",
    tags=["teacher-demo-research"],
    dependencies=[Depends(require_role(["teacher"]))],
)

EXPORT_FILENAME = "clinpath-SYNTHETIC-demo-research-v1.csv"


def _dataset() -> demo_research.DemoDataset:
    try:
        return demo_research.load_dataset()
    except FileNotFoundError as error:
        # A deployment missing the demo asset must say so, not serve an empty
        # page that looks like "there are no participants".
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/meta")
def demo_research_meta() -> dict:
    dataset = _dataset()
    return demo_research.meta_payload(dataset)


@router.get("/summary")
def demo_research_summary() -> dict:
    dataset = _dataset()
    return {
        "banner": demo_research.BANNER,
        "data_origin": demo_research.DATA_ORIGIN,
        "rater_origin": demo_research.RATER_ORIGIN,
        **demo_research.compute_summary(dataset),
    }


@router.get("/students")
def demo_research_students(
    group: str | None = Query(default=None, pattern="^(CBL|CLINPATH)$"),
    q: str | None = Query(default=None, max_length=40),
) -> dict:
    dataset = _dataset()
    rows = demo_research.list_students(dataset, group=group, query=q)
    return {
        "banner": demo_research.BANNER,
        "data_origin": demo_research.DATA_ORIGIN,
        "rater_origin": demo_research.RATER_ORIGIN,
        "count": len(rows),
        "students": rows,
    }


@router.get("/students/{study_id}")
def demo_research_student(study_id: str) -> dict:
    dataset = _dataset()
    detail = demo_research.student_detail(dataset, study_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="unknown synthetic study_id")
    return {
        "banner": demo_research.BANNER,
        "data_origin": demo_research.DATA_ORIGIN,
        "rater_origin": demo_research.RATER_ORIGIN,
        **detail,
    }


@router.get("/dictionary")
def demo_research_dictionary() -> dict:
    dataset = _dataset()
    return {
        "banner": demo_research.BANNER,
        "data_origin": demo_research.DATA_ORIGIN,
        "fields": demo_research.dictionary_payload(dataset),
    }


@router.get("/expert-review")
def demo_research_expert_review() -> dict:
    dataset = _dataset()
    return {
        "banner": demo_research.BANNER,
        "status": "PENDING_REAL_REVIEW",
        "note": "真实教师审核尚未进行；收到带日期与签名的原始记录前不得标记为已审核。",
        "rows": demo_research.expert_review_payload(dataset),
    }


@router.get("/export.csv")
def demo_research_export_csv() -> Response:
    """The synthetic study dataset as a spreadsheet a reviewer can inspect.

    The filename, the header row and every data row carry the synthetic marker.
    There is no query parameter that turns that off.
    """

    dataset = _dataset()
    rows = demo_research.export_rows(dataset)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "SYNTHETIC_DATA_ORIGIN",
            "study_id",
            "group",
            "cohort",
            "pre_score_T0",
            "post_score_T1",
            "gain_score",
            "rater_origin",
            "training_sessions",
            "reasoning_steps",
            "simulation_seed",
            "DISCLAIMER",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["data_origin"],
                row["study_id"],
                row["group"],
                row["cohort"],
                row["pre_score_T0"],
                row["post_score_T1"],
                row["gain_score"],
                row["rater_origin"],
                row["training_sessions"],
                row["reasoning_steps"],
                row["simulation_seed"],
                "模拟数据，不代表真实教学成效",
            ]
        )
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{EXPORT_FILENAME}"',
            # A proxy or browser cache must never hand this file out as if it
            # were the real research export.
            "X-Data-Origin": demo_research.DATA_ORIGIN,
        },
    )
