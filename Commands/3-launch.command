#!/bin/bash
cd "$(dirname "$0")/.." || exit 1

echo "🎵 Launching Timbre-Slider..."
make launch-interface

echo "Server started. Max/MSP frontend should open automatically."
echo "Press Ctrl+C to stop the server."

# Keep window open
wait
