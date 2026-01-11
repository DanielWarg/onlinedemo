#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy/tailscale"

if [[ ! -f "${DEPLOY_DIR}/.env" ]]; then
  echo "Saknar ${DEPLOY_DIR}/.env"
  exit 1
fi

# shellcheck disable=SC1090
source "${DEPLOY_DIR}/.env"

if [[ -z "${DOMAIN_ROOT:-}" ]]; then
  echo "DOMAIN_ROOT saknas i .env"
  exit 1
fi

echo "Smoke (via HTTPS Funnel):"
echo "  https://${DOMAIN_ROOT}/"
echo "  https://${DOMAIN_ROOT}/api/health"

curl -fsS "https://${DOMAIN_ROOT}/" >/dev/null
curl -fsS "https://${DOMAIN_ROOT}/api/health" | grep -q "ok"

echo "OK"

