"""
Entry point for PyInstaller builds.
Uses absolute imports to avoid issues with package structure during bundling.
"""
import sys
import os

# Ensure backend is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from backend.udp_communication import start_server
    start_server()
