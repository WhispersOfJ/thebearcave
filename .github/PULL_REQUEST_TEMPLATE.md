## Summary

<!-- What does this PR do? One sentence. -->

## Changes

-
-

## Service or area affected

- [ ] Plex
- [ ] NzbDAV / rclone mount
- [ ] Radarr / Sonarr / Prowlarr
- [ ] Seerr / Unpackerr
- [ ] CI/CD
- [ ] Documentation
- [ ] Scripts / Fish functions

## Testing

- [ ] `docker compose config --quiet`
- [ ] `bash -n scripts/*.sh tests/*/*.sh`
- [ ] `python3 scripts/check_compose_mounts.py`
- [ ] `./tests/health/run-all.sh`
- [ ] Manual critical-path verification (describe below)

## Checklist

- [ ] No secrets or credentials committed
- [ ] `.env.template` updated if Compose variables changed
- [ ] Documentation updated where needed
- [ ] NzbDAV queue checked before any recreate
- [ ] FUSE mount checked before any Plex scan

## Related issues

<!-- Fixes #123, Closes #456 -->
