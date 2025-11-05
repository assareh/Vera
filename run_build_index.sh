#!/bin/bash
# Run the web index builder with nohup so it survives SSH disconnects

set -e

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

# Log file with timestamp
LOG_FILE="build_index_$(date +%Y%m%d_%H%M%S).log"
PID_FILE="build_index.pid"

echo "Starting index build in background..."
echo "Log file: $LOG_FILE"
echo "PID file: $PID_FILE"
echo ""

# Run with nohup
nohup python3 build_web_index.py > "$LOG_FILE" 2>&1 &

# Save PID
echo $! > "$PID_FILE"

echo "Process started with PID: $(cat $PID_FILE)"
echo ""
echo "To monitor progress:"
echo "  tail -f $LOG_FILE"
echo ""
echo "To check if still running:"
echo "  ps -p \$(cat $PID_FILE) || echo 'Process finished'"
echo ""
echo "To stop the process:"
echo "  kill \$(cat $PID_FILE)"
echo ""

# Show initial output
sleep 2
echo "Initial output:"
echo "----------------------------------------"
tail -20 "$LOG_FILE"
