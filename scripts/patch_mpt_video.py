#!/usr/bin/env python3
"""Patch MoneyPrinterTurbo video.py for None transition mode.

When video_transition_mode is None (no transition configured), the code
calls .value on None, crashing the clip assembly. This patch adds a guard.

Usage: python patch_mpt_video.py /path/to/video.py
"""
from __future__ import annotations

import sys
from pathlib import Path


def patch(video_path: Path) -> None:
    """Apply transition None guard to video.py."""
    text = video_path.read_text(encoding="utf-8")

    old = "if video_transition_mode.value == VideoTransitionMode.none.value:"
    new = "if video_transition_mode is None or video_transition_mode.value == VideoTransitionMode.none.value:"

    if new in text:
        print(f"  Already patched: {video_path}")
        return

    if old not in text:
        print(f"  WARNING: Could not find transition check in {video_path}")
        return

    text = text.replace(old, new)
    video_path.write_text(text, encoding="utf-8")
    print(f"  Patched: {video_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/video.py")
        sys.exit(1)
    patch(Path(sys.argv[1]))
