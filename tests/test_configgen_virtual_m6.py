"""Regresja wygenerowanego handshake M6 dla trybów bez GUI.

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: ChatGPT
"""

from types import SimpleNamespace

from linumert.machine.configgen import render_plant_hal, render_sim_hal


def _machine():
    io = SimpleNamespace(
        inputs={"estop_a": 0, "estop_b": 1},
        outputs={},
        estop=SimpleNamespace(input="estop_a"),
    )
    return SimpleNamespace(
        machine=SimpleNamespace(name="m6_test"),
        io=io,
        axes=[],
        probe=None,
        positions=SimpleNamespace(tool_setter=None),
    )


def _assert_m6_handshake(hal):
    assert "loadrt timedelay names=sim_toolchange" in hal
    assert "addf sim_toolchange servo-thread" in hal
    assert "setp sim_toolchange.on-delay 0.1" in hal
    assert (
        "net linumert.io.tool-change iocontrol.0.tool-change => sim_toolchange.in"
        in hal
    )
    assert (
        "net linumert.io.tool-changed sim_toolchange.out => iocontrol.0.tool-changed"
        in hal
    )
    assert "iocontrol.0.tool-prepare => iocontrol.0.tool-prepared" in hal


def test_plant_m6_handshake_without_gui():
    hal = render_plant_hal(_machine(), [])
    _assert_m6_handshake(hal)
    assert "lrt-net.0.connected => estop_chain.in1" in hal
    assert "lrt-estop2.0.ok => estop_chain.in0" in hal
    assert "lrt-net.0.din-00 => lrt-estop2.0.ch-a" in hal
    assert "lrt-net.0.din-01 => lrt-estop2.0.ch-b" in hal
    assert "estop_latch.ok-out => iocontrol.0.emc-enable-in" in hal


def test_sim_m6_handshake_without_gui():
    hal = render_sim_hal(_machine(), [])
    _assert_m6_handshake(hal)
    assert "estop_latch.ok-out => iocontrol.0.emc-enable-in" in hal
