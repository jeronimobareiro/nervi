# SPDX-License-Identifier: GPL-3.0-or-later
"""``python -m nervi.gui [proyecto.nrv]``."""

import sys

from .app import main

sys.exit(main())
