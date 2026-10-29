"""Parytet rdzenia C (native/) z wersją numpy usuwania materiału 2.5D.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from linumert_sim import native
from linumert_sim.cutter import Cutter
from linumert_sim.zmap import StockMap

NATIVE_DIR = Path(__file__).resolve().parent.parent / "native"
pytestmark = pytest.mark.skipif(shutil.which("cc") is None, reason="brak kompilatora C")

CUTTERS = {
    "flat": Cutter(1, "flat", 3.0, 20.0, 3.0, 25.0, 60.0, 16.0),
    "ball": Cutter(2, "ball", 2.5, 15.0, 2.5, 22.0, 55.0, 14.0),
    "bull": Cutter(3, "bull", 4.0, 18.0, 4.0, 24.0, 58.0, 15.0, corner=1.0),
    "cone": Cutter(4, "v", 5.0, 8.0, 2.0, 20.0, 50.0, 14.0, cone_tan=0.7),
}
SPINDLE = [("wrzeciono", 30.0, 4.0, 60.0)]   # dolna krawędź 4 mm nad czubkiem: łapie materiał


def _run(mode: str, monkeypatch, shape: str, cutter: Cutter, seed: int, parts):
    monkeypatch.setenv("LRT_NATIVE", mode)
    native.reset_for_tests()
    rng = random.Random(seed)
    stock = StockMap(shape, 0, 0, 60, 40, -8, 0, cell=0.5)
    results = []
    for _ in range(60):
        p0 = (rng.uniform(-5, 65), rng.uniform(-5, 45), rng.uniform(-9, 3))
        p1 = (rng.uniform(-5, 65), rng.uniform(-5, 45), rng.uniform(-9, 3))
        res = stock.cut(cutter, p0, p1, parts)
        results.append((res.removed, sorted(res.parts), res.contact_at))
    return stock, results


@pytest.fixture(autouse=True)
def _reset_native():
    yield
    native.reset_for_tests()


@pytest.mark.parametrize("kind", sorted(CUTTERS))
@pytest.mark.parametrize("shape", ["BOX", "CYL"])
@pytest.mark.parametrize("with_spindle", [False, True])
def test_c_i_numpy_daja_ten_sam_wynik(kind, shape, with_spindle, monkeypatch) -> None:
    cutter = CUTTERS[kind]
    parts = SPINDLE if with_spindle else ()
    ref, ref_res = _run("0", monkeypatch, shape, cutter, 7, parts)
    got, got_res = _run("1", monkeypatch, shape, cutter, 7, parts)
    assert np.array_equal(np.isinf(ref.h), np.isinf(got.h))
    finite = np.isfinite(ref.h)
    assert np.array_equal(ref.h[finite], got.h[finite])
    for (r_rem, r_parts, r_at), (g_rem, g_parts, g_at) in zip(ref_res, got_res, strict=True):
        assert g_rem == pytest.approx(r_rem, rel=1e-5, abs=1e-6)
        assert g_parts == r_parts
        assert (g_at is None) == (r_at is None)
        if r_at is not None:
            assert g_at == pytest.approx(r_at)
    assert got.volume() == pytest.approx(ref.volume(), rel=1e-6)
    if with_spindle:
        assert any(r[1] for r in ref_res), "test nie sprawdza kontaktu części nietnących"


def test_wersja_zapasowa_dziala_bez_biblioteki(monkeypatch) -> None:
    monkeypatch.setenv("LRT_NATIVE", "0")
    native.reset_for_tests()
    assert native.load() is None
    stock = StockMap("BOX", 0, 0, 20, 20, -5, 0)
    assert stock.cut(CUTTERS["flat"], (10, 10, -2), (12, 10, -2)).removed > 0


def test_testy_c_przechodza() -> None:
    result = subprocess.run(["make", "-C", str(NATIVE_DIR), "test"], capture_output=True,
                            text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK: test_zmap" in result.stdout
