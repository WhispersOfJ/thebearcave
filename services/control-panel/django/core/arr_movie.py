"""Radarr-specific movie operations — lookup, add, blocklist, quality profiles, tags.

Extracted from core/arr_client.py. Imports ARR_APPS and RADARR_APPS from
core/arr_config for app configuration.
"""
import httpx

from core.api_base import ServiceError
from core.arr_config import ARR_APPS, RADARR_APPS


def get_movie_or_episode(app_name: str, cfg: dict, target_id: int) -> dict | None:
    endpoint = "movie" if app_name in RADARR_APPS else "episode"
    try:
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/{endpoint}/{target_id}", headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return None


def item_is_monitored(app_name: str, q: dict, cfg: dict, id_field: str) -> bool:
    # unmonitored movies/episodes should never be re-searched by the loop -
    # the queue response's embedded movie/episode object is NOT reliable
    # (confirmed live: can sit null for 8+ seconds straight), so always
    # confirm via a direct lookup by id instead of trusting it blindly.
    embedded = q.get("movie") if app_name in RADARR_APPS else q.get("episode")
    if embedded is not None:
        return bool(embedded.get("monitored", True))
    target_id = q.get(id_field)
    if target_id is None:
        return True
    endpoint = "movie" if app_name in RADARR_APPS else "episode"
    try:
        r = httpx.get(f"{cfg['url']}/api/{cfg['api']}/{endpoint}/{target_id}", headers={"X-Api-Key": cfg["key"]}, timeout=20)
        r.raise_for_status()
        return bool(r.json().get("monitored", True))
    except httpx.HTTPError:
        return True


def blocklist_and_research(app_name: str, items: list[dict]) -> tuple[list[str], list[str]]:
    cfg = ARR_APPS[app_name]
    fixed, errors = [], []
    search_ids: list[int] = []
    id_field = "movieId" if app_name in RADARR_APPS else "episodeId"
    for q in items:
        title = q.get("title") or str(q["id"])
        monitored = item_is_monitored(app_name, q, cfg, id_field)
        params = {"removeFromClient": "true", "blocklist": "true", "skipRedownload": str(not monitored).lower()}
        delete_ok = False
        for attempt in range(2):
            try:
                r = httpx.delete(f"{cfg['url']}/api/{cfg['api']}/queue/{q['id']}", params=params,
                                  headers={"X-Api-Key": cfg["key"]}, timeout=20)
                if r.status_code not in (200, 404):
                    r.raise_for_status()
                delete_ok = True
                break
            except httpx.TimeoutException:
                if attempt == 0:
                    continue
                errors.append(f"{title}: timed out")
            except httpx.HTTPError as e:
                errors.append(f"{title}: {e}")
                break
        if not delete_ok:
            continue
        fixed.append(title)
        target_id = q.get(id_field)
        if monitored and target_id is not None:
            search_ids.append(target_id)
    if search_ids:
        command_name = "MoviesSearch" if app_name in RADARR_APPS else "EpisodeSearch"
        command_field = "movieIds" if app_name in RADARR_APPS else "episodeIds"
        try:
            r = httpx.post(f"{cfg['url']}/api/{cfg['api']}/command", json={"name": command_name, command_field: search_ids},
                            headers={"X-Api-Key": cfg["key"]}, timeout=20)
            r.raise_for_status()
        except httpx.HTTPError as e:
            errors.append(f"search trigger failed for {len(search_ids)} item(s): {e}")
    return fixed, errors


def radarr_root_folder_and_profile(cfg, root_folder: str | None, quality_profile: str | None) -> tuple[str, int]:
    try:
        folders = httpx.get(f"{cfg['url']}/api/{cfg['api']}/rootfolder", headers={"X-Api-Key": cfg["key"]}, timeout=15).json()
        profiles = httpx.get(f"{cfg['url']}/api/{cfg['api']}/qualityprofile", headers={"X-Api-Key": cfg["key"]}, timeout=15).json()
    except httpx.HTTPError as e:
        raise ServiceError(f"Couldn't read Radarr's root folders/quality profiles: {e}")

    root_folder_path = (
        root_folder
        or next((f["path"] for f in folders if f["path"] == "/data/movies"), None)
        or (folders[0]["path"] if folders else None)
    )
    if not root_folder_path:
        raise ServiceError("Radarr has no root folders configured.", status=500)

    wanted_profile = quality_profile or "Unlimited"
    quality_profile_id = next((p["id"] for p in profiles if p["name"] == wanted_profile), None)
    if quality_profile_id is None:
        quality_profile_id = profiles[0]["id"] if profiles else None
    if quality_profile_id is None:
        raise ServiceError("Radarr has no quality profiles configured.", status=500)

    return root_folder_path, quality_profile_id


