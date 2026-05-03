"""Classification constants and regexes for log detection."""

from __future__ import annotations

import re

ERROR_LEVELS = {"error", "fatal", "critical", "panic"}
NON_ERROR_LEVELS = {"info", "debug", "trace", "notice", "warn", "warning"}
ERROR_HINT_RE = re.compile(
    r"(?:\bexception\b|\berror\b|\bfail(?:ed|ure)?\b|\bpanic\b|\btraceback\b|"
    r"\btimeout\b|\bdenied\b|\bunavailable\b|\bsegfault\b|\bassert(?:ion)?\b|\bcrash(?:ed)?\b)",
    re.IGNORECASE,
)
HTTP_5XX_RE = re.compile(r"\b5\d\d\b")
MAX_RARE_TEMPLATE_COUNT = 2
MIN_TEMPLATES_FOR_ROBUST_SCORING = 8
PROGRESS_STEP_PERCENT = 10
