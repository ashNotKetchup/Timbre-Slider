"""
Entry point for running backend as a module.
Allows: python -m backend (runs UDP server)
        python -m backend export (runs export)
"""
import sys

if len(sys.argv) > 1 and sys.argv[1] == "export":
    # python -m backend export [args...]
    from .export import main
    sys.exit(main(sys.argv[2:]))
else:
    # python -m backend (default: run UDP server)
    from .udp_communication import start_server
    start_server()

