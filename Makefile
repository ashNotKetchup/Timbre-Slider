# Makefile for Timbre-Slider workflows

.PHONY: setup install run-udp open-frontend launch-interface

# Create venv and install requirements
setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Launch interface: run UDP server and open frontend (UDP runs in background)
launch-interface:
	. .venv/bin/activate && (python3 udp_communication.py &)
	sleep 1
	open frontend/frontend.maxpat
	@echo "Frontend launched. UDP server running in background."




##### Individual commands for flexibility #####

# Install requirements in existing venv
install:
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Run the UDP server
run-udp:
	. .venv/bin/activate && python3 udp_communication.py
	@echo "UDP server running. Use Ctrl+C to stop."

# Open the Max/MSP frontend patch
open-frontend:
	open frontend/frontend.maxpat
	@echo "Frontend opened in Max/MSP. Make sure to run the UDP server separately."
