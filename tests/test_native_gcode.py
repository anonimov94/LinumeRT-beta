"""Parytet interpretera podzbioru G-code: rdzeń C (native/) kontra wersja Python.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from __future__ import annotations

import random
import shutil

import numpy as np
import pytest

from linumert_sim import native
from linumert_sim.path import parse_subset

pytestmark = pytest.mark.skipif(shutil.which("cc") is None, reason="brak kompilatora C")

CORPUS = {
    "podstawy": ("G21 G90 G17\nT1 M6\nM3 S12000\nG0 X0 Y0 Z5\nG1 Z-1 F300\n"
                 "G1 X10 Y10 F800\nM5\nM30\n"),
    "cale_i_przyrosty": "G20\nG0 X1 Y1\nG91\nG1 X0.5 Y-0.25 F10\nG90\nG1 X2 F20\n",
    "luki_ij": "G0 X10 Y0\nG3 X0 Y10 I-10 J0 F500\nG2 X10 Y0 I0 J-10\n",
    "luk_pelny": "G0 X10 Y0\nG2 X10 Y0 I-10 J0 F500\nG3 X10 Y0 I-10 J0 P2\n",
    "luk_r": "G0 X0 Y0\nG2 X10 Y0 R6 F300\nG3 X0 Y0 R-6\nG2 X10 Y0 R5.000001\n",
    "luk_abs_ij": "G90.1\nG0 X10 Y0\nG2 X0 Y10 I0 J0 F300\nG91.1\n",
    "plaszczyzny": "G18\nG0 X5 Z0\nG3 X0 Z5 I-5 K0 F300\nG19\nG0 Y0 Z0\nG2 Y5 Z5 J0 K5\n",
    "luk_spirala": "G0 X10 Y0 Z0\nG3 X10 Y0 Z-3 I-10 J0 P3 F400\n",
    "cykle": ("G90 G0 X0 Y0 Z10\nG98 G81 X5 Y5 Z-5 R2 F100\nX10\nG99 G82 X15 R3\n"
              "G83 X20 Z-9 R2 Q3\nG73 X25 Z-9 R2 Q2.5\nG80\nG0 Z10\n"),
    "cykl_g91": "G91\nG81 X5 Y5 Z-5 R2 F100\nX5\nG80\n",
    "cykl_poza_g17": "G18\nG81 X5 Z-5 R2 F100\n",
    "komentarze": ("(start) G0 X1 (komentarz) Y2 ; reszta\n; cala linia\n(tylko)\n%\n"
                   "G1 X3 F100 (a;b) X4\n"),
    "slowa_o": ("O100 sub\nG0 X99\nO100 endsub\nG0 X1\nO<abc> sub\nG1 X50 F1\nO<abc> endsub\n"
                "O200 call\no300 if [1]\nO100\nO 7 while\nO<x\nG0 X2\n"),
    "tabulatory_i_male_litery": "g0\tx1\ty2\nG1 x 3 y\t4 f 500\nm3 s1000\n",
    "nieobslugiwane": ("G28\nG0 X1\nG41 D1\nG0 X2\nG53 G0 X0\nG999 X5\nG10 L2 P1 X0\n"
                       "G92 X0\nG0 X3\n"),
    "bez_trybu": "X5 Y5\nG1 X1 F10\nG80\nX7\n",
    "konce_linii": "G0 X1\r\nG0 X2\rG0 X3\x0cG0 X4\x0bG0 X5\n",
    "koniec_m2": "G0 X1\nM2\nG0 X2\n",
    "narzedzie_i_wrzeciono": ("T3 M6\nM3 S500\nG1 X1 F10\nM4\nG1 X2\nM3 M5\nG1 X3\nT5\n"
                              "G1 X4\nM6\nG1 X5\n"),
    "cyfry_kodow": "G01 X1 F10\nG00 X2\nG1.0 X3\nG17.1\nG59.1\nG64 P0.01\nG4 P1\nM06\n",
    "przeciag_g_w_linii": "G0 G1 G2 X1 Y1 I1 J0 F1\n",
}

ERRORS = {
    "luk_r_za_maly": "G0 X0 Y0\nG2 X10 Y0 R2\n",
    "luk_r_zerowa_cieciwa": "G0 X0 Y0\nG2 X0 Y0 R2\n",
    "luk_p0": "G0 X10 Y0\nG3 X0 Y10 I-10 P0 F1\n",
    "cykl_bez_r": "G81 X1 Z-2 F10\n",
    "cykl_bez_z": "G81 X1 R2 F10\n",
    "nieskonczonosc": "G1 X" + "9" * 400 + " F10\n",
}


def _run(mode: str, monkeypatch, text, **kwargs):
    monkeypatch.setenv("LRT_NATIVE", mode)
    native.reset_for_tests()
    try:
        return parse_subset(text, **kwargs)
    except ValueError as exc:
        return exc


def _same(ref, got) -> None:
    if isinstance(ref, ValueError):
        assert isinstance(got, ValueError), "C nie zgłosił błędu zgłoszonego przez Python"
        assert str(got) == str(ref)
        return
    assert not isinstance(got, ValueError), f"C zgłosił błąd: {got}"
    assert len(got) == len(ref)
    assert got.notes == ref.notes
    assert np.array_equal(got.line, ref.line)
    assert np.array_equal(got.tool, ref.tool)
    assert np.array_equal(got.kind, ref.kind)
    assert np.array_equal(got.feed, ref.feed)
    assert np.array_equal(got.spindle, ref.spindle)
    np.testing.assert_allclose(got.start, ref.start, rtol=1e-5, atol=1e-4)
    np.testing.assert_allclose(got.end, ref.end, rtol=1e-5, atol=1e-4)


@pytest.fixture(autouse=True)
def _reset_native():
    yield
    native.reset_for_tests()


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_korpus_programow(name, monkeypatch) -> None:
    ref = _run("0", monkeypatch, CORPUS[name])
    got = _run("1", monkeypatch, CORPUS[name])
    assert not isinstance(ref, ValueError), ref
    _same(ref, got)


@pytest.mark.parametrize("name", sorted(ERRORS))
def test_bledy_maja_te_same_komunikaty(name, monkeypatch) -> None:
    ref = _run("0", monkeypatch, ERRORS[name])
    got = _run("1", monkeypatch, ERRORS[name])
    assert isinstance(ref, ValueError), "scenariusz błędu przestał zgłaszać błąd w Pythonie"
    _same(ref, got)


def test_punkt_startowy_i_cale(monkeypatch) -> None:
    text = "G91\nG1 X1 Y2 Z3 F10\n"
    ref = _run("0", monkeypatch, text, start=(5.0, 6.0, 7.0), metric=False)
    got = _run("1", monkeypatch, text, start=(5.0, 6.0, 7.0), metric=False)
    _same(ref, got)


def test_rdzen_c_jest_naprawde_uzywany(monkeypatch) -> None:
    monkeypatch.setenv("LRT_NATIVE", "1")
    native.reset_for_tests()
    assert native.load() is not None


def test_pusty_i_samymi_komentarzami(monkeypatch) -> None:
    for text in ("", "\n", "(nic)\n; nic\n", "   \n\n"):
        _same(_run("0", monkeypatch, text), _run("1", monkeypatch, text))


TEMPLATES = [
    "G0 X{a} Y{b} Z{c}", "G1 X{a} Y{b} F{f}", "G1 Z{c} F{f}", "G2 X{a} Y{b} I{i} J{j}",
    "G3 X{a} Y{b} R{r} F{f}", "G2 X{a} Y{b} I{i} J{j} P{p}", "G81 X{a} Y{b} Z{c} R{r} F{f}",
    "G83 X{a} Y{b} Z-{d} R2 Q{d}", "G73 Z-{d} R1 Q1.5", "G80", "G90", "G91", "G20", "G21",
    "G17", "G18", "G19", "G98", "G99", "G90.1", "G91.1", "T{p} M6", "M3 S{f}", "M4", "M5",
    "X{a}", "Y{b} Z{c}", "G28", "G41 D1", "(komentarz) G1 X{a}", "; nic", "O1 sub", "O1 endsub",
    "O2 call", "S{f}", "F{f}", "G54", "G64 P0.1", "G4 P{p}", "%", "",
]


def _fuzz_program(rng: random.Random) -> str:
    lines = []
    for _ in range(rng.randint(5, 60)):
        t = rng.choice(TEMPLATES)
        lines.append(t.format(
            a=round(rng.uniform(-50, 50), rng.choice([0, 1, 3])),
            b=round(rng.uniform(-50, 50), rng.choice([0, 1, 3])),
            c=round(rng.uniform(-10, 10), 2), f=rng.choice([100, 250, 800, 1200]),
            i=round(rng.uniform(-20, 20), 2), j=round(rng.uniform(-20, 20), 2),
            r=round(rng.uniform(-30, 30), 2), p=rng.randint(0, 4), d=rng.randint(1, 9)))
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("seed", range(150))
def test_fuzzing_zgodny_z_pythonem(seed, monkeypatch) -> None:
    text = _fuzz_program(random.Random(seed))
    _same(_run("0", monkeypatch, text), _run("1", monkeypatch, text))
