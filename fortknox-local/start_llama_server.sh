#!/bin/bash
# Start script för llama.cpp server

set -e

MODEL_DIR="$HOME/.cache/fortknox/models"
PORT=${1:-8080}
THREADS=${2:-4}

# Find model (prioritera Ministral-3-8B, annars Mistral 7B, annars första GGUF)
MODEL=$(find "$MODEL_DIR" -name "*ministral*8b*.gguf" -type f | head -1)
if [ -z "$MODEL" ]; then
    MODEL=$(find "$MODEL_DIR" -name "*mistral*7b*.gguf" -type f | head -1)
fi
if [ -z "$MODEL" ]; then
    MODEL=$(find "$MODEL_DIR" -name "*.gguf" -type f | head -1)
fi

if [ -z "$MODEL" ]; then
    echo "❌ Ingen modell hittad i $MODEL_DIR"
    echo "Kör: ./download_model.sh för att ladda ner en modell"
    exit 1
fi

echo "Startar llama.cpp server..."
echo "  Model: $MODEL"
echo "  Port: $PORT"
echo "  Threads: $THREADS"
echo ""

# Find llama-server
LLAMA_SERVER=$(which llama-server 2>/dev/null || which llama.cpp 2>/dev/null || echo "")

if [ -z "$LLAMA_SERVER" ]; then
    # Try to find in common build locations
    if [ -f "$HOME/.local/llama.cpp/llama.cpp/server" ]; then
        LLAMA_SERVER="$HOME/.local/llama.cpp/llama.cpp/server"
    elif [ -f "$HOME/.local/llama.cpp/llama.cpp/llama-server" ]; then
        LLAMA_SERVER="$HOME/.local/llama.cpp/llama.cpp/llama-server"
    else
        echo "❌ llama-server inte hittad"
        echo "Kör: ./install_llama.sh"
        exit 1
    fi
fi

echo "Using: $LLAMA_SERVER"
echo ""

# Start server
"$LLAMA_SERVER" \
    -m "$MODEL" \
    --port "$PORT" \
    --ctx-size 4096 \
    --n-predict 2048 \
    --threads "$THREADS" \
    --host 0.0.0.0
