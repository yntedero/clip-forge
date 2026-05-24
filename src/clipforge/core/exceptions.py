"""Domain exception hierarchy.

All errors raised by ``clipforge.core`` are subclasses of
:class:`ClipForgeError` so callers can catch domain failures uniformly.
"""

from __future__ import annotations


class ClipForgeError(Exception):
    """Base for all domain errors."""


class ValidationError(ClipForgeError):
    """A domain-level validation failure raised by ClipForge code.

    NOT the same as ``pydantic.ValidationError``. Pydantic raises its own
    ``ValidationError`` when model construction fails; that exception
    inherits from ``ValueError`` and does NOT match this class. Callers
    that need to catch both must import them under distinct names:

        from pydantic import ValidationError as PydanticValidationError
        from clipforge.core.exceptions import ValidationError as DomainValidationError
    """


class PlanningError(ClipForgeError):
    """The planner cannot produce a valid plan for the given inputs."""


class PresetError(ClipForgeError):
    """A preset file is malformed, missing, or fails schema validation."""


class FilterBuildError(ClipForgeError):
    """The filter builder cannot construct a valid FFmpeg argument list."""
