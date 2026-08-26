"""Radarr/Sonarr/Prowlarr application configuration constants.

Extracted from core/arr_client.py — these are pure data declarations
with no logic, used by every arr-related module in the control panel.
"""
import os

# Internal bearcave hostnames - not HOST_IP, since this container reaches
# every *arr app over the docker network directly. Bare os.environ[...]
# subscript matches the FastAPI-era app's own behavior: a missing key is a
# deployment misconfiguration that should fail loudly at import time, not
# silently produce a broken ARR_APPS entry.
ARR_APPS = {
    "radarr": {
        "url": "http://radarr:7878",
        "api": "v3",
        "key": os.environ["RADARR_API_KEY"],
        "search_command": "MissingMoviesSearch",
        "label": "Radarr",
        "import_events": ("downloadFolderImported",),
    },
    "sonarr": {
        "url": "http://sonarr:8989",
        "api": "v3",
        "key": os.environ["SONARR_API_KEY"],
        "search_command": "MissingEpisodeSearch",
        "label": "Sonarr",
        "import_events": ("downloadFolderImported",),
    },
}

# Radarr and Sonarr both have a real download queue (NzbDAV wired to each as
# the sole download client) - Unstick/manual-import work identically on both.
QUEUE_ARR_APPS = ("radarr", "sonarr")

RADARR_APPS = ("radarr",)

SONARR_APPS = ("sonarr",)

PROWLARR_API_KEY = os.environ.get("PROWLARR_API_KEY")
PROWLARR_CFG = {"url": "http://prowlarr:9696", "api": "v1", "key": PROWLARR_API_KEY, "label": "Prowlarr"}

HOST_CONFIG_DIR = "/host-config"
