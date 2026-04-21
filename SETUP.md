# 🚀 Timbre-Slider Setup Guide

## One-Time Setup (First Time Only)

Follow these steps in order. Each one is a clickable file in the `Commands/` folder.

### Step 1️⃣ — Install Dependencies
**File:** `Commands/1-install.command`

Double-click this file. It will:
- Set up a Python environment
- Install all required packages
- Create a `.env` configuration file

⏱️ Takes 2-3 minutes.

---

### Step 2️⃣ — Download AI Model
**File:** `Commands/2-download-model.command`

Double-click this file. It will:
- Prompt you for your HuggingFace API token (free account needed)
- Download the Stable Audio Open 1.0 model (~1.2 GB)
- Cache it for future use

📝 **Need a token?** Go to https://huggingface.io/settings/tokens and create one (free).

⏱️ Takes 5-10 minutes depending on internet.

---

### Step 3️⃣ — Launch the App
**File:** `Commands/3-launch.command`

Double-click this file. It will:
- Start the audio processing server
- Open your Max/MSP frontend automatically

The app is now ready to use! 🎵

---

## Later: Update Code
**File:** `Commands/update.command`

If you pull new code from GitHub, double-click this to sync everything.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **"command not found: python3"** | Install Python 3.10+ from python.org |
| **"No module named streamable_audio"** | Run Step 1 again (dependencies not installed) |
| **Download fails** | Check your HuggingFace token is correct and has read access |
| **Max/MSP doesn't open** | Install Max/MSP, or open `frontend/frontend.maxpat` manually |

---

**Ready to start?** Open the `Commands/` folder and double-click `1-install.command`
