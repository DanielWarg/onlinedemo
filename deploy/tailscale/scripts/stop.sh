#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy/tailscale"

echo "Stoppar docker-compose (api+postgres)..."
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose -f "${DEPLOY_DIR}/docker-compose.prod.yml" down
fi

echo "Klart."

