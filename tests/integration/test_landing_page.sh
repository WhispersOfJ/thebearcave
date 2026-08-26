#!/usr/bin/env bash
# tests/integration/test_landing_page.sh
# Integration test for the Bear Cave landing page.
# Verifies: page serves, JS rendering functions, Mermaid, TLS badge, health dots, registry.
# Requires: curl, jq, python3.
set -euo pipefail

HOST="${BEARCAVE_HOST:-https://bearcave.192.168.4.20.nip.io}"
PASS=0
FAIL=0
WARN=0

pass() { echo "  ✅ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  ⚠️  $1"; WARN=$((WARN + 1)); }

echo "=========================================="
echo "  Landing Page Integration Test"
echo "  Target: ${HOST}"
echo "=========================================="
echo ""

# Fetch page once
PAGE=$(curl -sk "${HOST}/" 2>/dev/null || echo "")

# ── 1. Page serves ──────────────────────────────────────────────
echo "1. Page serves"
HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "${HOST}/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  pass "Page returns HTTP 200"
else
  fail "Page returns HTTP ${HTTP_CODE} (expected 200)"
fi

# ── 2. JS rendering structure ──────────────────────────────────
echo ""
echo "2. JavaScript rendering structure"
for fn in renderCategories renderPipeline renderGraph checkAll toggleDetail loadRegistry; do
  if echo "$PAGE" | grep -q "function ${fn}"; then
    pass "${fn}() present"
  else
    fail "${fn}() missing"
  fi
done

# ── 3. Service registry (inline + fetchable) ───────────────────
echo ""
echo "3. Service registry"
INLINE_COUNT=$(echo "$PAGE" | grep -o '"services":{' | wc -l)
if [ "$INLINE_COUNT" -ge 1 ]; then
  pass "Inline registry present (${INLINE_COUNT} occurrence)"
else
  fail "Inline registry missing"
fi

REGISTRY=$(curl -sk "${HOST}/service-registry.json" 2>/dev/null || echo "{}")
REG_COUNT=$(echo "$REGISTRY" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('services',{})))" 2>/dev/null || echo "0")
if [ "$REG_COUNT" -ge 22 ]; then
  pass "service-registry.json serves ${REG_COUNT} services"
else
  fail "service-registry.json serves ${REG_COUNT} services (expected ≥22)"
fi

# ── 4. Mermaid ecosystem graph ─────────────────────────────────
echo ""
echo "4. Mermaid ecosystem graph"
MERMAID_DIV=$(echo "$PAGE" | grep -c 'id="ecosystem-graph"' || true)
MERMAID_SCRIPT=$(echo "$PAGE" | grep -c 'mermaid.min.js' || true)
if [ "$MERMAID_DIV" -ge 1 ] && [ "$MERMAID_SCRIPT" -ge 1 ]; then
  pass "Mermaid graph div and CDN script present"
else
  fail "Mermaid graph missing (div: ${MERMAID_DIV}, script: ${MERMAID_SCRIPT})"
fi

# ── 5. Health status dots ──────────────────────────────────────
echo ""
echo "5. Health status dots"
HAS_CHECKALL=$(echo "$PAGE" | grep -c 'async function checkAll' || true)
HAS_STATUS=$(echo "$PAGE" | grep -c 'card-status' || true)
if [ "$HAS_CHECKALL" -ge 1 ] && [ "$HAS_STATUS" -ge 1 ]; then
  pass "Health check function and status elements present"
else
  fail "Health dots missing (checkAll: ${HAS_CHECKALL}, status: ${HAS_STATUS})"
fi

# ── 6. TLS badge ───────────────────────────────────────────────
echo ""
echo "6. TLS certificate badge"
TLS_RESP=$(curl -sk "${HOST}/api/v2/host/tls" 2>/dev/null || echo "{}")
TLS_TRUSTED=$(echo "$TLS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('trusted', False))" 2>/dev/null || echo "False")
if [ "$TLS_TRUSTED" = "True" ]; then
  pass "TLS badge shows CA-trusted"
else
  warn "TLS badge: trusted=${TLS_TRUSTED}"
fi

# ── 7. Health endpoint ─────────────────────────────────────────
echo ""
echo "7. Health endpoint (via same-origin proxy)"
HEALTH=$(curl -sk "${HOST}/api/v2/host/health" 2>/dev/null || echo "{}")
TOTAL=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('services',{})))" 2>/dev/null || echo "0")
UP=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); svc=d.get('services',{}); print(sum(1 for v in svc.values() if v.get('status')=='up'))" 2>/dev/null || echo "0")
if [ "$TOTAL" -ge 22 ]; then
  pass "Health endpoint reports ${UP}/${TOTAL} services up"
else
  fail "Health endpoint reports ${UP}/${TOTAL} (expected ≥22 total)"
fi

# ── 8. CVE baseline card ───────────────────────────────────────
echo ""
echo "8. CVE baseline card"
CVE_CARD=$(echo "$PAGE" | grep -c 'CVE Baseline' || true)
if [ "$CVE_CARD" -ge 1 ]; then
  pass "CVE baseline card present"
else
  warn "CVE baseline card not found in page HTML"
fi

# ── 9. Backlinks ───────────────────────────────────────────────
echo ""
echo "9. Navigation links"
BEARCAVE_LINKS=$(echo "$PAGE" | grep -o 'thebearcave' | wc -l)
# Check visible HTML (not inline JS registry data or archive references) for media-stack references
MEDIA_STACK_HTML=$(echo "$PAGE" | grep -v 'INLINE_REGISTRY' | grep -v 'service-registry' | grep -v 'archive/' | grep -o 'media-stack' | wc -l || true)
if [ "$BEARCAVE_LINKS" -ge 1 ] && [ "$MEDIA_STACK_HTML" -eq 0 ]; then
  pass "All visible links point to thebearcave (${BEARCAVE_LINKS} references)"
else
  fail "Link audit: thebearcave=${BEARCAVE_LINKS}, media-stack in HTML=${MEDIA_STACK_HTML}"
fi

# ── 10. Certificate setup section ──────────────────────────────
echo ""
echo "10. Certificate setup section"
CERT_SECTION=$(echo "$PAGE" | grep -ci 'certificate\|rootCA\|mkcert' || true)
if [ "$CERT_SECTION" -ge 1 ]; then
  pass "Certificate setup section present"
else
  warn "Certificate setup section not found"
fi

# ── Summary ─────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo ""
TOTAL_TESTS=$((PASS + FAIL + WARN))
echo "Passed: ${PASS}/${TOTAL_TESTS}"
echo "Failed: ${FAIL}/${TOTAL_TESTS}"
echo "Warned: ${WARN}/${TOTAL_TESTS}"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "❌ ${FAIL} test(s) FAILED"
  exit 1
else
  echo "✅ All critical tests passed"
  exit 0
fi
