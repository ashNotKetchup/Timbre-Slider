# Makefile for Timbre-Slider workflows

.PHONY: setup install init-submodule check-env download-model run-udp open-frontend launch-interface preprocess

# ---------- Full setup (first time) ----------

# Clone submodule, create venv, install deps, download model, check .env
setup: init-submodule
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@[ -f .env ] || (cp .env.example .env && echo "\n⚠️  Created .env from template — edit it to add your HF_TOKEN\n   Get one at https://huggingface.co/settings/tokens")
	@echo "\n✅ Setup complete. Next steps:"
	@echo "   1. Edit .env with your HuggingFace token"
	@echo "   2. Run 'make download-model' to cache the Stable Audio model"
	@echo "   3. Run 'make launch-interface' to start"

# Initialise the streamable-stable-audio-open submodule
init-submodule:
	git submodule update --init --recursive

# Check that .env has a real token
check-env:
	@[ -f .env ] || (echo "❌ .env file not found. Run: cp .env.example .env" && exit 1)
	@grep -q '^HF_TOKEN=hf_' .env || echo "⚠️  HF_TOKEN in .env looks like a placeholder — update it with your real token"

# Download Stable Audio Open 1.0 model weights (cached in ~/.cache/huggingface)
download-model: check-env
	. .venv/bin/activate && python3 download_model.py

# ---------- Run ----------

# Launch interface: run HTTP server and open Max/MSP frontend
launch-interface: check-env
	. .venv/bin/activate && (python3 udp_communication.py &)
	sleep 1
	open frontend/frontend.maxpat
	@echo "Frontend launched. Server running in background."

# Preprocess audio: compute features for a folder of sounds
# Usage: make preprocess FOLDER=sounds/Foley
preprocess: check-env
	. .venv/bin/activate && python3 mass_preprocess.py


##### Individual commands for flexibility #####

# Install requirements in existing venv
install:
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Run the HTTP server
run-udp: check-env
	. .venv/bin/activate && python3 udp_communication.py
	@echo "Server running. Use Ctrl+C to stop."

# Open the Max/MSP frontend patch
open-frontend:
	open frontend/frontend.maxpat
	@echo "Frontend opened in Max/MSP. Make sure to run the server separately."
