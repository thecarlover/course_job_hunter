#!/usr/bin/env bash
# Course & Job Hunter — Instant Live Admin Server
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "================================================================="
echo " 🚀 Course & Job Hunter — Live Admin Launcher"
echo "================================================================="

# Start background uvicorn server if not already running
if ! lsof -i :8000 > /dev/null 2>&1; then
    echo "Starting local admin server on port 8000..."
    "$DIR/.venv/bin/python" admin.py &
    SERVER_PID=$!
    trap "kill $SERVER_PID 2>/dev/null || true" EXIT
    sleep 2
else
    echo "Admin server already running on port 8000."
fi

echo ""
echo "🌐 Connecting to public HTTPS tunnel..."
echo "Press Ctrl+C anytime to stop."
echo "================================================================="
ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run
