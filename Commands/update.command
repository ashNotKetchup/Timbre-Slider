#!/bin/bash
cd "$(dirname "$0")/.." || exit 1

echo "📦 Updating from GitHub..."
echo ""

# Fetch and reset to upstream (GitHub is source of truth)
git fetch origin main
git reset --hard origin/main

if [ $? -eq 0 ]; then
    echo "✅ Synced to GitHub"
else
    echo "❌ Failed to sync with GitHub."
    read -p "Press Enter to close..."
    exit 1
fi

# Update submodules
git submodule update --recursive

if [ $? -eq 0 ]; then
    echo "✅ Update complete!"
else
    echo "❌ Submodule update failed."
fi

read -p "Press Enter to close..."
