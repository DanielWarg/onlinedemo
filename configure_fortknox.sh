#!/bin/bash
# Konfigurera Fort Knox Remote URL i docker-compose.yml

set -e

TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)

if [ -z "$TAILSCALE_IP" ]; then
    echo "❌ Kunde inte hämta Tailscale IP"
    echo "Kontrollera att Tailscale körs:"
    echo "  tailscale status"
    exit 1
fi

echo "Tailscale IP: $TAILSCALE_IP"
echo ""

# Update docker-compose.yml
python3 << PYEOF
import re

with open('docker-compose.yml', 'r') as f:
    content = f.read()

# Replace FORTKNOX_REMOTE_URL
old_pattern = r'FORTKNOX_REMOTE_URL: \$\{FORTKNOX_REMOTE_URL:-[^}]+\}'
new_value = f'FORTKNOX_REMOTE_URL: ${{FORTKNOX_REMOTE_URL:-http://{TAILSCALE_IP}:8787}}'

content = re.sub(old_pattern, new_value, content)

with open('docker-compose.yml', 'w') as f:
    f.write(content)

print(f"✅ Uppdaterade docker-compose.yml")
print(f"   FORTKNOX_REMOTE_URL=http://{TAILSCALE_IP}:8787")
PYEOF

echo ""
echo "Nästa steg:"
echo "  1. Restart API: docker-compose restart api"
echo "  2. Testa: curl http://localhost:8000/api/fortknox/compile ..."
