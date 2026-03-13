# Makefile for MALT workflows

.PHONY: setup install init-submodule check-env download-model run-udp open-frontend launch-interface preprocess restart-server kill-server

LOG_DEPTH ?= normal
KILL_SERVER_SILENT ?= 0

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
	@token=$$(awk -F= '/^[[:space:]]*HF_TOKEN[[:space:]]*=/{v=$$2; gsub(/^[[:space:]]+|[[:space:]]+$$/,"",v); gsub(/^"|"$$/,"",v); print v; exit}' .env); \
	if [ -z "$$token" ] || [ "$$token" = "hf_your_token_here" ] || ! echo "$$token" | grep -Eq '^hf_[A-Za-z0-9]+'; then \
		echo "⚠️  HF_TOKEN in .env looks like a placeholder — update it with your real token"; \
	fi

# Download Stable Audio Open 1.0 model weights (cached in ~/.cache/huggingface)
download-model: check-env
	. .venv/bin/activate && python3 download_model.py

# ---------- Run ----------

# Kill any process currently listening on port 5000
kill-server:
	-@pids=$$(lsof -ti tcp:5000 2>/dev/null); \
	if [ -n "$$pids" ]; then \
		if [ "$(KILL_SERVER_SILENT)" != "1" ]; then \
			echo "Stopping existing server on :5000 ($$pids)"; \
		fi; \
		kill $$pids; \
		sleep 1; \
	fi

# Launch interface: run HTTP server and open Max/MSP frontend
launch-interface: KILL_SERVER_SILENT=1
launch-interface: kill-server
	@echo "(Re)Launching MALT server on :5000"
	@. .venv/bin/activate && (LOG_DEPTH=minimal PYTHONWARNINGS=ignore python3 udp_communication.py &)
	@sleep 1
	@open frontend/frontend.maxpat

# Restart the HTTP server in minimal log mode
restart-server: KILL_SERVER_SILENT=1
restart-server: kill-server
	@echo "(Re)Launching MALT server on :5000"
	@. .venv/bin/activate && (LOG_DEPTH=minimal PYTHONWARNINGS=ignore python3 udp_communication.py &)

# Preprocess audio: compute features for a folder of sounds
# Usage: make preprocess FOLDER=sounds/Foley
preprocess: check-env
	. .venv/bin/activate && python3 mass_preprocess.py


##### Individual commands for flexibility #####

# Install requirements in existing venv
install:
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Run the HTTP server
run-udp: check-env kill-server
	. .venv/bin/activate && python3 udp_communication.py
	@echo "Server running. Use Ctrl+C to stop."

# Open the Max/MSP frontend patch
open-frontend:
	open frontend/frontend.maxpat
	@echo "Frontend opened in Max/MSP. Make sure to run the server separately."
