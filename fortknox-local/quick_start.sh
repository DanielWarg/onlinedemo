#!/bin/bash
# Quick start script för Fort Knox Local

set -e

echo "=========================================="
echo "Fort Knox Local - Quick Start"
echo "=========================================="
echo ""

# Check model
MODEL_DIR="$HOME/.cache/fortknox/models"
MODEL=$(find "$MODEL_DIR" -name "*.gguf" -type f 2>/dev/null | head -1)

if [ -z "$MODEL" ]; then
    echo "❌ Ingen modell hittad i $MODEL_DIR"
    echo "Kör: ./download_model.sh"
    exit 1
fi

echo "✅ Modell hittad: $(basename "$MODEL")"
ls -lh "$MODEL" | awk '{print "   Storlek: " $5}'
echo ""

# Check llama-server
if ! command -v llama-server &> /dev/null; then
    echo "❌ llama-server inte hittad"
    echo "Kör: ./install_llama.sh"
    exit 1
fi

echo "✅ llama-server hittad: $(which llama-server)"
echo ""

# Check if services are already running
if curl -s http://localhost:8787/health > /dev/null 2>&1; then
    echo "⚠️  Fort Knox Local körs redan på port 8787"
    read -p "Vill du stoppa den och starta om? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "python3 main.py" 2>/dev/null || true
        sleep 1
    else
        echo "Avbruten."
        exit 0
    fi
fi

if curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "⚠️  llama.cpp server körs redan på port 8080"
    read -p "Vill du stoppa den och starta om? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "llama-server" 2>/dev/null || true
        sleep 1
    else
        echo "Avbruten."
        exit 0
    fi
fi

echo "=========================================="
echo "Startar tjänsterna..."
echo "=========================================="
echo ""
echo "VIKTIGT: Du behöver 2 terminalfönster!"
echo ""
echo "Terminal 1 - llama.cpp server:"
echo "  cd fortknox-local"
echo "  ./start_llama_server.sh"
echo ""
echo "Terminal 2 - Fort Knox Local:"
echo "  cd fortknox-local"
echo "  ./start.sh"
echo ""
echo "När båda körs, testa med:"
echo "  curl http://localhost:8787/health"
echo ""
echo "=========================================="
