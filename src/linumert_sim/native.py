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


def profile_of(cutter) -> int:
    """Rodzaj profilu części tnącej jak w ``Cutter.lower`` (kolejność warunków ma znaczenie)."""
    if cutter.kind in ("ball", "lollipop"):
        return PROFILES["ball"]
    if cutter.kind == "bull" and cutter.corner > 0:
        return PROFILES["bull"]
    if cutter.cone_tan > 0:
        return PROFILES["cone"]
    return PROFILES["flat"]


class SimPart(ctypes.Structure):
    _fields_ = [("name_id", ctypes.c_int), ("rank", ctypes.c_int),
                ("r", ctypes.c_double), ("z", ctypes.c_double)]


class SimCyl(ctypes.Structure):
    _fields_ = [("name_id", ctypes.c_int), ("r", ctypes.c_double),
                ("z0", ctypes.c_double), ("z1", ctypes.c_double)]


class SimTool(ctypes.Structure):
    _fields_ = [("number", ctypes.c_int), ("gauge", ctypes.c_double),
                ("radius", ctypes.c_double), ("cut_top", ctypes.c_double),
                ("max_rpm", ctypes.c_double), ("tap", ctypes.c_int), ("hand", ctypes.c_int),
                ("undercut", ctypes.c_int), ("substitute", ctypes.c_int),
                ("reach", ctypes.c_double), ("cutter", CutterC),
                ("part_off", ctypes.c_int), ("n_parts", ctypes.c_int),
                ("cyl_off", ctypes.c_int), ("n_cyl", ctypes.c_int)]


class SimBody(ctypes.Structure):
    _fields_ = [("name_id", ctypes.c_int), ("cylinder", ctypes.c_int),
                ("moving", ctypes.c_int), ("fixture", ctypes.c_int),
                ("toolsetter", ctypes.c_int), ("magazine", ctypes.c_int),
                ("size", ctypes.c_double * 3), ("pos", ctypes.c_double * 3)]


class SimConfig(ctypes.Structure):
    _fields_ = [("dt", ctypes.c_double), ("rapid", ctypes.c_double),
                ("origin", ctypes.c_double * 3), ("kc", ctypes.c_double),
                ("spindle_power", ctypes.c_double),
                ("curve_w", ctypes.POINTER(ctypes.c_double)),
                ("curve_t", ctypes.POINTER(ctypes.c_double)), ("n_curve", ctypes.c_int),
                ("axis_force", ctypes.c_double * 3), ("tool_name_id", ctypes.c_int),
                ("tools", ctypes.POINTER(SimTool)), ("n_tools", ctypes.c_int),
                ("parts", ctypes.POINTER(SimPart)), ("cyls", ctypes.POINTER(SimCyl)),
                ("bodies", ctypes.POINTER(SimBody)), ("n_bodies", ctypes.c_int),
                ("stock", ctypes.POINTER(ZMap)), ("n", ctypes.c_int64),
                ("start", ctypes.POINTER(ctypes.c_float)),
                ("end", ctypes.POINTER(ctypes.c_float)),
                ("line", ctypes.POINTER(ctypes.c_int32)),
                ("tool", ctypes.POINTER(ctypes.c_int32)),
                ("kind", ctypes.POINTER(ctypes.c_int8)),
                ("feed", ctypes.POINTER(ctypes.c_float)),
                ("spindle", ctypes.POINTER(ctypes.c_float)),
                ("dist", ctypes.POINTER(ctypes.c_double))]


class SimEvent(ctypes.Structure):
    _fields_ = [("code", ctypes.c_int), ("kind", ctypes.c_int), ("line", ctypes.c_int),
                ("tool", ctypes.c_int), ("pos", ctypes.c_double * 3),
                ("id_a", ctypes.c_int), ("id_b", ctypes.c_int),
                ("i1", ctypes.c_long), ("i2", ctypes.c_long), ("i3", ctypes.c_long),
                ("s1", ctypes.c_char * 40), ("s2", ctypes.c_char * 40)]


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
    lib.lrt_sim_new.argtypes = [ctypes.POINTER(SimConfig)]
    lib.lrt_sim_new.restype = ctypes.c_void_p
    lib.lrt_sim_free.argtypes = [ctypes.c_void_p]
    lib.lrt_sim_free.restype = None
    lib.lrt_sim_begin.argtypes = [ctypes.c_void_p]
    lib.lrt_sim_begin.restype = ctypes.c_int
    lib.lrt_sim_run.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
    lib.lrt_sim_run.restype = ctypes.c_int
    for name in ("time", "time_rapid", "time_feed"):
        fn = getattr(lib, f"lrt_sim_{name}")
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = ctypes.c_double
    lib.lrt_sim_event_count.argtypes = [ctypes.c_void_p]
    lib.lrt_sim_event_count.restype = ctypes.c_int64
    lib.lrt_sim_events.argtypes = [ctypes.c_void_p]
    lib.lrt_sim_events.restype = ctypes.POINTER(SimEvent)
    _lib = lib
    return lib


def reset_for_tests() -> None:
    global _lib, _tried
    _lib, _tried = None, False
