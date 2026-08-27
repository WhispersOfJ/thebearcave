"""Shared Radarr/Sonarr config + helpers — backward-compatible re-export hub.

All implementations now live in focused modules:

  core/arr_config   — ARR_APPS, QUEUE_ARR_APPS, RADARR_APPS, PROWLARR_CFG
  core/arr_movie    — radarr_add_movie, blocklist_and_research, etc.
  core/arr_series   — sonarr_add_series, sonarr_root_folder_and_profile
  core/arr_queue    — arr_queue, format_eta, dedup_suffix_hit, etc.
  core/arr_import   — dd_test_file, find_candidate_files
  core/formatters   — human_size

New code should import directly from the focused modules.
"""
from core.arr_config import (  # noqa: F401
    ARR_APPS,
    HOST_CONFIG_DIR,
    PROWLARR_API_KEY,
    PROWLARR_CFG,
    QUEUE_ARR_APPS,
    RADARR_APPS,
    SONARR_APPS,
)
from core.formatters import human_size  # noqa: F401
from core.nzbdav_client import NZBDAV_API_KEY, NZBDAV_URL, nzbdav_api  # noqa: F401
from core.arr_movie import (  # noqa: F401
    blocklist_and_research,
    get_movie_or_episode,
    item_is_monitored,
    radarr_add_movie,
    radarr_ensure_tags,
    radarr_quality_profile_id_by_name,
    radarr_root_folder_and_profile,
)
from core.arr_series import (  # noqa: F401
    sonarr_add_series,
    sonarr_root_folder_and_profile,
)
from core.arr_queue import (  # noqa: F401
    DEDUP_SUFFIX_RE,
    MIN_RATE_WINDOW_HOURS,
    RECENT_IMPORT_LOOKBACK_HOURS,
    RECENT_IMPORT_SAMPLE_SIZE,
    arr_command,
    arr_queue,
    arr_sizeleft_snapshot,
    current_queue_output_path,
    dedup_suffix_hit,
    disable_autoredownload_if_storm,
    format_eta,
    import_candidate_queue_items,
    importing_queue_targets,
    recent_import_rate_per_hour,
    require_queue_app,
    stuck_queue_items,
    wanted_missing_total,
)
from core.arr_import import (  # noqa: F401
    IMPORTING_TEST_MB,
    IMPORTING_TEST_TIMEOUT_S,
    dd_test_file,
    find_candidate_files,
)
