"""PyInstaller belépési pont az ADÓ Agent futtatható csomagokhoz."""

from ado_agent.app import main

if __name__ == "__main__":
    raise SystemExit(main())
