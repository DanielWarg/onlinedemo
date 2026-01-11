#!/usr/bin/env bash
set -euo pipefail

# Lokal E2E-smoke via Caddy (utan Tailscale).
# Syfte: bevisa att core-flödet funkar i CI: health -> skapa projekt -> skapa note -> export_snapshot (maskad).

BASE_URL="${1:-http://localhost:8443}"
API_BASE="${BASE_URL%/}/api"

AUTH_USER="${BASIC_AUTH_ADMIN_USER:-admin}"
AUTH_PASS="${BASIC_AUTH_ADMIN_PASS:-password}"
AUTH="${AUTH_USER}:${AUTH_PASS}"

echo "Smoke local:"
echo "  ${API_BASE}/health"

for i in $(seq 1 60); do
  if curl -fsS "${API_BASE}/health" >/dev/null 2>&1; then
    echo "OK: health"
    break
  fi
  sleep 1
done

# 1) Skapa projekt
PROJECT_JSON="$(curl -fsS -u "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{"name":"CI Smoke Project","description":"E2E smoke","tags":["ci","smoke"]}' \
  "${API_BASE}/projects")"

PROJECT_ID="$(printf "%s" "${PROJECT_JSON}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
echo "OK: project_id=${PROJECT_ID}"

# 2) Skapa anteckning (enkel metadata-safe content)
NOTE_BODY="Det här är ett smoke-test. Datum: 2026-01-06 kl 13:24."
curl -fsS -u "${AUTH}" \
  -H "Content-Type: application/json" \
  -d "$(NOTE_BODY="${NOTE_BODY}" python3 -c 'import json, os; print(json.dumps({"title":"Smoke note","body":os.environ["NOTE_BODY"]}))')" \
  "${API_BASE}/projects/${PROJECT_ID}/notes" >/dev/null
echo "OK: note created"

# 3) Snapshot-export (maskad vy)
SNAPSHOT_JSON="$(curl -fsS -u "${AUTH}" "${API_BASE}/projects/${PROJECT_ID}/export_snapshot")"
printf "%s" "${SNAPSHOT_JSON}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
assert "export_markdown" in data and isinstance(data["export_markdown"], str) and data["export_markdown"].strip()
assert "input_manifest" in data and isinstance(data["input_manifest"], list)
assert "counts" in data and isinstance(data["counts"], dict)
'
echo "OK: export_snapshot schema"

echo "OK"

