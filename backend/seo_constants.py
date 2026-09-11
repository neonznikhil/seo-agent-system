"""Canonical SEO thresholds and definitions.

Single source of truth — every module that classifies striking-distance
keywords or gates on indexation MUST import from here, never hardcode its
own range. Per-site overrides live in autonomous_settings / site settings
(striking_min, striking_max, indexation_threshold); these are the defaults.
"""

# Striking distance: positions close enough to page 1 that focused work
# (internal links, refresh, intent match) can plausibly move them up.
STRIKING_DISTANCE_MIN = 11
STRIKING_DISTANCE_MAX = 20

# Indexation gate: minimum share of submitted pages that must be indexed
# before normal publishing cadence is allowed. Configurable per site.
INDEXATION_GATE_THRESHOLD = 0.80

# QA / content minimums enforced by the deterministic QA gate.
QA_MIN_WORDS = 1800
QA_MIN_INTERNAL_LINKS = 2
QA_TITLE_MIN_CHARS = 30
QA_TITLE_MAX_CHARS = 65
QA_META_MIN_CHARS = 140
QA_META_MAX_CHARS = 160

# Decay: a page counts as decaying when its GSC click/position decay
# exceeds this fraction versus the prior 28-day period.
DECAY_THRESHOLD = 0.15


def is_striking_distance(position, sd_min: int = STRIKING_DISTANCE_MIN,
                         sd_max: int = STRIKING_DISTANCE_MAX) -> bool:
    """One definition of striking distance, used everywhere."""
    try:
        pos = float(position)
    except (TypeError, ValueError):
        return False
    return sd_min <= pos <= sd_max


def get_site_striking_range(settings: dict) -> tuple:
    """Per-site override (striking_min/striking_max in site settings or
    goals JSON), else the global defaults."""
    settings = settings or {}
    goals = settings.get("goals") or {}
    try:
        sd_min = int(settings.get("striking_min", goals.get("striking_min", STRIKING_DISTANCE_MIN)))
    except (TypeError, ValueError):
        sd_min = STRIKING_DISTANCE_MIN
    try:
        sd_max = int(settings.get("striking_max", goals.get("striking_max", STRIKING_DISTANCE_MAX)))
    except (TypeError, ValueError):
        sd_max = STRIKING_DISTANCE_MAX
    if sd_min < 1:
        sd_min = STRIKING_DISTANCE_MIN
    if sd_max < sd_min:
        sd_max = STRIKING_DISTANCE_MAX
    return sd_min, sd_max
