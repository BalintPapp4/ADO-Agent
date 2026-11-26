"""Module entrypoint for `python -m ado_agent` and PyInstaller."""

from ado_agent.app import main

if __name__ == "__main__":
    raise SystemExit(main())
