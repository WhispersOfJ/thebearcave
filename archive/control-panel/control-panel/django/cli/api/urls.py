from django.urls import path

from cli.api.views import (
    # Container & Stack
    CliStatusView,
    CliContainerActionView,
    CliRestartAllView,
    CliResourceCheckView,
    CliOomCheckView,
    CliTopView,
    CliDiskUsageView,
    CliMountHealthView,
    CliPermsCheckView,
    CliVersionView,
    # Arr
    CliArrCommandView,
    CliArrBacklogView,
    CliArrMissingAiredView,
    CliArrImportCandidatesView,
    CliArrImportView,
    CliArrBlocklistView,
    CliArrRecentlyAddedView,
    CliArrImportStarvationView,
    CliArrQueueErrorsView,
    CliQueueStatusView,
    CliQueueAutofixView,
    # NzbDAV
    CliNzbdavQueueView,
    CliNzbdavHistoryView,
    CliNzbdavStatsView,
    CliNzbdavDeleteFailuresView,
    CliNzbdavDedupCheckView,
    # Plex
    CliPlexLibrariesView,
    CliPlexSessionsView,
    CliPlexRecentlyAddedView,
    # WatchState
    CliWatchstateStatusView,
    CliWatchstateImportView,
    CliWatchstateHistoryView,
    # Cleanuparr
    CliCleanuparrInstancesView,
    CliCleanuparrStrikesView,
    # Log Levels
    CliLogLevelsView,
    # Seerr
    CliSeerrRequestsView,
    # Notifications
    CliNotifyTestView,
    # List Imports
    CliLetterboxdImportView,
    CliMdblistImportView,
    # Loop Remediation
    CliLoopCandidatesView,
    CliLoopUnmonitorView,
    CliLoopExcludeView,
)

app_name = "cli"

urlpatterns = [
    # Container & Stack
    path("status", CliStatusView.as_view(), name="status"),
    path("container/<str:name>/<str:action>", CliContainerActionView.as_view(), name="container_action"),
    path("stack/restart-all", CliRestartAllView.as_view(), name="restart_all"),
    path("resource-check", CliResourceCheckView.as_view(), name="resource_check"),
    path("oom-check", CliOomCheckView.as_view(), name="oom_check"),
    path("top", CliTopView.as_view(), name="top"),
    path("disk-usage", CliDiskUsageView.as_view(), name="disk_usage"),
    path("mount-health", CliMountHealthView.as_view(), name="mount_health"),
    path("perms-check", CliPermsCheckView.as_view(), name="perms_check"),
    path("version", CliVersionView.as_view(), name="version"),
    # Arr
    path("arr/<str:app>/command/<str:command>", CliArrCommandView.as_view(), name="arr_command"),
    path("arr/<str:app>/backlog", CliArrBacklogView.as_view(), name="arr_backlog"),
    path("arr/<str:app>/missing-aired", CliArrMissingAiredView.as_view(), name="arr_missing_aired"),
    path("arr/<str:app>/import-candidates", CliArrImportCandidatesView.as_view(), name="arr_import_candidates"),
    path("arr/<str:app>/import/<str:index>", CliArrImportView.as_view(), name="arr_import"),
    path("arr/<str:app>/blocklist", CliArrBlocklistView.as_view(), name="arr_blocklist"),
    path("arr/<str:app>/recently-added", CliArrRecentlyAddedView.as_view(), name="arr_recently_added"),
    path("arr/starvation", CliArrImportStarvationView.as_view(), name="arr_starvation"),
    path("arr/queue-errors", CliArrQueueErrorsView.as_view(), name="arr_queue_errors"),
    path("queue/status", CliQueueStatusView.as_view(), name="queue_status"),
    path("queue/autofix", CliQueueAutofixView.as_view(), name="queue_autofix"),
    # NzbDAV
    path("nzbdav/queue", CliNzbdavQueueView.as_view(), name="nzbdav_queue"),
    path("nzbdav/history", CliNzbdavHistoryView.as_view(), name="nzbdav_history"),
    path("nzbdav/stats", CliNzbdavStatsView.as_view(), name="nzbdav_stats"),
    path("nzbdav/delete-failures", CliNzbdavDeleteFailuresView.as_view(), name="nzbdav_delete_failures"),
    path("nzbdav/dedup-check", CliNzbdavDedupCheckView.as_view(), name="nzbdav_dedup_check"),
    # Plex
    path("plex/libraries", CliPlexLibrariesView.as_view(), name="plex_libraries"),
    path("plex/sessions", CliPlexSessionsView.as_view(), name="plex_sessions"),
    path("plex/recently-added", CliPlexRecentlyAddedView.as_view(), name="plex_recently_added"),
    # WatchState
    path("watchstate/status", CliWatchstateStatusView.as_view(), name="watchstate_status"),
    path("watchstate/import", CliWatchstateImportView.as_view(), name="watchstate_import"),
    path("watchstate/history", CliWatchstateHistoryView.as_view(), name="watchstate_history"),
    # Cleanuparr
    path("cleanuparr/instances", CliCleanuparrInstancesView.as_view(), name="cleanuparr_instances"),
    path("cleanuparr/strikes", CliCleanuparrStrikesView.as_view(), name="cleanuparr_strikes"),
    # Log Levels
    path("log-levels", CliLogLevelsView.as_view(), name="log_levels"),
    # Seerr
    path("seerr/requests", CliSeerrRequestsView.as_view(), name="seerr_requests"),
    # Notifications
    path("notify/test", CliNotifyTestView.as_view(), name="notify_test"),
    # List Imports
    path("letterboxd/import", CliLetterboxdImportView.as_view(), name="letterboxd_import"),
    path("mdblist/import", CliMdblistImportView.as_view(), name="mdblist_import"),
    # Loop Remediation
    path("loop/candidates", CliLoopCandidatesView.as_view(), name="loop_candidates"),
    path("loop/unmonitor", CliLoopUnmonitorView.as_view(), name="loop_unmonitor"),
    path("loop/exclude", CliLoopExcludeView.as_view(), name="loop_exclude"),
]
