# SPDX-License-Identifier: GPL-3.0-or-later
"""Punto de entrada del ejecutable de escritorio (PyInstaller)."""

import sys

from nervi.gui import main

if __name__ == "__main__":
    sys.exit(main())
