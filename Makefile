# Makefile for MALT workflows

.PHONY: setup install init-submodule check-env download-model run-udp open-frontend launch-interface preprocess restart-server kill-server dist_max dist_standalone

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

	@OS=$$(uname -s | tr '[:upper:]' '[:lower:]'); \
	DIST=dist_max_$$OS; \
	echo "── Building $$DIST …"; \
	rm -rf $$DIST && mkdir -p $$DIST; \
	cp dist/$(APP_NAME) $$DIST/; \
	cp -r frontend $$DIST/ && rm -rf $$DIST/frontend/builds; \
	mkdir -p $$DIST/data/models && cp -r data/models/StableAudio $$DIST/data/models/; \
	cp -r data/eg_sounds $$DIST/data/; \
	cp how-to.md $$DIST/; \
	echo "── $$DIST done."

	@OS=$$(uname -s | tr '[:upper:]' '[:lower:]'); \
	DIST=dist_standalone_$$OS; \
	echo "── Building $$DIST …"; \
	LATEST=$$(ls -td frontend/builds/*.app 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then echo "Error: no .app found in frontend/builds/"; exit 1; fi; \
	rm -rf $$DIST && mkdir -p $$DIST; \
	cp dist/$(APP_NAME) $$DIST/; \
	cp -r "$$LATEST" $$DIST/; \
	mkdir -p $$DIST/data/models && cp -r data/models/StableAudio $$DIST/data/models/; \
	cp -r data/eg_sounds $$DIST/data/; \
	cp how-to.md $$DIST/; \
	echo "── $$DIST done."

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
