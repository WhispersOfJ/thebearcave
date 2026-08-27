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

# Step 2: Find the latest backup archive
LATEST_BACKUP=$(ls -t "$REPO_DIR"/backups/bearcave_backup_*.tar.gz 2>/dev/null | head -1)
if [ -z "$LATEST_BACKUP" ]; then
    fail "No backup archive found in backups/"
    echo ""
    echo "Results: $PASS passed, $FAIL failed"
    exit 1
fi
pass "Found backup archive: $(basename "$LATEST_BACKUP") ($(du -h "$LATEST_BACKUP" | cut -f1))"

# Step 3: Verify archive integrity
echo ""
echo "Step 2: Verifying archive integrity..."
if tar -tzf "$LATEST_BACKUP" > /dev/null 2>&1; then
    pass "Archive is valid tar.gz"
else
    fail "Archive is corrupted (tar -tzf failed)"
fi

# Step 4: Extract to scratch directory
echo ""
echo "Step 3: Extracting to scratch directory..."
if tar -xzf "$LATEST_BACKUP" -C "$SCRATCH_DIR" 2>/dev/null; then
    pass "Archive extracted successfully"
else
    fail "Extraction failed"
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
