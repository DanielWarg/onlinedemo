#!/bin/bash
# Sätt Fort Knox Remote URL med din Tailscale IP

set -e

echo "=========================================="
echo "FORT KNOX - SÄTT TAILSCALE IP"
echo "=========================================="
echo ""

# Hämta Tailscale IP
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)

if [ -z "$TAILSCALE_IP" ]; then
    echo "⚠️  Kunde inte hämta Tailscale IP automatiskt"
    echo ""
    echo "Kör detta i din terminal för att hämta din IP:"
    echo "  tailscale ip -4"
    echo ""
    read -p "Ange din Tailscale IP: " TAILSCALE_IP
    
    if [ -z "$TAILSCALE_IP" ]; then
        echo "❌ Ingen IP angiven"
        exit 1
    fi
fi

echo "✅ Tailscale IP: $TAILSCALE_IP"
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
echo ""
echo "Testa connection:"
echo "  docker-compose exec api curl -s http://$TAILSCALE_IP:8787/health"
echo ""
