#!/usr/bin/env python3
"""
Wrapper script to run udp_communication from the backend package.
"""
import sys
from backend.run_server import start_server

if __name__ == "__main__":
    start_server()
