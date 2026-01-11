#!/bin/bash
# Komplett setup-script för Fort Knox Local

set -e

echo "=========================================="
echo "Fort Knox Local - Komplett Setup"
echo "=========================================="
echo ""

cd "$(dirname "$0")"

# 1. Installera dependencies
echo "1. Installerar Python dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo "   ✅ Dependencies installerade"
echo ""

# 2. Installera llama.cpp
echo "2. Installerar llama.cpp..."
./install_llama.sh
echo ""

# 3. Ladda ner modell (om inte redan nedladdad)
echo "3. Kontrollerar modell..."
MODEL=$(find ~/.cache/fortknox/models -name "*.gguf" -type f 2>/dev/null | head -1)
if [ -z "$MODEL" ]; then
    echo "   ⚠️  Ingen modell hittad"
    echo "   Kör: cd ~/.cache/fortknox/models && ./download_mistral.sh"
    echo "   Eller ladda ner manuellt från Hugging Face"
else
    echo "   ✅ Modell hittad: $MODEL"
fi
echo ""

# 4. Testa Fort Knox Local (test mode)
echo "4. Testar Fort Knox Local (test mode)..."
FORTKNOX_TESTMODE=1 timeout 3 ./start.sh > /dev/null 2>&1 &
sleep 2
if curl -s http://localhost:8787/health > /dev/null 2>&1; then
    echo "   ✅ Fort Knox Local fungerar"
    pkill -f "python3 main.py" 2>/dev/null || true
else
    echo "   ⚠️  Fort Knox Local startar inte korrekt"
fi
echo ""

echo "=========================================="
echo "Setup komplett!"
echo "=========================================="
echo ""
echo "NÄSTA STEG:"
echo ""
echo "1. Ladda ner modell (om inte redan gjort):"
echo "   cd ~/.cache/fortknox/models"
echo "   ./download_mistral.sh"
echo ""
echo "2. Starta llama.cpp server (Terminal 1):"
echo "   cd fortknox-local"
echo "   ./start_llama_server.sh"
echo ""
echo "3. Starta Fort Knox Local (Terminal 2):"
echo "   cd fortknox-local"
echo "   ./start.sh"
echo ""
echo "4. Testa:"
echo "   ./test_connection.sh"
echo ""
