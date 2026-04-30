"""
Entry point for running backend as a module.
Allows: python -m backend.udp_communication
"""
from .udp_communication import start_server

if __name__ == "__main__":
    start_server()
