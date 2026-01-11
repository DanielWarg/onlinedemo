#!/bin/bash
# Start script för Fort Knox Local

set -e

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
export LLAMA_SERVER_URL=${LLAMA_SERVER_URL:-http://localhost:8080}
export FORTKNOX_PORT=${FORTKNOX_PORT:-8787}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export FORTKNOX_TESTMODE=${FORTKNOX_TESTMODE:-0}

echo "Starting Fort Knox Local..."
echo "  LLAMA_SERVER_URL: $LLAMA_SERVER_URL"
echo "  FORTKNOX_PORT: $FORTKNOX_PORT"
echo "  TESTMODE: $FORTKNOX_TESTMODE"
echo ""

python3 main.py
