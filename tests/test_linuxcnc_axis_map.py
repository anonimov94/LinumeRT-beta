"""Regresje P0 na atrapie NML; nie są odbiorem SIM ani sprzętu.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from linumert.cnc.linuxcnc_reader import LinuxCNCReader
from linumert_headless.backends.linuxcnc import LinuxCNCBackend
from linumert_headless.errors import SafetyRefused
from test_cnc_reader import fake_module


def machine(coords="XYYZ", sequences=(0, -1, -1, 2), **state):
    letters = "XYZABCUVW"
    values = {
        ("KINS", "JOINTS"): str(len(coords)),
        ("KINS", "KINEMATICS"): f"trivkins coordinates={coords} kinstype=BOTH",
        ("TRAJ", "COORDINATES"): "".join(dict.fromkeys(coords)),
    }
    for j, (letter, sequence) in enumerate(zip(coords, sequences, strict=True)):
        values[f"JOINT_{j}", "TYPE"] = "ANGULAR" if letter in "ABC" else "LINEAR"
        if sequence is not None:
            values[f"JOINT_{j}", "HOME_SEQUENCE"] = str(sequence)
    defaults = dict(joints=len(coords), axis_mask=sum(1 << letters.index(x) for x in set(coords)),
                    ini_filename="/test/machine.ini", kinematics_type=12,
                    homed=(1,) * len(coords), limit=(0,) * len(coords))
    defaults.update(state)
    module = fake_module(**defaults)
    module.KINEMATICS_BOTH = 12
    module.KINEMATICS_IDENTITY = 11
    module.ini = lambda path: SimpleNamespace(
        find=lambda section, key: values.get((section, key)),
        findall=lambda section, key: ([values[section, key]] if (section, key) in values else []))
    command = Mock()
    command.wait_complete.return_value = 1
    module.command = lambda: command
    module.RCS_ERROR = 3
    module.JOG_CONTINUOUS = 6
    module.JOG_INCREMENT = 7
    reader = LinuxCNCReader(module=module)
    return LinuxCNCBackend(module=module, reader=reader), command, values, module.stat()


def test_home_z_addresses_joint_three():
    backend, command, _, _ = machine()
    backend.home("Z")
    command.home.assert_called_once_with(3)


def test_gantry_flags_aggregate_both_y_joints():
    backend, _, _, _ = machine(homed=(1, 1, 0, 1), limit=(0, 0, 1, 0))
    snap = backend.snapshot()
    assert not snap.axis("Y").homed
    assert snap.axis("Y").limit_hit
    assert snap.axis("Z").homed
    assert not snap.axis("Z").limit_hit


def test_gantry_home_sends_one_synchronized_group_command():
    backend, command, _, _ = machine()
    backend.home("Y")
    command.home.assert_called_once_with(1)
    command.teleop_enable.assert_called_once_with(0)


@pytest.mark.parametrize("coords", ["XZYABC", "CBAXYZ", "XZ", "XYZ"])
def test_joint_order_is_independent_of_axis_mask(coords):
    backend, command, _, _ = machine(coords, tuple(range(len(coords))))
    for index, letter in enumerate(coords):
        command.reset_mock()
        backend.home(letter)
        command.home.assert_called_once_with(index)


@pytest.mark.parametrize("field,value", [
    (("KINS", "KINEMATICS"), "corexykins"),
    (("KINS", "KINEMATICS"), "trivkins coordinates=XYZ"),
    (("KINS", "JOINTS"), "3"),
    (("TRAJ", "COORDINATES"), "XYZA"),
    (("JOINT_3", "TYPE"), "ANGULAR"),
])
def test_invalid_configuration_refuses_before_command(field, value):
    backend, command, values, _ = machine()
    values[field] = value
    with pytest.raises(SafetyRefused):
        backend.home("Z")
    assert command.mock_calls == []


@pytest.mark.parametrize("field,value", [("joints", 3), ("axis_mask", 3),
                                          ("homed", (1, 1)), ("limit", (0,)),
                                          ("kinematics_type", 999), ("ini_filename", "")])
def test_invalid_state_refuses_before_command(field, value):
    backend, command, _, stat = machine()
    setattr(stat, field, value)
    with pytest.raises(SafetyRefused):
        backend.home("Z")
    assert command.mock_calls == []


@pytest.mark.parametrize("sequences", [(0, 1, 1, 2), (0, -1, -2, 3), (0, None, None, 1)])
def test_unsynchronized_gantry_refuses(sequences):
    backend, command, _, _ = machine(sequences=sequences)
    with pytest.raises(SafetyRefused):
        backend.home("Y")
    assert command.mock_calls == []


def test_cross_axis_synchronized_group_refuses_axis_home():
    backend, command, _, _ = machine(sequences=(0, -1, -1, -1))
    with pytest.raises(SafetyRefused):
        backend.home("Y")
    assert command.mock_calls == []


def test_home_all_validates_configuration():
    backend, command, values, _ = machine()
    values["KINS", "KINEMATICS"] = "unknownkins"
    with pytest.raises(SafetyRefused):
        backend.home(None)
    assert command.mock_calls == []


def test_jog_z_keeps_cartesian_index():
    backend, command, _, _ = machine()
    backend.jog("Z", 1)
    command.jog.assert_called_once_with(6, False, 2, 1)


def test_invalid_jog_axis_has_no_mode_side_effects():
    backend, command, _, _ = machine()
    with pytest.raises(SafetyRefused):
        backend.jog("A", 1)
    assert command.mock_calls == []
