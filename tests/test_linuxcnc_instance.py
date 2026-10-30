"""Wykrywanie zmiany INI po starcie instancji LinuxCNC (R-1); atrapy, nie SIM.

SPDX-License-Identifier: GPL-2.0-or-later
"""

import pytest
from test_cnc_reader import fake_module

from linumert.cnc.axis_map import AxisMapError
from linumert.cnc.instance import ini_changed_after_start, process_start_time
from linumert.cnc.linuxcnc_reader import LinuxCNCReader


def fake_proc(tmp_path, ini, *, ticks=500, btime=1000, name="milltask"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "stat").write_text(f"cpu 1 2 3\nbtime {btime}\n")
    pid = tmp_path / "123"
    pid.mkdir()
    (pid / "cmdline").write_bytes(f"{name}\0-ini\0{ini}\0".encode())
    # pole 22 (starttime) po nawiasie z nazwą procesu zawierającą spację
    fields = ["S"] + ["0"] * 18 + [str(ticks)]
    (pid / "stat").write_text(f"123 ({name} x) " + " ".join(fields) + " 0 0\n")
    return tmp_path


def test_process_start_time_from_proc(tmp_path):
    ini = tmp_path / "m.ini"
    ini.write_text("")
    proc = fake_proc(tmp_path / "proc", str(ini))
    start = process_start_time(str(ini), proc_root=proc, clock_ticks=100)
    assert start == pytest.approx(1000 + 500 / 100)


def test_process_start_time_unknown_when_no_process(tmp_path):
    ini = tmp_path / "m.ini"
    ini.write_text("")
    proc = fake_proc(tmp_path / "proc", "/inne/maszyny.ini")
    assert process_start_time(str(ini), proc_root=proc, clock_ticks=100) is None


def test_ini_newer_than_start_is_detected(tmp_path):
    ini = tmp_path / "m.ini"
    ini.write_text("")
    mtime = ini.stat().st_mtime
    assert ini_changed_after_start(str(ini), start=mtime - 60)
    assert not ini_changed_after_start(str(ini), start=mtime + 60)


def reader(tmp_path, start):
    ini = tmp_path / "m.ini"
    ini.write_text("")
    module = fake_module(ini_filename=str(ini))
    return LinuxCNCReader(module=module, instance_started=lambda path: start), ini


def test_reader_refuses_ini_edited_after_instance_start(tmp_path):
    rd, ini = reader(tmp_path, start=None)
    rd._instance_started = lambda path: ini.stat().st_mtime - 30
    with pytest.raises(AxisMapError, match="po starcie"):
        rd.read()


def test_reader_refuses_when_start_time_unknown(tmp_path):
    rd, _ = reader(tmp_path, start=None)
    with pytest.raises(AxisMapError, match="czasu startu"):
        rd.read()


def test_reader_accepts_ini_older_than_instance(tmp_path):
    rd, ini = reader(tmp_path, start=None)
    rd._instance_started = lambda path: ini.stat().st_mtime + 30
    assert rd.read().axes


def test_reader_rechecks_ini_on_every_read(tmp_path):
    rd, ini = reader(tmp_path, start=None)
    rd._instance_started = lambda path: ini.stat().st_mtime + 30
    rd.read()
    rd._instance_started = lambda path: ini.stat().st_mtime - 30
    with pytest.raises(AxisMapError, match="po starcie"):
        rd.read()


def test_injected_module_without_hook_skips_check():
    # istniejące testy z atrapą modułu nie mają procesu LinuxCNC do sprawdzenia
    assert LinuxCNCReader(module=fake_module()).read().axes
