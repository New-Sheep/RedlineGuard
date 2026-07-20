"""Shared upload size validation (PRD F1 — 10 MB)."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError


def max_upload_bytes() -> int:
    return int(getattr(settings, "MAX_UPLOAD_BYTES", 10 * 1024 * 1024))


def validate_upload_size(upload) -> None:
    """Raise ValidationError if file exceeds MAX_UPLOAD_BYTES."""
    if upload is None:
        return
    size = getattr(upload, "size", None)
    if size is None:
        return
    limit = max_upload_bytes()
    if size > limit:
        mb = limit / (1024 * 1024)
        raise ValidationError(
            f"File too large ({size / (1024 * 1024):.1f} MB). Max upload is {mb:.0f} MB."
        )
