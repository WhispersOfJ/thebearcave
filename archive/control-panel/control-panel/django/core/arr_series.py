"""Sonarr-specific series operations — lookup, add, quality profiles.

Extracted from core/arr_client.py. Imports ARR_APPS from core/arr_config
for app configuration.
"""
import httpx

from core.api_base import ServiceError
from core.arr_config import ARR_APPS


def sonarr_root_folder_and_profile(cfg, root_folder: str | None, quality_profile: str | None) -> tuple[str, int]:
    try:
        folders = httpx.get(f"{cfg['url']}/api/{cfg['api']}/rootfolder", headers={"X-Api-Key": cfg["key"]}, timeout=15).json()
        profiles = httpx.get(f"{cfg['url']}/api/{cfg['api']}/qualityprofile", headers={"X-Api-Key": cfg["key"]}, timeout=15).json()
    except httpx.HTTPError as e:
        raise ServiceError(f"Couldn't read Sonarr's root folders/quality profiles: {e}")

    root_folder_path = (
        root_folder
        or next((f["path"] for f in folders if f["path"] == "/data/shows"), None)
        or (folders[0]["path"] if folders else None)
    )
    if not root_folder_path:
        raise ServiceError("Sonarr has no root folders configured.", status=500)

    wanted_profile = quality_profile or "Any"
    quality_profile_id = next((p["id"] for p in profiles if p["name"] == wanted_profile), None)
    if quality_profile_id is None:
        quality_profile_id = profiles[0]["id"] if profiles else None
    if quality_profile_id is None:
        raise ServiceError("Sonarr has no quality profiles configured.", status=500)

    return root_folder_path, quality_profile_id


def sonarr_add_series(cfg, tvdb_id: int, monitored: bool, search: bool, root_folder_path: str, quality_profile_id: int,
                       existing_tvdb_ids: set[int], dry_run: bool = False) -> dict:
    if tvdb_id in existing_tvdb_ids:
        return {"status": "already", "title": None, "tvdbId": tvdb_id}
    try:
        lookup = httpx.get(f"{cfg['url']}/api/{cfg['api']}/series/lookup", params={"term": f"tvdb:{tvdb_id}"},
                            headers={"X-Api-Key": cfg["key"]}, timeout=20)
        lookup.raise_for_status()
        results = lookup.json()
    except httpx.HTTPError as e:
        return {"status": "failed", "reason": f"tvdb {tvdb_id}: lookup failed ({e})"}
    if not results:
        return {"status": "failed", "reason": f"tvdb {tvdb_id}: no Sonarr match"}
    series = results[0]

    series["qualityProfileId"] = quality_profile_id
    series["rootFolderPath"] = root_folder_path
    series["monitored"] = monitored
    series["seasonFolder"] = True
    series["addOptions"] = {
        "monitor": "all" if monitored else "none",
        "searchForMissingEpisodes": search,
        "searchForCutoffUnmetEpisodes": False,
    }

    if dry_run:
        return {"status": "added", "title": series["title"]}

    try:
        add = httpx.post(f"{cfg['url']}/api/{cfg['api']}/series", json=series, headers={"X-Api-Key": cfg["key"]}, timeout=30)
        add.raise_for_status()
    except httpx.HTTPStatusError as e:
        return {"status": "failed", "reason": f'"{series["title"]}": {e.response.text.strip() or e}'}
    except httpx.HTTPError as e:
        return {"status": "failed", "reason": f'"{series["title"]}": {e}'}
    added = add.json()
    return {"status": "added", "title": added.get("title", series["title"])}
