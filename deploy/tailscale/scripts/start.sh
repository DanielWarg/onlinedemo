#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy/tailscale"

if [[ ! -f "${DEPLOY_DIR}/.env" ]]; then
  echo "Saknar ${DEPLOY_DIR}/.env"
  echo "Gör så här:"
  echo "  cp ${DEPLOY_DIR}/env.example ${DEPLOY_DIR}/.env"
  exit 1
fi

if ! command -v docker-compose >/dev/null 2>&1; then
  echo "docker-compose saknas. Installera Docker Desktop (eller docker-compose) först."
  exit 1
fi

echo "Bygger frontend (VITE_API_BASE=/api)..."
(
  cd "${ROOT_DIR}/apps/web"
  VITE_API_BASE=/api npm ci --silent
  VITE_API_BASE=/api npm run build --silent
)

echo "Startar prod-demo (caddy+api+postgres) via docker-compose..."
(
  cd "${ROOT_DIR}"
  docker-compose -f "${DEPLOY_DIR}/docker-compose.prod.yml" --env-file "${DEPLOY_DIR}/.env" up -d --build
)

echo ""
echo "Lokalt:"
echo "  http://localhost:8443/"
echo "  http://localhost:8443/api/health"
echo ""
echo "Nästa steg (kör manuellt, ingen kod):"
echo "  tailscale funnel 443 localhost:8443"
echo "  # öppna: https://\${DOMAIN_ROOT}/  och  https://\${DOMAIN_ROOT}/api/health"

