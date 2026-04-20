#!/bin/bash

# Timbre-Slider Bootstrap Installer
# Download this file, make it executable, and run it.
# It will clone/update the repo and run the setup.

set -e

REPO_URL="https://github.com/ashNotKetchup/Timbre-Slider.git"
REPO_DIR="Timbre-Slider"

echo "🎵 Timbre-Slider Bootstrap Installer"
echo "====================================="
echo ""

# Check if repo already exists
if [ -d "$REPO_DIR" ]; then
    echo "📁 Found existing Timbre-Slider folder, updating..."
    cd "$REPO_DIR"
    git fetch origin executable
    git reset --hard origin/executable
    git submodule update --recursive
else
    echo "📥 Cloning Timbre-Slider repository..."
    git clone --recursive -b executable "$REPO_URL"
    cd "$REPO_DIR"
fi

echo ""
echo "✅ Repository ready. Starting setup..."
echo ""

# Run the install command
bash Commands/1-install.command
