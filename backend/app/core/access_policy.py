"""Small, explicit public-access policy switches.

Nothing here replaces real authorization (that stays in ``app.auth``); these are
the knobs that decide how much an unauthenticated visitor may consume.
"""

import os

ENVIRONMENT = os.getenv("CLINPATH_ENV", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# Production defaults to closed: anonymous self-registration must be an explicit
# decision, because every registered account can spend paid model calls.
ALLOW_PUBLIC_REGISTRATION = _flag("ALLOW_PUBLIC_REGISTRATION", not IS_PRODUCTION)

# Bounded formative coaching: the tutor asks a few focused questions per step
# instead of becoming an unbounded chat that burns quota.
MAX_COACH_TURNS_PER_SESSION = int(os.getenv("MAX_COACH_TURNS_PER_SESSION", "20"))
MAX_SP_MESSAGES_PER_SESSION = int(os.getenv("MAX_SP_MESSAGES_PER_SESSION", "40"))
