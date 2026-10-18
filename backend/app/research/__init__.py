"""Pure, DB-free research statistics for the 7-cohort exploratory study.

Nothing here touches the database, the clock or the network: every function is a
deterministic transform of its arguments, so a frozen dataset reproduces the same
numbers later. Persistence is wired elsewhere.

The study is exploratory (feasibility and effect-signal generation). 7 clusters
cannot support confirmatory superiority claims, and no function in this package
produces one.
"""

DATA_ORIGIN_REAL = "real_study"
DATA_ORIGIN_DEMO = "synthetic_demo"
DATA_ORIGIN_PILOT = "pilot_test"
DATA_ORIGINS = (DATA_ORIGIN_REAL, DATA_ORIGIN_DEMO, DATA_ORIGIN_PILOT)

STUDY_GROUP_CLINPATH = "clinpath"
STUDY_GROUP_CBL = "cbl"
STUDY_GROUPS = (STUDY_GROUP_CLINPATH, STUDY_GROUP_CBL)

MODE_RANDOMIZED = "randomized"
MODE_QUASI = "quasi_experimental"

FORM_ORDERS = ("X", "Y")
# X: T0=A01, T1=A02; Y: T0=A02, T1=A01.
FORM_BY_ORDER = {"X": {"T0": "A01", "T1": "A02"}, "Y": {"T0": "A02", "T1": "A01"}}


class ResearchError(ValueError):
    """Base class for refusals raised by the research modules."""


class MixedDataOriginError(ResearchError):
    """Rows with different data_origin values (or a non-real origin) were combined."""


class QuasiExperimentalError(ResearchError):
    """A randomization-test conclusion was requested for a non-randomized design."""


class RandomizationOrderError(ResearchError):
    """Form order was not frozen before the group draw, or the record is inconsistent."""
