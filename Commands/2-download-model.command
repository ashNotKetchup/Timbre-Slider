#!/bin/bash
cd "$(dirname "$0")/.." || exit 1

echo "📥 Downloading Stable Audio Open model (~1.2 GB)..."
echo ""

# Check if .env exists and has a valid token
if [ -f .env ]; then
    token=$(awk -F= '/^[[:space:]]*HF_TOKEN[[:space:]]*=/{v=$2; gsub(/^[[:space:]]+|[[:space:]]+$/,"",v); gsub(/^"|"$/,"",v); print v; exit}' .env)
fi

# If no valid token, prompt user
if [ -z "$token" ] || [ "$token" = "hf_your_token_here" ]; then
    echo "⚠️  HuggingFace token not found or invalid."
    echo "Get a free token at: https://huggingface.io/settings/tokens"
    echo ""
    read -p "Paste your HF_TOKEN here: " token
    
    if [ -z "$token" ]; then
        echo "❌ No token provided. Exiting."
        read -p "Press Enter to close..."
        exit 1
    fi
    
    # Create or update .env
    if [ ! -f .env ]; then
        cp .env.example .env 2>/dev/null || echo "HF_TOKEN=$token" > .env
    else
        # Update existing .env
        if grep -q "HF_TOKEN" .env; then
            sed -i.bak "s/^HF_TOKEN=.*/HF_TOKEN=$token/" .env
            rm -f .env.bak
        else
            echo "HF_TOKEN=$token" >> .env
        fi
    fi
    
    echo "✅ Token saved to .env"
fi

echo ""
make download-model

if [ $? -eq 0 ]; then
    echo "✅ Model downloaded!"
    echo "Next: Run 3-launch.command to start the app"
else
    echo "❌ Download failed. Check your token is valid."
fi

read -p "Press Enter to close..."
