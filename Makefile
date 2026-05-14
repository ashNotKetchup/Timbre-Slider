# Makefile for MALT workflows

.PHONY: setup install init-submodule check-env download-model run-udp open-frontend launch-interface preprocess restart-server kill-server

LOG_DEPTH ?= normal
KILL_SERVER_SILENT ?= 0

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
	@. .venv/bin/activate && (LOG_DEPTH=minimal PYTHONWARNINGS=ignore python3 -m backend.run_server &)
	@sleep 1
	@open frontend/frontend.maxpat

# Restart the HTTP server in minimal log mode
restart-server: KILL_SERVER_SILENT=1
restart-server: kill-server
	@echo "(Re)Launching MALT server on :5000"
	@. .venv/bin/activate && (LOG_DEPTH=minimal PYTHONWARNINGS=ignore python3 -m backend.run_server &)

# Preprocess audio: compute features for a folder of sounds
# Usage: make preprocess FOLDER=sounds/Foley
preprocess: check-env
	. .venv/bin/activate && python3 backend/mass_preprocess.py


##### Individual commands for flexibility #####

# Install requirements in existing venv
install:
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Run the HTTP server
run-udp: check-env kill-server
	. .venv/bin/activate && python3 -m backend.run_server
	@echo "Server running. Use Ctrl+C to stop."

# Open the Max/MSP frontend patch
open-frontend:
	open frontend/frontend.maxpat
	@echo "Frontend opened in Max/MSP. Make sure to run the server separately."


APP_NAME=run_server

compile:
	
	pyinstaller backend/run_server.py \
		--name $(APP_NAME) \
		--onefile \
		--collect-submodules backend \
		--collect-all torch \
		--collect-all numpy

	# Copy extra folders into dist
	cp -r frontend dist/
	cp -r data dist/
	cp how-to.md dist/

clean:
	rm -rf build __pycache__ .mypy_cache *.spec

build:
	$(MAKE) purge
	$(MAKE) compile
	$(MAKE) clean

build_debug: clean compile

purge:
	rm -rf build dist __pycache__ .mypy_cache *.spec


test:
	$(MAKE) build
	/Users/ash/Documents/GitHub/Timbre-Slider/dist/run_server
