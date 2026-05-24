"""Domain exception hierarchy.

All errors raised by ``clipforge.core`` are subclasses of
:class:`ClipForgeError` so callers can catch domain failures uniformly.
"""

from __future__ import annotations


class ClipForgeError(Exception):
    """Base for all domain errors."""


class ValidationError(ClipForgeError):
    """A domain-level validation failure surfaced from a model or function."""


class PlanningError(ClipForgeError):
    """The planner cannot produce a valid plan for the given inputs."""


class PresetError(ClipForgeError):
    """A preset file is malformed, missing, or fails schema validation."""


class FilterBuildError(ClipForgeError):
    """The filter builder cannot construct a valid FFmpeg argument list."""
