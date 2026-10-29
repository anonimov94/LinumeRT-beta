# SPDX-License-Identifier: GPL-2.0-or-later
"""Weryfikacja polaryzacji wejścia sondy generowanej konfiguracji Plant."""

from types import SimpleNamespace

import pytest

from linumert.machine.configgen import render_plant_hal


def _cfg(contact):
    return SimpleNamespace(
        machine=SimpleNamespace(name="probe_test"),
        axes=[],
        io=SimpleNamespace(inputs={"estop_a": 0, "estop_b": 15, "probe": 7},
                           outputs={}, estop=SimpleNamespace(input="estop_a")),
        probe=SimpleNamespace(input="probe", contact=contact),
        positions=SimpleNamespace(tool_setter=None),
    )


@pytest.mark.parametrize("contact", ["NC", "NO"])
def test_probe_polarity(contact):
    hal = render_plant_hal(_cfg(contact), [])
    if contact == "NC":
        assert "loadrt not names=probe_nc" in hal
        assert "addf probe_nc servo-thread" in hal
        assert "lrt-net.0.din-07 => probe_nc.in" in hal
        assert "probe_nc.out => motion.probe-input" in hal
        assert "lrt-net.0.din-07 => motion.probe-input" not in hal
    else:
        assert "probe_nc" not in hal
        assert "lrt-net.0.din-07 => motion.probe-input" in hal
    assert "lrt-net.0.connected => estop_chain.in1" in hal
    assert "lrt-net.0.din-00 => lrt-estop2.0.ch-a" in hal
    assert "lrt-net.0.din-15 => lrt-estop2.0.ch-b" in hal
