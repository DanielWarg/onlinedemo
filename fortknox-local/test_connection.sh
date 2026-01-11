#!/bin/bash
# Test script för att verifiera Fort Knox Local setup

echo "=========================================="
echo "Fort Knox Local - Connection Test"
echo "=========================================="
echo ""

# Test 1: Python dependencies
echo "1. Testar Python dependencies..."
cd "$(dirname "$0")"
source venv/bin/activate
python3 -c "import fastapi, uvicorn, pydantic, requests; print('   ✅ All dependencies OK')" || {
    echo "   ❌ Dependencies saknas"
    echo "   Kör: pip install -r requirements.txt"
    exit 1
}

# Test 2: llama.cpp server
echo ""
echo "2. Testar llama.cpp server..."
LLAMA_SERVER=$(which llama-server 2>/dev/null || which llama.cpp 2>/dev/null || echo "")
if [ -z "$LLAMA_SERVER" ]; then
    echo "   ⚠️  llama-server inte i PATH"
    echo "   Kör: ./install_llama.sh"
else
    echo "   ✅ llama-server hittad: $LLAMA_SERVER"
fi

# Test 3: Model
echo ""
echo "3. Testar modell..."
MODEL=$(find ~/.cache/fortknox/models -name "*.gguf" -type f 2>/dev/null | head -1)
if [ -z "$MODEL" ]; then
    echo "   ⚠️  Ingen modell hittad"
    echo "   Kör: ./download_model.sh"
else
    echo "   ✅ Modell hittad: $MODEL"
    ls -lh "$MODEL" | awk '{print "      Storlek: " $5}'
fi

# Test 4: Fort Knox Local service
echo ""
echo "4. Testar Fort Knox Local service..."
if curl -s http://localhost:8787/health > /dev/null 2>&1; then
    echo "   ✅ Service körs på port 8787"
    curl -s http://localhost:8787/health | python3 -m json.tool 2>/dev/null || echo "   Response: OK"
else
    echo "   ⚠️  Service körs inte"
    echo "   Starta med: ./start.sh"
fi

# Test 5: llama.cpp server connection
echo ""
echo "5. Testar llama.cpp server connection..."
if curl -s http://localhost:8080/health > /dev/null 2>&1 || curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "   ✅ llama.cpp server svarar på port 8080"
else
    echo "   ⚠️  llama.cpp server körs inte"
    echo "   Starta med: ./start_llama_server.sh"
fi

# Test 6: Tailscale
echo ""
echo "6. Testar Tailscale..."
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null)
if [ -n "$TAILSCALE_IP" ]; then
    echo "   ✅ Tailscale IP: $TAILSCALE_IP"
    echo "   Använd denna i docker-compose.yml: FORTKNOX_REMOTE_URL=http://$TAILSCALE_IP:8787"
else
    echo "   ⚠️  Tailscale inte installerat eller körs inte"
    echo "   Installera: https://tailscale.com/download"
fi

echo ""
echo "=========================================="
echo "Test komplett!"
echo "=========================================="
