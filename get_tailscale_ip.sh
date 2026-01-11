#!/bin/bash
# Hämta Tailscale IP på Mac

# Try different paths
TAILSCALE_CMD=""

# Check if tailscale is in PATH
if command -v tailscale &> /dev/null; then
    TAILSCALE_CMD="tailscale"
# Check Mac App Store installation
elif [ -f "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]; then
    TAILSCALE_CMD="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
# Check Homebrew installation
elif [ -f "/opt/homebrew/bin/tailscale" ]; then
    TAILSCALE_CMD="/opt/homebrew/bin/tailscale"
elif [ -f "/usr/local/bin/tailscale" ]; then
    TAILSCALE_CMD="/usr/local/bin/tailscale"
fi

if [ -z "$TAILSCALE_CMD" ]; then
    echo "❌ Kunde inte hitta Tailscale"
    echo ""
    echo "Kontrollera att Tailscale är installerat och körs:"
    echo "  1. Öppna Tailscale appen från Applications"
    echo "  2. Logga in om du inte redan är inloggad"
    echo "  3. Se till att status är 'Connected'"
    exit 1
fi

echo "Hämtar Tailscale IP..."
IP=$($TAILSCALE_CMD ip -4 2>/dev/null | head -1)

if [ -z "$IP" ]; then
    echo "⚠️  Kunde inte hämta IP"
    echo ""
    echo "Kontrollera att Tailscale är ansluten:"
    echo "  - Öppna Tailscale appen"
    echo "  - Se till att status är 'Connected'"
    echo ""
    echo "ELLER kör manuellt:"
    echo "  $TAILSCALE_CMD ip -4"
    exit 1
fi

echo "✅ Tailscale IP: $IP"
echo ""
echo "Kör detta för att uppdatera docker-compose.yml:"
echo "  ./set_fortknox_ip.sh"
echo ""
echo "ELLER ange IP:n manuellt när scriptet frågar:"
echo "  $IP"
