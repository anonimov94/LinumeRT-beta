"""Wiązanie ctypes z rdzeniem natywnym (`native/`): szybkie jądro usuwania materiału.

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: Claude

Tryby (zmienna ``LRT_NATIVE``): ``auto`` (domyślnie; brak biblioteki = numpy), ``0`` (zawsze
numpy), ``1`` (wymagaj biblioteki, inaczej błąd). Bibliotekę buduje ``make -C native``;
wiązanie robi to samo przy pierwszym użyciu, jeśli jest kompilator.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from pathlib import Path

NATIVE_DIR = Path(__file__).resolve().parents[2] / "native"
LIB_PATH = NATIVE_DIR / "build" / "liblrt_native.so"
PROFILES = {"flat": 0, "ball": 1, "bull": 2, "cone": 3}
MAX_PARTS = 64

_lib: ctypes.CDLL | None = None
_tried = False


class ZMap(ctypes.Structure):
    _fields_ = [("h", ctypes.POINTER(ctypes.c_float)), ("nx", ctypes.c_int),
                ("ny", ctypes.c_int), ("x0", ctypes.c_double), ("y0", ctypes.c_double),
                ("cell", ctypes.c_double), ("z_bottom", ctypes.c_double),
                ("top_bound", ctypes.c_double)]


class CutterC(ctypes.Structure):
    _fields_ = [("profile", ctypes.c_int), ("radius", ctypes.c_double),
                ("corner", ctypes.c_double), ("cone_tan", ctypes.c_double)]


class CutResultC(ctypes.Structure):
    _fields_ = [("removed", ctypes.c_double), ("parts_mask", ctypes.c_uint64),
                ("has_contact", ctypes.c_int), ("contact", ctypes.c_double * 3)]


class GcodeMoves(ctypes.Structure):
    _fields_ = [("n", ctypes.c_int64),
                ("start", ctypes.POINTER(ctypes.c_float)),
                ("end", ctypes.POINTER(ctypes.c_float)),
                ("line", ctypes.POINTER(ctypes.c_int32)),
                ("tool", ctypes.POINTER(ctypes.c_int32)),
                ("kind", ctypes.POINTER(ctypes.c_int8)),
                ("feed", ctypes.POINTER(ctypes.c_float)),
                ("spindle", ctypes.POINTER(ctypes.c_float)),
                ("notes", ctypes.c_char_p), ("notes_len", ctypes.c_int64),
                ("error", ctypes.c_int), ("error_msg", ctypes.c_char * 320)]


def mode() -> str:
    return os.environ.get("LRT_NATIVE", "auto").strip().lower() or "auto"


def _build() -> bool:
    if shutil.which("make") is None or shutil.which(os.environ.get("CC", "cc")) is None:
        return False
    result = subprocess.run(["make", "-C", str(NATIVE_DIR)], capture_output=True, text=True)
    return result.returncode == 0 and LIB_PATH.is_file()


def load() -> ctypes.CDLL | None:
    """Zwraca bibliotekę albo ``None`` (tryb numpy). Wynik jest pamiętany."""
    global _lib, _tried
    if mode() in {"0", "off", "false", "numpy"}:
        return None
    if _tried:
        return _lib
    _tried = True
    sources = [*NATIVE_DIR.glob("*.c"), *NATIVE_DIR.glob("*.h")]
    stale = LIB_PATH.is_file() and any(
        s.is_file() and s.stat().st_mtime > LIB_PATH.stat().st_mtime for s in sources)
    if (not LIB_PATH.is_file() or stale) and not _build() and not LIB_PATH.is_file():
        if mode() in {"1", "on", "true"}:
            raise RuntimeError(f"LRT_NATIVE=1, ale brak {LIB_PATH} (make -C native)")
        return None
    lib = ctypes.CDLL(str(LIB_PATH))
    dp = ctypes.POINTER(ctypes.c_double)
    lib.lrt_zmap_cut.argtypes = [ctypes.POINTER(ZMap), ctypes.POINTER(CutterC), dp, dp,
                                 ctypes.c_int, dp, dp, ctypes.c_double, ctypes.c_double,
                                 ctypes.POINTER(CutResultC)]
    lib.lrt_zmap_cut.restype = ctypes.c_int
    lib.lrt_gcode_parse.argtypes = [ctypes.c_char_p, ctypes.c_int64, dp, ctypes.c_int]
    lib.lrt_gcode_parse.restype = ctypes.POINTER(GcodeMoves)
    lib.lrt_gcode_free.argtypes = [ctypes.POINTER(GcodeMoves)]
    lib.lrt_gcode_free.restype = None
    _lib = lib
    return lib


def reset_for_tests() -> None:
    global _lib, _tried
    _lib, _tried = None, False
