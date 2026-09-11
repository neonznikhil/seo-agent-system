"""Canonical SEO thresholds — spec'd import path.

Single source of truth lives in backend/seo_constants.py; this module
re-exports it so `services.seo_constants` and `seo_constants` never diverge.
"""
try:
    from seo_constants import (  # noqa: F401
        STRIKING_DISTANCE_MIN,
        STRIKING_DISTANCE_MAX,
        INDEXATION_GATE_THRESHOLD,
        QA_MIN_WORDS,
        QA_MIN_INTERNAL_LINKS,
        QA_TITLE_MIN_CHARS,
        QA_TITLE_MAX_CHARS,
        QA_META_MIN_CHARS,
        QA_META_MAX_CHARS,
        DECAY_THRESHOLD,
        is_striking_distance,
        get_site_striking_range,
    )
except (ImportError, ValueError):  # pragma: no cover
    from backend.seo_constants import (  # noqa: F401
        STRIKING_DISTANCE_MIN,
        STRIKING_DISTANCE_MAX,
        INDEXATION_GATE_THRESHOLD,
        QA_MIN_WORDS,
        QA_MIN_INTERNAL_LINKS,
        QA_TITLE_MIN_CHARS,
        QA_TITLE_MAX_CHARS,
        QA_META_MIN_CHARS,
        QA_META_MAX_CHARS,
        DECAY_THRESHOLD,
        is_striking_distance,
        get_site_striking_range,
    )
