"""In-memory login rate limiter with AuditLog integration.

Tracks failed login attempts per IP address. After MAX_ATTEMPTS within
the WINDOW_SECONDS window, the IP is locked out for LOCKOUT_SECONDS.

Design choices:
- In-memory (not DB-backed) because this panel runs on a single host
  with one worker process. A restart resets counters, which is acceptable
  for a LAN-hosted dashboard.
- Keyed by REMOTE_ADDR, not X-Forwarded-For, because the panel sits
  behind Traefik on the same host — REMOTE_ADDR is always the real
  client IP.
- AuditLog entries are written for every failed attempt AND every lockout
  event, so the activity log shows brute-force patterns.
"""
import logging
import time

logger = logging.getLogger(__name__)

# --- Configuration ---
MAX_ATTEMPTS = 5          # failures before lockout
WINDOW_SECONDS = 300      # 5-minute sliding window
LOCKOUT_SECONDS = 900     # 15-minute lockout after threshold

# --- State ---
# {ip: [(timestamp, ...)]}
_attempts: dict[str, list[float]] = {}
# {ip: lockout_expiry_timestamp}
_lockouts: dict[str, float] = {}


def _now() -> float:
    return time.monotonic()


def _clean_old(ip: str) -> None:
    """Drop attempts older than the sliding window."""
    cutoff = _now() - WINDOW_SECONDS
    if ip in _attempts:
        _attempts[ip] = [t for t in _attempts[ip] if t > cutoff]
        if not _attempts[ip]:
            del _attempts[ip]


def is_locked_out(ip: str) -> bool:
    """Check if the IP is currently locked out."""
    expiry = _lockouts.get(ip)
    if expiry is None:
        return False
    if _now() >= expiry:
        del _lockouts[ip]
        return False
    return True


def record_failure(ip: str, username: str) -> None:
    """Record a failed login attempt. Locks out the IP if threshold exceeded."""
    _clean_old(ip)
    _attempts.setdefault(ip, []).append(_now())

    # Log to AuditLog
    from core.models import AuditLog
    AuditLog.objects.create(
        action="login_failed",
        detail=f"username={username} from {ip} ({len(_attempts.get(ip, []))} attempts in window)",
    )

    if len(_attempts.get(ip, [])) >= MAX_ATTEMPTS:
        _lockouts[ip] = _now() + LOCKOUT_SECONDS
        logger.warning("Login lockout: %s exceeded %d attempts in %ds, locked for %ds",
                       ip, MAX_ATTEMPTS, WINDOW_SECONDS, LOCKOUT_SECONDS)
        AuditLog.objects.create(
            action="login_lockout",
            detail=f"IP {ip} locked out after {MAX_ATTEMPTS} failed attempts",
        )


def remaining_lockout_seconds(ip: str) -> float:
    """Seconds remaining on the lockout, or 0 if not locked out."""
    expiry = _lockouts.get(ip)
    if expiry is None:
        return 0.0
    remaining = expiry - _now()
    if remaining <= 0:
        del _lockouts[ip]
        return 0.0
    return remaining
