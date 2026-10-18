"""Form-order (X/Y) sensitivity: does A01-vs-A02 difficulty contaminate the change?

X: T0=A01, T1=A02.  Y: T0=A02, T1=A01.  If A02 is harder/easier than A01, a form
effect delta enters change with opposite sign in X and Y:
    change_X = effect + delta,   change_Y = effect - delta.
delta_hat = (mean change_X - mean change_Y) / 2 pooled over all paired students
(form order is balanced inside cohorts, independent of study arm). Form-adjusted
change subtracts delta_hat for X and adds it for Y. This is a sensitivity analysis,
reported next to the unadjusted result, never instead of it.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from . import FORM_ORDERS, ResearchError


def form_effect(changes_by_order: Mapping[str, Sequence[float]], min_per_order: int = 3) -> dict:
    nx, ny = (len(changes_by_order.get(o, ())) for o in FORM_ORDERS)
    if nx < min_per_order or ny < min_per_order:
        return {"status": "insufficient_data", "n_X": nx, "n_Y": ny, "delta_hat": None,
                "reason": f"need >= {min_per_order} paired students in each form order"}
    mx = sum(changes_by_order["X"]) / nx
    my = sum(changes_by_order["Y"]) / ny
    return {"status": "ok", "n_X": nx, "n_Y": ny, "mean_change_X": mx, "mean_change_Y": my,
            "delta_hat": (mx - my) / 2.0}


def adjust_change(change: float, order: str, delta_hat: float) -> float:
    if order == "X":
        return change - delta_hat
    if order == "Y":
        return change + delta_hat
    raise ResearchError(f"unknown form order {order!r}")
