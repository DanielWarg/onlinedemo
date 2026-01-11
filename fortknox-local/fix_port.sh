#!/bin/bash
# Fix script för port-konflikter

PORT=8787

echo "Kontrollerar port $PORT..."

# Find process using port
PID=$(lsof -ti:$PORT 2>/dev/null)

if [ -n "$PID" ]; then
    echo "⚠️  Port $PORT används av process $PID"
    ps -p $PID -o command= 2>/dev/null | head -1
    echo ""
    read -p "Vill du stoppa processen? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill $PID 2>/dev/null
        sleep 1
        if lsof -ti:$PORT > /dev/null 2>&1; then
            echo "⚠️  Process stoppades inte, försöker force kill..."
            kill -9 $PID 2>/dev/null
            sleep 1
        fi
        if ! lsof -ti:$PORT > /dev/null 2>&1; then
            echo "✅ Port $PORT är nu ledig"
        else
            echo "❌ Kunde inte frigöra port $PORT"
            exit 1
        fi
    else
        echo "Avbruten. Använd annan port:"
        echo "  FORTKNOX_PORT=8788 ./start.sh"
        exit 1
    fi
else
    echo "✅ Port $PORT är ledig"
fi
