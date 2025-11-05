#!/bin/bash
# Check the progress of the index build

cd "$(dirname "$0")"

PID_FILE="build_index.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No build process found (no PID file)"
    exit 1
fi

PID=$(cat "$PID_FILE")

# Check if process is still running
if ps -p "$PID" > /dev/null 2>&1; then
    echo "✓ Build process is RUNNING (PID: $PID)"
    echo ""

    # Find the latest log file
    LATEST_LOG=$(ls -t build_index_*.log 2>/dev/null | head -1)

    if [ -n "$LATEST_LOG" ]; then
        echo "Latest log: $LATEST_LOG"
        echo ""
        echo "Last 30 lines:"
        echo "----------------------------------------"
        tail -30 "$LATEST_LOG"
        echo "----------------------------------------"
        echo ""
        echo "To follow live: tail -f $LATEST_LOG"
    fi
else
    echo "✗ Build process is NOT running (was PID: $PID)"
    echo ""

    # Find the latest log file
    LATEST_LOG=$(ls -t build_index_*.log 2>/dev/null | head -1)

    if [ -n "$LATEST_LOG" ]; then
        echo "Latest log: $LATEST_LOG"
        echo ""
        echo "Last 50 lines:"
        echo "----------------------------------------"
        tail -50 "$LATEST_LOG"
        echo "----------------------------------------"
        echo ""

        # Check if it completed successfully
        if grep -q "SUCCESS! Index built and saved" "$LATEST_LOG"; then
            echo "✓ Build completed SUCCESSFULLY!"
        else
            echo "✗ Build may have failed or been interrupted"
        fi
    fi

    rm -f "$PID_FILE"
fi
