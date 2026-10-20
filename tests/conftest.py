"""Shared test isolation.

Every test used to set ``DXVK_MANAGER_HOME`` on its own; a module that forgot
wrote into the real user profile (settings.json, games.json, cover cache).
conftest is imported before any test module, so this is the one place that
guarantees isolation and an off-screen Qt platform.

``setdefault`` keeps an explicitly exported value intact, which is what the
golden test relies on to get a stable cache path.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

_ROOT = Path(tempfile.mkdtemp(prefix="dxvk-tests-"))
os.environ.setdefault("DXVK_MANAGER_HOME", str(_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

atexit.register(shutil.rmtree, _ROOT, ignore_errors=True)
