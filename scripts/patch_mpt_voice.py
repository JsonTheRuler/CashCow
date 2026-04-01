#!/usr/bin/env python3
"""Patch MoneyPrinterTurbo voice.py for edge_tts v7 compatibility.

edge_tts 7.x breaking changes:
  - SubMaker.subs / SubMaker.offset removed (replaced by SubMaker.cues)
  - SubMaker.create_sub() removed (replaced by SubMaker.feed())
  - mktimestamp() removed from edge_tts.submaker
  - Stream emits SentenceBoundary instead of WordBoundary

This script patches voice.py to handle both v6 and v7 seamlessly.

Usage: python patch_mpt_voice.py /path/to/voice.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

COMPAT_BLOCK = '''import edge_tts
import requests
from edge_tts import submaker as _submaker_mod

# edge_tts v7 compatibility layer
_EDGE_TTS_V7 = not hasattr(_submaker_mod, "mktimestamp") if hasattr(_submaker_mod, "__file__") else True

try:
    from edge_tts.submaker import mktimestamp
except ImportError:
    _EDGE_TTS_V7 = True
    def mktimestamp(ns: int) -> str:
        ms = ns // 10_000
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

if _EDGE_TTS_V7:
    from edge_tts import SubMaker as _OrigSubMaker
    submaker = _submaker_mod

    class SubMaker(_OrigSubMaker):
        """Compat wrapper: v6 .subs/.offset/.create_sub on top of v7 .cues/.feed."""

        def __init__(self):
            super().__init__()

        def create_sub(self, timing_tuple, text):
            offset_ns, duration_ns = timing_tuple
            self.feed({
                "type": "WordBoundary",
                "offset": offset_ns,
                "duration": duration_ns,
                "text": text,
            })

        @property
        def subs(self):
            return [c.content for c in self.cues]

        @subs.setter
        def subs(self, value):
            from datetime import timedelta
            self.cues = []
            for i, text in enumerate(value):
                self.cues.append(_submaker_mod.Subtitle(
                    index=i + 1, start=timedelta(0), end=timedelta(0), content=text,
                ))

        @property
        def offset(self):
            return [
                (int(c.start.total_seconds() * 10_000_000),
                 int(c.end.total_seconds() * 10_000_000))
                for c in self.cues
            ]

        @offset.setter
        def offset(self, value):
            pass
else:
    from edge_tts import SubMaker, submaker'''


def patch(voice_path: Path) -> None:
    """Apply edge_tts v7 patches to voice.py."""
    text = voice_path.read_text(encoding="utf-8")

    # Already patched?
    if "_EDGE_TTS_V7" in text:
        print(f"  Already patched: {voice_path}")
        return

    # 1. Replace import block
    old_imports = re.search(
        r"import edge_tts\nimport requests\nfrom edge_tts import SubMaker, submaker\n"
        r"from edge_tts\.submaker import mktimestamp",
        text,
    )
    if old_imports:
        text = text[:old_imports.start()] + COMPAT_BLOCK + text[old_imports.end():]
    else:
        print(f"  WARNING: Could not find original import block in {voice_path}")
        return

    # 2. Replace edge_tts.SubMaker() with SubMaker()
    text = text.replace("edge_tts.SubMaker()", "SubMaker()")

    # 3. Accept SentenceBoundary in stream handler
    text = text.replace(
        'chunk["type"] == "WordBoundary"',
        'chunk["type"] in ("WordBoundary", "SentenceBoundary")',
    )

    voice_path.write_text(text, encoding="utf-8")
    print(f"  Patched: {voice_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/voice.py")
        sys.exit(1)
    patch(Path(sys.argv[1]))
