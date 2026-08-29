#!/usr/bin/env bash
# ============================================================================
# The Bear Cave — Backup Restore Test
# ============================================================================
# Verifies that backup.sh produces valid, restorable archives.
# Creates a backup, restores into a scratch directory, and validates integrity.
#
# Usage:
#   ./tests/integration/test_backup_restore.sh
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCRATCH_DIR="$(mktemp -d /tmp/bearcave-restore-test.XXXXXX)"
PASS=0
FAIL=0

cleanup() { rm -rf "$SCRATCH_DIR"; }
trap cleanup EXIT

pass() { echo -e "  \033[32m✓\033[0m $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  \033[31m✗\033[0m $1"; FAIL=$((FAIL + 1)); }

echo "============================================"
echo " Bear Cave Backup Restore Test"
echo "============================================"
echo ""

# Step 1: Run backup
echo "Step 1: Running backup.sh..."
if cd "$REPO_DIR" && bash scripts/backup.sh --configs-only 2>&1 | tail -5; then
    pass "backup.sh completed successfully"
else
    fail "backup.sh failed"
    echo ""
    echo "Results: $PASS passed, $FAIL failed"
    exit 1
fi

# Step 2: Find the latest backup directory (backup.sh writes a directory tree,
# not a tarball)
LATEST_BACKUP=$(find "$REPO_DIR/backups" -maxdepth 1 -type d -name 'bearcave_backup_*' -printf '%T@\t%p\n' 2>/dev/null | sort -rn | head -1 | cut -f2-)
if [ -z "$LATEST_BACKUP" ]; then
    fail "No backup directory found in backups/"
    echo ""
    echo "Results: $PASS passed, $FAIL failed"
    exit 1
fi
pass "Found backup: $(basename "$LATEST_BACKUP") ($(du -sh "$LATEST_BACKUP" | cut -f1))"

# Step 3: Verify backup structure — a configs/ tree must exist with content
echo ""
echo "Step 2: Verifying backup structure..."
CONFIG_COUNT=$(find "$LATEST_BACKUP/configs" -type f 2>/dev/null | wc -l)
if [ "$CONFIG_COUNT" -gt 0 ]; then
    pass "Backup contains configs/ with $CONFIG_COUNT files"
else
    fail "Backup missing configs/ content"
fi

# Step 4: Restore into scratch directory (simulate a restore: copy the tree)
echo ""
echo "Step 3: Restoring into scratch directory..."
if cp -r "$LATEST_BACKUP/." "$SCRATCH_DIR/" 2>/dev/null; then
    pass "Backup restored successfully"
else
    fail "Restore failed"
fi

# Step 5: Verify expected files exist
echo ""
echo "Step 4: Checking extracted contents..."
FOUND=0
for pattern in "*.env" "*.sh" "*.yml" "*.yaml" "*.json"; do
    COUNT=$(find "$SCRATCH_DIR" -name "$pattern" -type f 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        ((FOUND += COUNT))
    fi
done
if [ "$FOUND" -gt 0 ]; then
    pass "Found $FOUND config files in extracted archive"
else
    fail "No config files found in extracted archive"
fi

# Step 6: Check for sensitive files that shouldn't be in plaintext
echo ""
echo "Step 5: Checking for sensitive file exposure..."
SENSITIVE_COUNT=$(find "$SCRATCH_DIR" -name "*.env" -exec grep -l "changeme" {} \; 2>/dev/null | wc -l)
if [ "$SENSITIVE_COUNT" -eq 0 ]; then
    pass "No changeme placeholders found in backup"
else
    fail "$SENSITIVE_COUNT files still contain 'changeme' defaults"
fi

# Summary
echo ""
echo "============================================"
echo " Results: $PASS passed, $FAIL failed"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
