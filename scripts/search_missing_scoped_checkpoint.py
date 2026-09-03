"""Atomic, validated checkpoints for scoped Sonarr searches."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile

CHECKPOINT_VERSION = 1
_GROUP_STATUSES = {"pending", "running", "completed", "failed"}
_VERIFICATION_STATUSES = {
    "pending", "not_requested", "ok", "unavailable", "aborted", "failed",
}


class CheckpointError(ValueError):
    """The checkpoint is absent, corrupt, incomplete, or incompatible."""


@dataclass
class CheckpointStore:
    """Read and atomically replace one checkpoint file."""

    path: Path

    def exists(self):
        return self.path.exists()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CheckpointError(f"checkpoint not found: {self.path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"checkpoint is unreadable: {self.path}") from exc
        self._validate(data)
        return data

    def write(self, data):
        self._validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent, text=True
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            try:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                # File replacement is still atomic where directory fsync is unavailable.
                pass
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict) or data.get("version") != CHECKPOINT_VERSION:
            raise CheckpointError("checkpoint has an unsupported version")

        config = data.get("config")
        required_config = {
            "scope", "url", "batchSize", "gap", "quietWindow", "checkpoint",
            "verify", "timeout",
        }
        if not isinstance(config, dict) or set(config) != required_config:
            raise CheckpointError("checkpoint config is incomplete")
        if not isinstance(config.get("url"), str) or not config["url"].strip():
            raise CheckpointError("checkpoint URL is invalid")
        scope = config.get("scope")
        if (not isinstance(scope, dict)
                or set(scope) != {"mode", "seriesIds"}
                or scope.get("mode") not in {"all", "series"}):
            raise CheckpointError("checkpoint scope is invalid")
        if scope["mode"] == "series":
            if (not isinstance(scope.get("seriesIds"), list)
                    or not scope["seriesIds"]
                    or any(not _positive_int(value) for value in scope["seriesIds"])):
                raise CheckpointError("checkpoint series scope is invalid")
        elif scope.get("seriesIds") is not None:
            raise CheckpointError("checkpoint all scope must not contain series IDs")
        allowed_series_ids = (
            set(scope["seriesIds"]) if scope["mode"] == "series" else None
        )
        if (not _positive_int(config["batchSize"])
                or not _nonnegative_int(config["gap"])
                or not _positive_int(config["quietWindow"])
                or type(config["checkpoint"]) is not bool
                or type(config["verify"]) is not bool
                or not _positive_int(config["timeout"])):
            raise CheckpointError("checkpoint execution config is invalid")

        batches = data.get("batches")
        if not isinstance(batches, list) or not batches:
            raise CheckpointError("checkpoint is missing planned batches")
        numbers = []
        group_keys = set()
        episode_ids = set()
        for batch in batches:
            if (not isinstance(batch, dict)
                    or set(batch) != {"number", "groups"}
                    or not _positive_int(batch.get("number"))
                    or not isinstance(batch.get("groups"), list)
                    or not batch["groups"]):
                raise CheckpointError("checkpoint contains an incomplete batch")
            numbers.append(batch["number"])
            for group in batch["groups"]:
                CheckpointStore._validate_group(group)
                identity = group["identity"]
                group_key = (identity["seriesId"], identity["seasonNumber"])
                if (allowed_series_ids is not None
                        and identity["seriesId"] not in allowed_series_ids):
                    raise CheckpointError(
                        "checkpoint group falls outside its series scope"
                    )
                if group_key in group_keys:
                    raise CheckpointError("checkpoint repeats a season group")
                group_keys.add(group_key)
                for episode_id in identity["episodeIds"]:
                    if episode_id in episode_ids:
                        raise CheckpointError("checkpoint repeats an episode identity")
                    episode_ids.add(episode_id)
        if numbers != list(range(1, len(numbers) + 1)):
            raise CheckpointError("checkpoint batch numbering is invalid")

    @staticmethod
    def is_complete(data):
        """Return whether every planned group reached a terminal safe state."""
        CheckpointStore._validate(data)
        return all(
            group["status"] == "completed"
            and group["verification"]["status"] in {
                "ok", "not_requested", "unavailable",
            }
            for batch in data["batches"]
            for group in batch["groups"]
        )

    @staticmethod
    def _validate_group(group):
        required = {"identity", "status", "command", "snapshot", "verification"}
        if not isinstance(group, dict) or set(group) != required:
            raise CheckpointError("checkpoint contains an incomplete group")

        identity = group["identity"]
        if (not isinstance(identity, dict)
                or set(identity) != {"seriesId", "seasonNumber", "episodeIds"}
                or not _positive_int(identity.get("seriesId"))
                or type(identity.get("seasonNumber")) is not int
                or identity["seasonNumber"] < 0
                or not isinstance(identity.get("episodeIds"), list)
                or not identity["episodeIds"]
                or any(not _positive_int(value) for value in identity["episodeIds"])):
            raise CheckpointError("checkpoint group identity is invalid")

        status = group["status"]
        if status not in _GROUP_STATUSES:
            raise CheckpointError("checkpoint group status is invalid")

        command = group["command"]
        if (not isinstance(command, dict)
                or set(command) != {"id", "status", "result"}
                or (command["id"] is not None and not _positive_int(command["id"]))
                or (command["status"] is not None
                    and not isinstance(command["status"], str))
                or (command["result"] is not None
                    and not isinstance(command["result"], str))):
            raise CheckpointError("checkpoint command state is invalid")

        snapshot = group["snapshot"]
        if snapshot is not None:
            if not isinstance(snapshot, dict) or set(snapshot) != {"watermark", "beforeIds"}:
                raise CheckpointError("checkpoint snapshot is invalid")
            watermark = snapshot["watermark"]
            if watermark is not None and (
                    not isinstance(watermark, list)
                    or len(watermark) != 2
                    or not isinstance(watermark[0], str)
                    or not _nonnegative_int(watermark[1])):
                raise CheckpointError("checkpoint watermark is invalid")
            if (not isinstance(snapshot["beforeIds"], list)
                    or any(not isinstance(value, str)
                           for value in snapshot["beforeIds"])):
                raise CheckpointError("checkpoint queue snapshot is invalid")

        verification = group["verification"]
        if (not isinstance(verification, dict)
                or set(verification) != {
                    "status", "historyAvailable", "historyCount", "queueCount",
                }
                or verification["status"] not in _VERIFICATION_STATUSES
                or (verification["historyAvailable"] is not None
                    and type(verification["historyAvailable"]) is not bool)
                or not _nonnegative_int(verification["historyCount"])
                or not _nonnegative_int(verification["queueCount"])):
            raise CheckpointError("checkpoint verification state is invalid")

        if status == "pending" and (
                command["id"] is not None
                or command["status"] is not None
                or command["result"] is not None
                or snapshot is not None
                or verification["status"] != "pending"):
            raise CheckpointError("pending checkpoint group has execution state")
        if status == "running":
            if snapshot is None:
                raise CheckpointError("running checkpoint group is incomplete")
            if command["id"] is None and (
                    command["status"] is not None
                    or command["result"] is not None
                    or verification["status"] != "pending"):
                raise CheckpointError("ambiguous running checkpoint is invalid")
        if status == "completed" and (
                command["id"] is None
                or snapshot is None
                or verification["status"] not in {"ok", "not_requested", "unavailable"}):
            raise CheckpointError("completed checkpoint group is incomplete")
        if status == "failed" and (
                command["id"] is None
                or snapshot is None
                or verification["status"] not in {"failed", "aborted"}):
            raise CheckpointError("failed checkpoint group is incomplete")


def _positive_int(value):
    return type(value) is int and value > 0


def _nonnegative_int(value):
    return type(value) is int and value >= 0
