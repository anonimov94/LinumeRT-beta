"""Parytet pętli symulacji offline: rdzeń C (native/lrt_sim.c) kontra wzorcowy Python.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from __future__ import annotations

import random
import shutil

import numpy as np
import pytest

from linumert.programs.stock import parse_stock_line
from linumert_sim import native, native_sim, offline
from linumert_sim.cutter import make_cutter
from linumert_sim.engine import SimEngine
from linumert_sim.machine import Body, Machine
from linumert_sim.placement import place_stock

pytestmark = pytest.mark.skipif(shutil.which("cc") is None, reason="brak kompilatora C")

STOCK = ";@STOCK BOX X100 Y100 Z20"
FLAT = make_cutter(1, 30.0, 6.0, "flat", {"max_rpm": 10000.0, "l": 25.0})


@pytest.fixture(autouse=True)
def _native_on(monkeypatch):
    monkeypatch.setenv("LRT_NATIVE", "1")
    native.reset_for_tests()
    yield
    native.reset_for_tests()


def build(program, stock, cutters, machine=None, origin=(0.0, 0.0, 0.0), dt=0.05, rapid=5000.0):
    job = offline.OfflineJob(program=program, stock=stock, origin=origin, rapid=rapid, dt=dt,
                             source="subset")
    ml = offline.movelist(job)
    engine = SimEngine(machine)
    parsed = parse_stock_line(stock)
    engine.set_stock(place_stock(parsed, origin), parsed.material)
    engine.set_tools({c.number: c for c in cutters})
    return job, ml, engine


def both(*args, **kwargs):
    """Uruchamia tę samą symulację w Pythonie i w C; zwraca oba wyniki i oba silniki."""
    job, ml, py_engine = build(*args, **kwargs)
    py = offline._loop_python(py_engine, ml, job, None, None)
    job, ml, c_engine = build(*args, **kwargs)
    c = native_sim.run(c_engine, ml, dt=job.dt, rapid=job.rapid, origin=job.origin,
                       progress=None, cancelled=None,
                       cancel_exc=lambda i, n: RuntimeError(f"anulowano {i}/{n}"))
    return py, c, py_engine, c_engine


def assert_same(py, c, py_engine, c_engine) -> None:
    assert c[0] == py[0], "zdarzenia różne"
    assert c[1] == pytest.approx(py[1], rel=1e-12, abs=1e-12)
    for key in ("rapid", "feed"):
        assert c[2][key] == pytest.approx(py[2][key], rel=1e-12, abs=1e-12)
    assert np.array_equal(py_engine.stock.h, c_engine.stock.h), "mapa materiału różna"


def codes(result) -> set[str]:
    return {e["code"] for e in result[0]}


MACHINE = Machine(bodies=[
    Body("imadlo", "box", "vise", (14.0, 14.0, 30.0), (62.0, 35.0, -10.0)),
    Body("stol", "box", "table", (12.0, 12.0, 20.0), (22.0, 22.0, -5.0)),
    Body("czujnik", "box", "toolsetter", (10.0, 10.0, 10.0), (50.0, 80.0, -3.0)),
    Body("magazyn", "box", "magazine", (10.0, 10.0, 10.0), (80.0, 80.0, -3.0)),
    Body("wrzeciono", "cylinder", "spindle", (40.0, 20.0), (0.0, 0.0, 12.0)),
    Body("glowica", "cylinder", "head", (50.0, 30.0), (0.0, 0.0, 40.0)),
], spindle_power=100.0, axis_force={"X": 20.0, "Y": 20.0, "Z": 20.0})

SCENARIOS = {
    "kontakt_bez_obrotow_szybki_zly_kierunek_obroty": (
        "T1 M6\nG0 X20 Y20 Z5\nG1 Z-2 F200\nM3 S20000\nG0 X40 Z-3\nM4 S8000\nG1 X60 F300\n"
        "M3 S8000\nG1 X70 Y50 Z-24 F300\nG0 Z30\n",
        {"K-301", "K-302", "K-308", "K-309"}, None),
    "oprawka_w_materiale": (
        "T1 M6\nM3 S8000\nG0 X30 Y30 Z5\nG1 Z-1 F200\nG1 X35 Z-26 F200\nG0 Z40\n",
        {"K-303"}, None),
    "bryly_maszyny_i_przeciazenia": (
        "T1 M6\nM3 S8000\nG0 X20 Y20 Z5\nG1 Z-3 F300\nG1 X70 Y50 F600\nG1 X52 Y80 Z-1 F300\n"
        "G1 X80 Y80 F300\nG0 Z20\nG0 X20 Y20\n",
        {"K-304", "K-305", "K-306", "K-307"}, MACHINE),
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenariusze_daja_te_same_zdarzenia(name) -> None:
    program, expected, machine = SCENARIOS[name]
    stock = STOCK + (" MAT=stal" if machine else "")
    py, c, pe, ce = both(program, stock, [FLAT], machine=machine)
    assert expected <= codes(py), f"scenariusz nie wywołuje {expected - codes(py)}"
    assert_same(py, c, pe, ce)


def test_ostrzezenia_narzedzi_bez_geometrii_i_z_podcieciem() -> None:
    substitute = make_cutter(2, 40.0, 5.0, None, {})
    tslot = make_cutter(3, 40.0, 8.0, "tslot", {"width": 3.0})
    # pierwsza próbka programu jest odrzucana (jak w simulate), więc zaczynamy zwykłym frezem
    program = ("T1 M6\nM3 S9000\nG0 X10 Y10 Z5\nG1 Z-1 F200\nT3 M6\nM3 S9000\nG1 X30 Z-2 F200\n"
               "T2 M6\nM3 S9000\nG1 X40 F200\n")
    py, c, pe, ce = both(program, STOCK, [FLAT, substitute, tslot])
    assert {"K-320", "K-322"} <= codes(py)
    assert_same(py, c, pe, ce)


def test_przerwa_dluzsza_niz_sekunda_i_zmiana_narzedzia() -> None:
    other = make_cutter(2, 35.0, 4.0, "ball", {"l": 20.0})
    program = ("T1 M6\nM3 S8000\nG0 X10 Y10 Z5\nG1 Z-2 F20\nG1 X90 F20\nT2 M6\nM3 S8000\n"
               "G1 Y90 F400\n")
    py, c, pe, ce = both(program, STOCK, [FLAT, other], rapid=60.0)
    assert_same(py, c, pe, ce)


def test_brak_materialu_i_przesuniecie_ukladu() -> None:
    program = "T1 M6\nM3 S8000\nG0 X10 Y10 Z5\nG1 X50 Z-1 F300\n"
    py, c, pe, ce = both(program, STOCK, [FLAT], origin=(5.0, -3.0, 2.0))
    assert_same(py, c, pe, ce)


def test_anulowanie_i_postep() -> None:
    job, ml, engine = build("T1 M6\nM3 S8000\n" + "G1 X10 F100\nG1 X20\n" * 300, STOCK, [FLAT])
    seen: list[float] = []
    native_sim.run(engine, ml, dt=job.dt, rapid=job.rapid, origin=job.origin,
                   progress=seen.append, cancelled=None, cancel_exc=RuntimeError)
    assert seen and seen[-1] == 1.0 and seen == sorted(seen)
    job, ml, engine = build("T1 M6\nM3 S8000\n" + "G1 X10 F100\nG1 X20\n" * 300, STOCK, [FLAT])
    with pytest.raises(offline.Cancelled, match="anulowano po 0 z"):
        native_sim.run(engine, ml, dt=job.dt, rapid=job.rapid, origin=job.origin,
                       progress=None, cancelled=lambda: True,
                       cancel_exc=lambda i, n: offline.Cancelled(f"anulowano po {i} z {n}"))


def test_simulate_daje_ten_sam_wynik_w_obu_trybach(monkeypatch) -> None:
    program = ";@STOCK BOX X100 Y100 Z20\nT1 M6\nM3 S9000\nG0 X10 Y10 Z5\nG1 Z-2 F300\n" \
              "G1 X80 Y60 F500\nG2 X80 Y20 I0 J-20\nG0 Z30\n"
    job = offline.OfflineJob(program=program, tools=((1, 40.0, 6.0),))
    results = {}
    for mode in ("0", "1"):
        monkeypatch.setenv("LRT_NATIVE", mode)
        native.reset_for_tests()
        results[mode] = offline.simulate(job)
    assert results["1"] == results["0"]


# ---- fuzzing -----------------------------------------------------------------------------

KINDS = ["flat", "ball", "bull", "chamfer", "drill_118", "tap", "face_mill", "tslot",
         "lollipop", None]
MATERIALS = ["", " MAT=aluminium", " MAT=stal", " MAT=drewno", " MAT=nieznany"]


def _fuzz_tools(rng: random.Random):
    tools = []
    for number in (1, 2, 3):
        kind = rng.choice(KINDS)
        d = rng.choice([2.0, 3.0, 6.0, 10.0, 16.0])
        params = {"l": rng.choice([15.0, 25.0, 40.0]),
                  "max_rpm": rng.choice([0.0, 6000.0, 15000.0]),
                  "hand": rng.choice([1, 1, -1]), "corner_radius": d / 4, "angle": 90.0}
        params = {k: v for k, v in params.items() if not (k == "max_rpm" and v == 0.0)}
        tools.append(make_cutter(number, rng.choice([30.0, 45.0, 60.0]), d, kind, params))
    return tools


def _fuzz_machine(rng: random.Random):
    if rng.random() < 0.4:
        return None
    bodies = []
    for i in range(rng.randint(1, 5)):
        attached = rng.choice(["vise", "fixture", "table", "toolsetter", "magazine", "spindle",
                               "head"])
        shape = rng.choice(["box", "cylinder"])
        size = ((rng.uniform(5, 40), rng.uniform(5, 40), rng.uniform(5, 40)) if shape == "box"
                else (rng.uniform(10, 60), rng.uniform(5, 60)))
        pos = (rng.uniform(0, 100), rng.uniform(0, 100), rng.uniform(-15, 15))
        bodies.append(Body(f"b{i}_{attached}", shape, attached, size, pos))
    curve = [(100.0, 1.0), (500.0, 0.8), (900.0, 0.2)] if rng.random() < 0.3 else []
    return Machine(bodies=bodies, spindle_power=rng.choice([100.0, 800.0, 2200.0]),
                   axis_force={"X": rng.choice([15.0, 100.0]), "Y": 60.0, "Z": 40.0},
                   spindle_curve=curve)


def _fuzz_program(rng: random.Random) -> str:
    lines = ["G21 G90"]
    for _ in range(rng.randint(8, 40)):
        pick = rng.random()
        if pick < 0.12:
            lines.append(f"T{rng.choice([1, 2, 3])} M6")
        elif pick < 0.25:
            lines.append(rng.choice(["M3", "M4", "M5"]) + f" S{rng.choice([0, 500, 8000, 20000])}")
        elif pick < 0.45:
            lines.append(f"G0 X{rng.uniform(0, 100):.2f} Y{rng.uniform(0, 100):.2f} "
                         f"Z{rng.uniform(-8, 30):.2f}")
        else:
            lines.append(f"G1 X{rng.uniform(0, 100):.2f} Y{rng.uniform(0, 100):.2f} "
                         f"Z{rng.uniform(-12, 10):.2f} F{rng.choice([60, 300, 900, 2500])}")
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("seed", range(80))
def test_fuzzing_zgodny_z_pythonem(seed) -> None:
    rng = random.Random(seed)
    program = _fuzz_program(rng)
    stock = STOCK.replace("X100", f"X{rng.choice([60, 100])}") + rng.choice(MATERIALS)
    kwargs = {"machine": _fuzz_machine(rng), "dt": rng.choice([0.02, 0.05, 0.2]),
              "rapid": rng.choice([800.0, 5000.0]),
              "origin": (rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(-3, 3))}
    py, c, pe, ce = both(program, stock, _fuzz_tools(rng), **kwargs)
    assert_same(py, c, pe, ce)
