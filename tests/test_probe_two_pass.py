# SPDX-License-Identifier: GPL-2.0-or-later
"""Regresja sondowania dwuetapowego: drugi styk decyduje o G10."""

import pytest

from linumert.programs.probe_macro import PROBE_MACRO, probe_call
from linumert_headless.services.offset import ProbeRunIn


@pytest.mark.parametrize("axis,index,parameter", [
    ("X", 0, 5061), ("Y", 1, 5062), ("Z", 2, 5063),
])
def test_two_contacts_before_offset(axis, index, parameter):
    command = probe_call(axis, -1, 12, 50, "G54", 0, 2,
                         approach_feed=100, backoff=1.5)
    assert f"[{index}]" in command
    assert "[100]" in command and "[50]" in command and "[1.5]" in command
    start = PROBE_MACRO.index(f"o10 {'if' if index == 0 else 'elseif'} [#1 EQ {index}]")
    end = PROBE_MACRO.index("o10 endif", start)
    block = PROBE_MACRO[start:end]
    first = block.index(f"G38.2 {axis}#<dist>")
    withdraw = block.index(f"G1 {axis}#<backoff_move>")
    second = block.index(f"G38.2 {axis}#<fine_dist>")
    save = block.index(f"G10 L20 P#5 {axis}")
    assert first < withdraw < second < save
    assert f"#{parameter}" in block


def test_fine_pass_bounded_and_modal_saved():
    assert "#<backoff> + 0.5" in PROBE_MACRO
    assert "M73" in PROBE_MACRO
    assert "G21 G94" in PROBE_MACRO
    assert PROBE_MACRO.index("G38.2 Z#<fine_dist>") < PROBE_MACRO.index("G10 L20 P#5 Z")


def test_api_defaults_slow_fine_pass():
    request = ProbeRunIn(axis="Z", direction=-1, confirm=True)
    assert request.feed is None
    assert request.approach_feed is None
    assert request.backoff == 1.5
    with pytest.raises(ValueError):
        ProbeRunIn(axis="Z", direction=-1, backoff=0.5)
    with pytest.raises(ValueError):
        ProbeRunIn(axis="Z", direction=-1, backoff=2.5)
