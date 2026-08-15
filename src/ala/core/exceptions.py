"""Typed exception hierarchy.

A single root (``AlaError``) lets callers catch "anything from the platform"
while specific subclasses allow precise handling. Never raise bare ``Exception``.
"""

from __future__ import annotations


class AlaError(Exception):
    """Root of all ALA-raised errors."""


class ConfigError(AlaError):
    """Configuration file missing, malformed, or internally inconsistent."""


class ValidationError(AlaError):
    """A resource failed one or more validation rules."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []


class CatalogError(AlaError):
    """A catalog (SQLite) operation failed."""


class ResourceNotFoundError(AlaError):
    """Lookup for a resource_id that is not in the catalog."""


class DuplicateResourceError(AlaError):
    """Attempt to register a resource_id that already exists as ACTIVE."""


class RegistryError(AlaError):
    """A registry orchestration step failed."""


class TaxonomyError(AlaError):
    """A classification value is not present in the configured taxonomy."""
