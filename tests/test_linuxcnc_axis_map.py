"""Regresje P0 na atrapie NML; nie są odbiorem SIM ani sprzętu.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_cnc_reader import fake_module

from linumert.cnc.linuxcnc_reader import LinuxCNCReader
from linumert_headless.backends.linuxcnc import LinuxCNCBackend
from linumert_headless.errors import SafetyRefused


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


def test_home_all_uses_linuxcnc_sequence_order():
    backend, command, _, _ = machine(sequences=(0, -1, -1, -1))
    backend.home(None)
    command.home.assert_called_once_with(-1)


@pytest.mark.parametrize("sequences", [(0, -1, -1, None), (0, -2, -2, 3)])
def test_home_all_missing_or_gapped_sequence_refuses(sequences):
    backend, command, _, _ = machine(sequences=sequences)
    with pytest.raises(SafetyRefused):
        backend.home(None)
    assert command.mock_calls == []


def test_mixed_sign_gantry_uses_negative_joint():
    backend, command, _, _ = machine(sequences=(0, 1, -1, 2))
    backend.home("Y")
    command.home.assert_called_once_with(2)


@pytest.mark.parametrize("action", [lambda b: b.estop(), lambda b: b.stop(),
                                     lambda b: b.jog_stop(None), lambda b: b.jog_stop("Y"),
                                     lambda b: b.jog("Y", 0)])
def test_stop_remains_available_with_invalid_mapping(action):
    backend, command, _, stat = machine(ini_filename="")
    action(backend)
    assert command.state.called or command.abort.called


def test_state_is_revalidated_after_successful_read():
    backend, command, _, stat = machine()
    backend.snapshot()
    stat.joints = 3
    with pytest.raises(SafetyRefused):
        backend.home("Z")
    assert command.mock_calls == []


def test_reader_reloads_on_instance_ini_change():
    backend, command, values, stat = machine()
    backend.snapshot()
    stat.ini_filename = "/test/changed.ini"
    values["KINS", "KINEMATICS"] = "unknownkins"
    with pytest.raises(SafetyRefused):
        backend.home("Z")
    assert command.mock_calls == []


def test_rotary_axis_flags_use_joint_order():
    backend, _, _, _ = machine("CBAXYZ", (0, 1, 2, 3, 4, 5),
                               homed=(0, 1, 1, 1, 1, 1), limit=(1, 0, 0, 0, 0, 0))
    snap = backend.snapshot()
    assert not snap.axis("C").homed and snap.axis("C").limit_hit
    assert snap.axis("X").homed and not snap.axis("X").limit_hit
    mapping = backend.reader.axis_mapping()
    assert mapping.axis_kind("C") == "angular"
    assert mapping.axis_kind("X") == "linear"


def test_default_trivkins_coordinates_are_not_derived_from_traj():
    backend, command, values, stat = machine("XZ", (0, 1))
    values["KINS", "KINEMATICS"] = "trivkins kinstype=BOTH"
    with pytest.raises(SafetyRefused):
        backend.home("Z")
    assert command.mock_calls == []


def test_mode_failure_does_not_start_homing():
    backend, command, _, _ = machine()
    command.wait_complete.return_value = -1
    from linumert_headless.errors import BackendUnavailable

    with pytest.raises(BackendUnavailable):
        backend.home("Z")
    command.home.assert_not_called()


def test_changed_mapping_in_same_ini_refuses_until_restart():
    backend, command, values, stat = machine()
    backend.snapshot()
    values["KINS", "KINEMATICS"] = "trivkins coordinates=XYZY kinstype=BOTH"
    with pytest.raises(SafetyRefused, match="rozruch"):
        backend.home("Z")
    assert command.mock_calls == []


def test_duplicate_ini_mapping_key_refuses():
    backend, command, _, _ = machine()
    backend.reader._module.ini = lambda path: SimpleNamespace(findall=lambda *args: ["3", "4"])
    with pytest.raises(SafetyRefused):
        backend.home("Z")
    assert command.mock_calls == []


def test_positive_member_of_cross_axis_sync_group_refuses_axis_home():
    backend, command, _, _ = machine("XYZ", (0, 1, -1))
    with pytest.raises(SafetyRefused, match="inne osie"):
        backend.home("Y")
    assert command.mock_calls == []
