"""Pętla symulacji offline w rdzeniu C (`native/lrt_sim.c`): to samo co `SimEngine.step`.

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: Claude

C liczy próbki, materiał, reguły K-3xx i obciążenia; tutaj budujemy jego konfigurację z
obiektów `SimEngine` i zamieniamy surowe zdarzenia na `Event` (teksty komunikatów z katalogu
alarmów składa Python). Wersja Python (`offline.py`) zostaje wzorcem i trybem zapasowym.
"""

from __future__ import annotations

import ctypes
import math
from collections.abc import Callable

import numpy as np

from . import native
from .engine import Event as PyEvent
from .engine import SimEngine, kc_for
from .machine import FIXTURE
from .path import MoveList

CHUNK = 200                      # segmentów między sprawdzeniem anulowania i raportem postępu
TOOL_NAME = "narzedzie"
STOCK_NAME = "przygotówka"

KIND = {301: "collision", 302: "collision", 303: "collision", 304: "collision",
        305: "collision", 308: "collision", 306: "overload", 307: "overload",
        309: "overload", 320: "warning", 322: "warning"}


class Unsupported(Exception):
    """Konfiguracja, której rdzeń C nie obsługuje (np. >64 części) — wraca ścieżka Python."""


class _Names:
    def __init__(self) -> None:
        self.ids: dict[str, int] = {}
        self.names: list[str] = []

    def id(self, name: str) -> int:
        if name not in self.ids:
            self.ids[name] = len(self.names)
            self.names.append(name)
        return self.ids[name]


def _array(ptr_type, array: np.ndarray, dtype):
    arr = np.ascontiguousarray(array, dtype=dtype)
    return arr, arr.ctypes.data_as(ptr_type)


def available(engine: SimEngine) -> bool:
    return native.load() is not None


def run(engine: SimEngine, ml: MoveList, *, dt: float, rapid: float,
        origin: tuple[float, float, float],
        progress: Callable[[float], None] | None,
        cancelled: Callable[[], bool] | None,
        cancel_exc: Callable[[int, int], Exception]) -> tuple[list[dict], float, dict]:
    """Zwraca (zdarzenia jako słowniki, czas całkowity, {"rapid", "feed"})."""
    lib = native.load()
    if lib is None:
        raise Unsupported("brak biblioteki natywnej")
    names = _Names()
    tool_name_id = names.id(TOOL_NAME)

    # ---- narzędzia, części, walce
    parts_py: list[tuple[str, float, float]] = []
    cyls_py: list[tuple[str, float, float, float]] = []
    tool_rows: list[tuple] = []
    for number, cutter in sorted(engine.tools.items()):
        own = list(cutter.parts())
        extra = engine._spindle_parts(cutter.gauge) if engine.stock is not None else []
        zparts = own + list(extra)
        if len(zparts) > native.MAX_PARTS:
            raise Unsupported("za dużo części nietnących")
        reach = max([cutter.radius] + [p[1] for p in zparts])
        tool_rows.append((number, cutter, len(parts_py), len(zparts), len(cyls_py), len(own),
                          reach))
        parts_py += [(p[0], p[1], p[2]) for p in zparts]
        cyls_py += [(p[0], p[1], p[2], p[3]) for p in own]
    ranks = {n: i for i, n in enumerate(sorted({p[0] for p in parts_py}))}
    parts = (native.SimPart * max(len(parts_py), 1))(
        *[native.SimPart(names.id(n), ranks[n], r, z) for n, r, z in parts_py])
    cyls = (native.SimCyl * max(len(cyls_py), 1))(
        *[native.SimCyl(names.id(n), r, z0, z1) for n, r, z0, z1 in cyls_py])
    tools = (native.SimTool * max(len(tool_rows), 1))()
    for i, (number, c, p_off, n_p, c_off, n_c, reach) in enumerate(tool_rows):
        tools[i] = native.SimTool(
            number, c.gauge, c.radius, c.cut_top, float(c.max_rpm or 0.0),
            int(c.kind == "tap"), c.hand, int(c.undercut), int(c.substitute), reach,
            native.CutterC(native.profile_of(c), c.radius, c.corner, c.cone_tan),
            p_off, n_p, c_off, n_c)

    # ---- bryły maszyny
    bodies_py = engine.machine.bodies
    bodies = (native.SimBody * max(len(bodies_py), 1))()
    for i, b in enumerate(bodies_py):
        size = (list(b.size) + [0.0, 0.0, 0.0])[:3]
        bodies[i] = native.SimBody(
            names.id(b.name), int(b.shape == "cylinder"), int(b.moving),
            int(b.attached in FIXTURE), int(b.attached == "toolsetter"),
            int(b.attached == "magazine"), (ctypes.c_double * 3)(*size),
            (ctypes.c_double * 3)(*b.position))
    curve = engine.machine.spindle_curve
    curve_w = (ctypes.c_double * max(len(curve), 1))(*[w for w, _ in curve])
    curve_t = (ctypes.c_double * max(len(curve), 1))(*[t for _, t in curve])

    # ---- ruchy
    keep, start = _array(ctypes.POINTER(ctypes.c_float), ml.start, np.float32)
    _end, end = _array(ctypes.POINTER(ctypes.c_float), ml.end, np.float32)
    _line, line = _array(ctypes.POINTER(ctypes.c_int32), ml.line, np.int32)
    _tool, tool = _array(ctypes.POINTER(ctypes.c_int32), ml.tool, np.int32)
    _kind, kind = _array(ctypes.POINTER(ctypes.c_int8), ml.kind, np.int8)
    _feed, feed = _array(ctypes.POINTER(ctypes.c_float), ml.feed, np.float32)
    _spin, spindle = _array(ctypes.POINTER(ctypes.c_float), ml.spindle, np.float32)
    n = len(ml)
    # Długości liczy Python (math.dist) — dokładnie jak wzorzec; ceil(sekundy/dt) jest nieciągły,
    # więc różnica 1 ulp względem pierwiastka z C mogłaby zmienić liczbę próbek.
    dist_arr = np.fromiter((math.dist(a, b) for a, b in zip(
        ml.start.astype(float).tolist(), ml.end.astype(float).tolist(), strict=True)),
        dtype=np.float64, count=n)
    dist = dist_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

    stock_struct = engine.stock.native_struct() if engine.stock is not None else None
    cfg = native.SimConfig(
        dt=dt, rapid=rapid, origin=(ctypes.c_double * 3)(*origin), kc=kc_for(engine.material),
        spindle_power=engine.machine.spindle_power,
        curve_w=curve_w, curve_t=curve_t, n_curve=len(curve),
        axis_force=(ctypes.c_double * 3)(*[engine.machine.force_limit(a) for a in "XYZ"]),
        tool_name_id=tool_name_id, tools=tools, n_tools=len(tool_rows), parts=parts, cyls=cyls,
        bodies=bodies, n_bodies=len(bodies_py),
        stock=ctypes.pointer(stock_struct) if stock_struct is not None else None,
        n=n, start=start, end=end, line=line, tool=tool, kind=kind, feed=feed, spindle=spindle,
        dist=dist)
    handle = lib.lrt_sim_new(ctypes.byref(cfg))
    if not handle:
        raise Unsupported("rdzeń odrzucił konfigurację")
    try:
        if lib.lrt_sim_begin(handle) != 0:
            raise MemoryError("rdzeń symulacji: brak pamięci")
        for i0 in range(0, n, CHUNK):
            if cancelled is not None and cancelled():
                raise cancel_exc(i0, n)
            i1 = min(i0 + CHUNK, n)
            if lib.lrt_sim_run(handle, i0, i1) != 0:
                raise MemoryError("rdzeń symulacji: brak pamięci")
            if progress is not None:
                progress(i1 / n)
        events = _events(lib, handle, names)
        total = lib.lrt_sim_time(handle)
        times = {"rapid": lib.lrt_sim_time_rapid(handle), "feed": lib.lrt_sim_time_feed(handle)}
    finally:
        lib.lrt_sim_free(handle)
    del dist_arr, keep, _end, _line, _tool, _kind, _feed, _spin, stock_struct
    if engine.stock is not None:
        engine.stock.version += 1
    return events, total, times


