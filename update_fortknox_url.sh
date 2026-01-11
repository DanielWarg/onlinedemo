#!/bin/bash
# Uppdatera FORTKNOX_REMOTE_URL med faktisk Tailscale IP

set -e

echo "Hämtar Tailscale IP..."

# Try different paths for tailscale
TAILSCALE_IP=""
for TAILSCALE_CMD in "/usr/local/bin/tailscale" "/opt/homebrew/bin/tailscale" "tailscale"; do
    if command -v "$TAILSCALE_CMD" &> /dev/null; then
        TAILSCALE_IP=$($TAILSCALE_CMD ip -4 2>/dev/null | head -1)
        if [ -n "$TAILSCALE_IP" ]; then
            break
        fi
    fi
done

if [ -z "$TAILSCALE_IP" ]; then
    echo "⚠️  Kunde inte hämta Tailscale IP automatiskt"
    echo ""
    echo "Ange din Tailscale IP manuellt:"
    read -p "Tailscale IP: " TAILSCALE_IP
    if [ -z "$TAILSCALE_IP" ]; then
        echo "❌ Ingen IP angiven"
        exit 1
    fi
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
echo "Restart API för att ladda nya inställningar:"
echo "  docker-compose restart api"
