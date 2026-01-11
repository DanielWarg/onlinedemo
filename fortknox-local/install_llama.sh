#!/bin/bash
# Install script för llama.cpp

set -e

echo "Installerar llama.cpp..."

# Check if already installed via brew
if brew list llama.cpp &>/dev/null; then
    echo "✅ llama.cpp redan installerat via Homebrew"
    which llama-server || which llama.cpp
    exit 0
fi

# Try to install via brew
if command -v brew &> /dev/null; then
    echo "Installerar via Homebrew..."
    brew install llama.cpp
    echo "✅ llama.cpp installerat via Homebrew"
    which llama-server || which llama.cpp
else
    echo "⚠️  Homebrew inte installerat. Bygger från källa..."
    
    # Build from source
    BUILD_DIR="$HOME/.local/llama.cpp"
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
    
    if [ ! -d "llama.cpp" ]; then
        git clone https://github.com/ggerganov/llama.cpp.git
    fi
    
    cd llama.cpp
    git pull
    make
    
    echo "✅ llama.cpp byggt från källa"
    echo "Kör: export PATH=\$PATH:$BUILD_DIR/llama.cpp"
    echo "Eller lägg till i ~/.zshrc:"
    echo "  export PATH=\$PATH:$BUILD_DIR/llama.cpp"
fi