def _events(lib, handle, names: _Names) -> list[dict]:
    count = int(lib.lrt_sim_event_count(handle))
    raw = lib.lrt_sim_events(handle)
    out: list[dict] = []
    for k in range(count):
        e = raw[k]
        code = f"K-{e.code}"
        pos = (e.pos[0], e.pos[1], e.pos[2])
        a = names.names[e.id_a] if e.id_a >= 0 else ""
        b = names.names[e.id_b] if e.id_b >= 0 else ""
        pair: tuple[str, str] | None
        if e.code in (301, 302, 308):
            params = {"line": e.line, "tool": e.tool}
            pair = (TOOL_NAME, STOCK_NAME)
            if e.code == 308:
                params["direction"] = e.s1.decode("utf-8")
        elif e.code == 303:
            params, pair = {"line": e.line, "part": a}, (a, STOCK_NAME)
        elif e.code == 304:
            params, pair = {"line": e.line, "tool": e.tool}, (a, b)
        elif e.code == 305:
            params, pair = {"line": e.line, "element": f"{a} – {b}"}, (a, b)
        elif e.code == 306:
            params = {"line": e.line, "torque": e.s1.decode(), "limit": e.s2.decode()}
            pair = ("wrzeciono", "")
        elif e.code == 307:
            axis = "XYZ"[e.i1]
            params = {"line": e.line, "axis": axis, "force": int(e.i2), "limit": int(e.i3)}
            pair = (f"oś {axis}", "")
        elif e.code == 309:
            params, pair = {"tool": e.tool, "rpm": int(e.i1), "limit": int(e.i2)}, None
        else:                                         # 320, 322
            params, pair = {"tool": e.tool}, None
        out.append(PyEvent(code, KIND[e.code], e.line, e.tool, pos, params, pair).to_dict())
    return out


__all__ = ["Unsupported", "available", "run"]
