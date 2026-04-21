#!/bin/bash
cd "$(dirname "$0")/.." || exit 1

echo "🚀 Installing Timbre-Slider dependencies..."
make setup

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Get a HuggingFace token: https://huggingface.io/settings/tokens"
    echo "  2. Run 2-download-model.command (it will prompt for your token)"
    echo "  3. Run 3-launch.command to start the app"
else
    echo "❌ Installation failed. Check the output above."
fi

read -p "Press Enter to close..."
