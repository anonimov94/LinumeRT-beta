"""Czytnik stanu LinuxCNC: ``linuxcnc.stat`` -> ``MachineSnapshot`` (tylko odczyt).

SPDX-License-Identifier: GPL-2.0-or-later
Model-Author: Claude

Modul ``linuxcnc`` jest importowany leniwie, przy pierwszym ``read()``; sam import tego
pliku (i calego pakietu ``linumert``) go nie wymaga. Modul i obiekty ``stat`` /
``error_channel`` mozna wstrzyknac, co pozwala testowac mapowanie bez LinuxCNC.

Mapowanie pochodzi z INI działającej instancji (stat.ini_filename), nigdy z kolejności
liter axis_mask. Obsługiwane jest trivkins; inne kinematyki wymagają osobnego modelu.
Odbiór gantry na LinuxCNC 2.9 SIM pozostaje otwarty. NIEZWERYFIKOWANE NA SPRZĘCIE.
"""

from __future__ import annotations

import importlib
import threading
import time
from collections.abc import Callable
from typing import Any

from .axis_map import AxisMap, AxisMapError
from .instance import cached_start_lookup, ini_changed_after_start
from .model import (
    AXIS_LETTERS,
    AxisSnapshot,
    InterpState,
    MachineSnapshot,
    Mode,
    TaskState,
)

_TASK_STATES = {
    "STATE_ESTOP": TaskState.ESTOP,
    "STATE_ESTOP_RESET": TaskState.ESTOP_RESET,
    "STATE_OFF": TaskState.OFF,
    "STATE_ON": TaskState.ON,
}
_MODES = {"MODE_MANUAL": Mode.MANUAL, "MODE_AUTO": Mode.AUTO, "MODE_MDI": Mode.MDI}
_INTERP_STATES = {
    "INTERP_IDLE": InterpState.IDLE,
    "INTERP_READING": InterpState.READING,
    "INTERP_PAUSED": InterpState.PAUSED,
    "INTERP_WAITING": InterpState.WAITING,
}
_WORK_OFFSETS = ("G54", "G55", "G56", "G57", "G58", "G59", "G59.1", "G59.2", "G59.3")
_MAX_ERRORS_PER_READ = 20


def _lookup(module: Any, names: dict[str, Any], value: Any, default: Any) -> Any:
    """Mapuje stala liczbowa LinuxCNC na enum po NAZWIE stalej, nie po liczbie."""
    for name, mapped in names.items():
        if getattr(module, name, object()) == value:
            return mapped
    return default


def _item(sequence: Any, index: int, default: Any) -> Any:
    try:
        return sequence[index]
    except (IndexError, KeyError, TypeError):
        return default


