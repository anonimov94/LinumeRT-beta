"""Start i kontrakt NML bez sterowania sprzętem. SPDX-License-Identifier: GPL-2.0-or-later"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from linumert.cnc.axis_map import AxisMap
from linumert_headless.__main__ import _config, build_arg_parser
from linumert_headless.backends.linuxcnc import LinuxCNCBackend
from linumert_headless.errors import BackendUnavailable, Conflict


def test_ini_and_state_paths(tmp_path):
    ini = tmp_path / "machine.ini"
    ini.write_text("[DISPLAY]\nPROGRAM_PREFIX = nc\n[LINUMERT]\nTOOL_DB = tools.db\n")
    args = build_arg_parser().parse_args([
        "serve", "--backend", "linuxcnc", "-ini", str(ini),
        "--state-dir", str(tmp_path / "state"), "--root", str(tmp_path)])
    paths = _config(args).paths()
    assert paths.default_ini == ini
    assert paths.programs == tmp_path / "nc"
    assert paths.tools_db == tmp_path / "tools.db"
    assert paths.state == tmp_path / "state"


def test_missing_ini_is_rejected(tmp_path):
    args = build_arg_parser().parse_args(["serve", "--ini", str(tmp_path / "missing")])
    with pytest.raises(ValueError, match="INI"):
        _config(args)


def make_backend(result=1):
    command = Mock(spec=["state", "wait_complete", "mode", "jog", "teleop_enable", "mdi"])
    command.wait_complete.return_value = result
    module = SimpleNamespace(command=lambda: command, STATE_ESTOP=1, STATE_ESTOP_RESET=2,
                             RCS_ERROR=3, MODE_MANUAL=4, MODE_MDI=5, JOG_CONTINUOUS=6)
    reader = SimpleNamespace(read=lambda: SimpleNamespace(axis_names=("X", "Z")),
                             axis_mapping=lambda: AxisMap(("X", "Z"), (0, 1), 11))
    return LinuxCNCBackend(module=module, reader=reader), command


def test_estop_uses_state_api():
    backend, command = make_backend()
    backend.estop()
    command.state.assert_called_with(1)
    backend.estop_reset()
    command.state.assert_called_with(2)


@pytest.mark.parametrize("result,error", [(-1, BackendUnavailable), (3, Conflict)])
def test_failed_mode_change_does_not_send_mdi(result, error):
    backend, command = make_backend(result)
    with pytest.raises(error):
        backend.mdi("G0 X1")
    command.mdi.assert_not_called()


def test_xz_jog_uses_cartesian_z_index():
    backend, command = make_backend()
    backend.jog("Z", 1)
    command.teleop_enable.assert_called_once_with(1)
    command.jog.assert_called_once_with(6, False, 2, 1)


def test_generated_sim_has_remap_and_estop_source():
    from pathlib import Path

    from linumert.machine.configgen import render
    from linumert.machine.schema import load_machine

    root = Path(__file__).resolve().parents[1]
    machine = load_machine(root / "config/machines/mill_servo_table.yaml")
    files = render(machine, "sim")
    assert "o<lrt_m6> sub" in files["macros/lrt_m6.ngc"]
    assert "iocontrol.0.user-enable-out => estop_latch.ok-in" in files["linumert_sim.hal"]
