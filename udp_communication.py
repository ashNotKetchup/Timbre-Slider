#!/usr/bin/env python3
"""
Wrapper script to run udp_communication from the backend package.
"""
import sys
from backend.udp_communication import start_server

if __name__ == "__main__":
    start_server()
