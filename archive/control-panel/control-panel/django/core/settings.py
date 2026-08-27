"""DB-backed settings store with in-memory caching.

Same public API (get_settings/update_settings/remember_value), same DEFAULTS,
same atomic-write guarantee (Django ORM update_or_create). The Setting model
lives in core.models with db_table=\"settings\" (schema parity with the
preserved /data/control-panel.db).

In-memory cache: get_settings() reads from a module-level dict after the
first DB hit. update_settings() and remember_value() invalidate the cache
so the next read re-fetches from DB. This eliminates redundant DB reads on
every API request while staying consistent.
"""
import json

from core.models import Setting

DEFAULTS = {
    "theme": "amber",
    "failed_pending_storm_threshold": 15,
    "loop_review_profile_threshold": 8,
    "recent_values": {},
}

# In-memory cache — None means "needs reload"
_cache: dict | None = None


def _load_from_db() -> dict:
    data = {row.key: json.loads(row.value_json) for row in Setting.objects.all()}
    return {**DEFAULTS, **data}


def _invalidate() -> None:
    global _cache
    _cache = None


def _persist_key(key: str, value) -> None:
    Setting.objects.update_or_create(key=key, defaults={"value_json": json.dumps(value)})


def get_settings() -> dict:
    """Return all settings, using in-memory cache after first DB hit."""
    global _cache
    if _cache is None:
        _cache = _load_from_db()
    return dict(_cache)  # return a copy so callers can't mutate the cache


def update_settings(patch: dict) -> dict:
    """Apply a settings patch and invalidate the cache."""
    data = _load_from_db()  # always read fresh to avoid stale merges
    for key, value in patch.items():
        if key in DEFAULTS:
            data[key] = value
            _persist_key(key, value)
    _invalidate()
    return data


def remember_value(arg_name: str, value: str, keep: int = 5) -> None:
    """Add a value to the recent_values list for an arg name."""
    data = _load_from_db()
    recent = data["recent_values"].setdefault(arg_name, [])
    if value in recent:
        recent.remove(value)
    recent.insert(0, value)
    del recent[keep:]
    _persist_key("recent_values", data["recent_values"])
    _invalidate()
