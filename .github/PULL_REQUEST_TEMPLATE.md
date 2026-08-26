## Summary

<!-- What does this PR do? One sentence summary. -->

## Changes

<!-- Bullet list of what changed. -->

-
-

## Service(s) affected

<!-- Which services are impacted by this change? Check all that apply. -->

- [ ] Plex
- [ ] Metacache
- [ ] InfiniDysk (nzbdav)
- [ ] Radarr / Sonarr / Prowlarr
- [ ] Seerr
- [ ] Control Panel
- [ ] Traefik
- [ ] WatchState
- [ ] Monitoring (Grafana / Prometheus / Loki)
- [ ] CI/CD
- [ ] Documentation
- [ ] Other: ___

## Testing

<!-- How did you verify this works? -->

- [ ] `docker compose config --quiet` passes
- [ ] `bash -n` syntax check on all shell scripts
- [ ] Compose file brought up successfully
- [ ] Health checks pass (`./tests/health/run-all.sh`)
- [ ] Manual testing performed (describe below)

## Checklist

- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] No secrets or credentials committed
- [ ] `.env.template` updated if new env vars were added
- [ ] Documentation updated (if applicable)
- [ ] Does not break existing services

## Related issues

<!-- Link any related issues: Fixes #123, Closes #456 -->
