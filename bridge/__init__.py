"""Bridge package: re-exports root ``bridge.py`` helpers (the ``bridge/`` dir shadows ``bridge.py`` on import)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_pkg_dir = Path(__file__).resolve().parent
_root_file = _pkg_dir.parent / "bridge.py"
_spec = importlib.util.spec_from_file_location("_cashcow_bridge_flat", _root_file)
if _spec is None or _spec.loader is None:
    raise ImportError("Cannot load root bridge.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

poll_task = _mod.poll_task
run_bridge = _mod.run_bridge
submit_video = _mod.submit_video

__all__ = ["poll_task", "run_bridge", "submit_video"]