class LinuxCNCReader:
    def __init__(
        self,
        module: Any = None,
        stat: Any = None,
        error_channel: Any = None,
        clock: Callable[[], float] = time.monotonic,
        instance_started: Callable[[str], float | None] | None = None,
    ):
        self._module = module
        self._stat = stat
        self._error_channel = error_channel
        self._lock = threading.RLock()
        self._clock = clock
        self._axis_map: AxisMap | None = None
        self._ini_filename: str | None = None
        # Bez wstrzykniętego modułu (produkcja) INI musi być starsze niż proces LinuxCNC;
        # atrapa modułu w testach nie ma procesu do sprawdzenia (chyba że podamy hak).
        if instance_started is None and module is None:
            instance_started = cached_start_lookup()
        self._instance_started = instance_started

    def _linuxcnc(self) -> Any:
        if self._module is None:
            try:
                self._module = importlib.import_module("linuxcnc")
            except ImportError as error:
                raise RuntimeError(
                    "Modul linuxcnc jest niedostepny: uruchom w srodowisku LinuxCNC (RIP)"
                ) from error
        return self._module

    def read(self) -> MachineSnapshot:
        with self._lock:
            return self._read_locked()

    def _read_locked(self, drain_errors: bool = True) -> MachineSnapshot:
        module = self._linuxcnc()
        if self._stat is None:
            self._stat = module.stat()
        stat = self._stat
        stat.poll()
        mapping = self._mapping(stat, module)
        mask = int(stat.axis_mask)
        indices = [i for i in range(len(AXIS_LETTERS)) if mask & (1 << i)]
        names = [AXIS_LETTERS[i] for i in indices]
        axes = tuple(
            self._axis(stat, mapping.joints_for(name), index, name)
            for index, name in zip(indices, names, strict=True)
        )
        spindle = _item(getattr(stat, "spindle", ()), 0, {}) or {}
        index = int(getattr(stat, "g5x_index", 1))
        offset_name = _WORK_OFFSETS[min(max(index, 1), len(_WORK_OFFSETS)) - 1]
        return MachineSnapshot(
            timestamp=self._clock(),
            task_state=_lookup(module, _TASK_STATES, stat.task_state, TaskState.ESTOP),
            mode=_lookup(module, _MODES, stat.task_mode, Mode.MANUAL),
            interp_state=_lookup(module, _INTERP_STATES, stat.interp_state, InterpState.IDLE),
            axes=axes,
            current_line=int(getattr(stat, "current_line", 0)),
            program_file=str(getattr(stat, "file", "") or ""),
            feed_override=float(getattr(stat, "feedrate", 1.0)),
            rapid_override=float(getattr(stat, "rapidrate", 1.0)),
            spindle_override=float(spindle.get("override", 1.0)),
            spindle_speed=abs(float(spindle.get("speed", 0.0))),
            spindle_direction=int(spindle.get("direction", 0)),
            tool_number=int(getattr(stat, "tool_in_spindle", 0)),
            tool_offset=self._by_axis(getattr(stat, "tool_offset", ()), indices, names),
            work_offset_name=offset_name,
            work_offset=self._by_axis(getattr(stat, "g5x_offset", ()), indices, names),
            active_gcodes=self._codes(getattr(stat, "gcodes", ()), "G", 10),
            active_mcodes=self._codes(getattr(stat, "mcodes", ()), "M", 1),
            errors=self._drain_errors(module) if drain_errors else (),
        )

    def teleop_active(self) -> bool:
        """Czy ruch jest w trybie teleop (``stat.motion_mode``); nie ruszamy kanału błędów."""
        with self._lock:
            module = self._linuxcnc()
            if self._stat is None:
                self._stat = module.stat()
            self._stat.poll()
            return int(self._stat.motion_mode) == int(module.TRAJ_MODE_TELEOP)

    def axis_mapping(self) -> AxisMap:
        """Odświeża stan przed użyciem mapowania; nie zabiera błędów z kanału LinuxCNC."""
        with self._lock:
            self._read_locked(drain_errors=False)
            if self._axis_map is None:
                raise AxisMapError("brak mapowania jointów")
            return self._axis_map

    def _check_ini_fresh(self, filename: str) -> None:
        if self._instance_started is None:
            return
        start = self._instance_started(filename)
        if start is None:
            raise AxisMapError("nie można ustalić czasu startu instancji LinuxCNC dla tego INI")
        try:
            changed = ini_changed_after_start(filename, start)
        except OSError as exc:
            raise AxisMapError(f"nie można sprawdzić czasu zmiany INI: {exc}") from exc
        if changed:
            raise AxisMapError("INI zmieniono po starcie LinuxCNC; uruchom LinuxCNC ponownie")

    def _mapping(self, stat: Any, module: Any) -> AxisMap:
        filename = getattr(stat, "ini_filename", "")
        if not filename:
            raise AxisMapError("brak INI działającej instancji LinuxCNC")
        self._check_ini_fresh(filename)
        try:
            mapping = AxisMap.from_ini(module.ini(filename), module)
        except Exception as exc:
            raise AxisMapError(f"nie można odczytać mapowania z INI: {exc}") from exc
        if self._axis_map is not None and (
                filename != self._ini_filename or mapping != self._axis_map):
            raise AxisMapError("mapowanie INI zmieniło się; wymagany ponowny rozruch aplikacji")
        self._axis_map, self._ini_filename = mapping, filename
        self._axis_map.validate_state(stat)
        return self._axis_map

    @staticmethod
    def _axis(stat: Any, joints: tuple[int, ...], index: int, name: str) -> AxisSnapshot:
        limits = _item(getattr(stat, "axis", ()), index, {}) or {}
        return AxisSnapshot(
            name=name,
            position=float(_item(stat.actual_position, index, 0.0)),
            commanded=float(_item(stat.position, index, 0.0)),
            homed=all(bool(stat.homed[joint]) for joint in joints),
            soft_min=float(limits.get("min_position_limit", float("-inf"))),
            soft_max=float(limits.get("max_position_limit", float("inf"))),
            limit_hit=any(bool(stat.limit[joint]) for joint in joints),
        )

    @staticmethod
    def _by_axis(values: Any, indices: list[int], names: list[str]) -> dict[str, float]:
        return {name: float(_item(values, i, 0.0)) for i, name in zip(indices, names, strict=True)}

    @staticmethod
    def _codes(values: Any, prefix: str, divisor: int) -> tuple[str, ...]:
        """Zamienia liczby ze stat (G: 10*kod, M: kod) na napisy; pomija pozycje < 0 i 0."""
        result = []
        for position, value in enumerate(values):
            if position == 0 or value < 0:
                continue  # [0] to numer sekwencji, -1 oznacza brak kodu w grupie
            result.append(f"{prefix}{value / divisor:g}")
        return tuple(result)

    def _drain_errors(self, module: Any) -> tuple[str, ...]:
        if self._error_channel is None:
            factory = getattr(module, "error_channel", None)
            if factory is None:
                return ()
            self._error_channel = factory()
        messages = []
        for _ in range(_MAX_ERRORS_PER_READ):
            error = self._error_channel.poll()
            if not error:
                break
            messages.append(str(error[1]))
        return tuple(messages)