def radarr_quality_profile_id_by_name(cfg: dict, name: str) -> int | None:
    try:
        profiles = httpx.get(f"{cfg['url']}/api/{cfg['api']}/qualityprofile", headers={"X-Api-Key": cfg["key"]}, timeout=15).json()
    except httpx.HTTPError:
        return None
    return next((p["id"] for p in profiles if p["name"] == name), None)


def radarr_ensure_tags(cfg: dict, tag_names: list[str]) -> list[int]:
    """Returns the Radarr tag ids for tag_names, creating any that don't
    exist yet. Radarr's v3 tag API requires creating a tag via POST /tag
    before it can be referenced by id on a movie - there's no
    create-on-attach shortcut."""
    if not tag_names:
        return []
    try:
        existing = httpx.get(f"{cfg['url']}/api/{cfg['api']}/tag", headers={"X-Api-Key": cfg["key"]}, timeout=15).json()
    except httpx.HTTPError as e:
        raise ServiceError(f"Couldn't read Radarr's tags: {e}")
    by_label = {t["label"]: t["id"] for t in existing}

    ids = []
    for name in tag_names:
        if name in by_label:
            ids.append(by_label[name])
            continue
        try:
            created = httpx.post(f"{cfg['url']}/api/{cfg['api']}/tag", json={"label": name},
                                  headers={"X-Api-Key": cfg["key"]}, timeout=15)
            created.raise_for_status()
        except httpx.HTTPError as e:
            raise ServiceError(f"Couldn't create Radarr tag '{name}': {e}")
        new_id = created.json()["id"]
        by_label[name] = new_id
        ids.append(new_id)
    return ids


def radarr_add_movie(cfg, tmdb_id: int, monitored: bool, search: bool, root_folder_path: str, quality_profile_id: int,
                      existing_tmdb_ids: set[int], dry_run: bool = False, tag_ids: list[int] | None = None) -> dict:
    if tmdb_id in existing_tmdb_ids:
        return {"status": "already", "title": None, "tmdbId": tmdb_id}
    try:
        lookup = httpx.get(f"{cfg['url']}/api/{cfg['api']}/movie/lookup/tmdb", params={"tmdbId": tmdb_id},
                            headers={"X-Api-Key": cfg["key"]}, timeout=20)
        lookup.raise_for_status()
        movie = lookup.json()
    except httpx.HTTPError as e:
        return {"status": "failed", "reason": f"tmdb {tmdb_id}: lookup failed ({e})"}
    if not movie or not movie.get("title"):
        return {"status": "failed", "reason": f"tmdb {tmdb_id}: no Radarr match"}

    movie["qualityProfileId"] = quality_profile_id
    movie["rootFolderPath"] = root_folder_path
    movie["monitored"] = monitored
    movie["addOptions"] = {"searchForMovie": search}
    if tag_ids:
        movie["tags"] = tag_ids

    if dry_run:
        return {"status": "added", "title": movie["title"]}

    try:
        add = httpx.post(f"{cfg['url']}/api/{cfg['api']}/movie", json=movie, headers={"X-Api-Key": cfg["key"]}, timeout=30)
        add.raise_for_status()
    except httpx.HTTPStatusError as e:
        return {"status": "failed", "reason": f'"{movie["title"]}": {e.response.text.strip() or e}'}
    except httpx.HTTPError as e:
        return {"status": "failed", "reason": f'"{movie["title"]}": {e}'}
    return {"status": "added", "title": add.json().get("title", movie["title"])}
