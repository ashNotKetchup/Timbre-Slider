#!/bin/bash
cd "$(dirname "$0")/.." || exit 1

echo "📦 Updating from repository..."
git pull origin executable
git submodule update --recursive

if [ $? -eq 0 ]; then
    echo "✅ Update complete!"
else
    echo "❌ Update failed. Check your git status."
fi

read -p "Press Enter to close..."
