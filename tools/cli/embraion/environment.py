"""Environment boundaries between an active runtime and independent children."""

from __future__ import annotations

import os
from collections.abc import Mapping


RESOLUTION_GUARD_ENV = "EMBRAION_VERSION_RESOLVED"
RESOLVED_VERSION_ENV = "EMBRAION_RESOLVED_VERSION"
RESOLVED_PROJECT_ENV = "EMBRAION_RESOLVED_PROJECT"


def child_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Drop resolver-owned state; retain explicit user development overrides."""
    result = dict(os.environ if environment is None else environment)
    if result.get(RESOLUTION_GUARD_ENV) == "1":
        # The resolver sets HOME for its own interpreter, not for project tools.
        result.pop("EMBRAION_HOME", None)
    for name in (RESOLUTION_GUARD_ENV, RESOLVED_VERSION_ENV, RESOLVED_PROJECT_ENV):
        result.pop(name, None)
    return result
