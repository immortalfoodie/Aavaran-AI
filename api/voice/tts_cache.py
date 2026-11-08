"""
Small disk + memory cache for Timbre audio.

Saarthi's follow-up questions are fixed sentences, so caching them saves
programme credits and cuts reply latency to near zero after the first call.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Optional

_MEM_MAX = 128
_mem: "OrderedDict[str, bytes]" = OrderedDict()


def _cache_dir() -> Path:
    d = Path(os.environ.get("AAVARAN_TTS_CACHE_DIR") or Path(tempfile.gettempdir()) / "aavaran_tts_cache")
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(model: str, voice: str, lang: str, text: str) -> str:
    return hashlib.sha1(f"{model}|{voice}|{lang}|{text}".encode("utf-8")).hexdigest()


def get(key: str) -> Optional[bytes]:
    if key in _mem:
        _mem.move_to_end(key)
        return _mem[key]
    try:
        path = _cache_dir() / f"{key}.mp3"
        if path.exists():
            data = path.read_bytes()
            _remember(key, data)
            return data
    except OSError:
        return None
    return None


def put(key: str, data: bytes) -> None:
    _remember(key, data)
    try:
        (_cache_dir() / f"{key}.mp3").write_bytes(data)
    except OSError:
        pass


def _remember(key: str, data: bytes) -> None:
    _mem[key] = data
    _mem.move_to_end(key)
    while len(_mem) > _MEM_MAX:
        _mem.popitem(last=False)


def clear_memory() -> None:
    _mem.clear()
