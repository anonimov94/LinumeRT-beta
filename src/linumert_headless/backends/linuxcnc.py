"""Backend LinuxCNC (`LinuxCNCBackend`).

SPDX-License-Identifier: GPL-2.0-or-later

Ten sam port ``MachinePort`` co atrapa, więc usługi, transporty i GUI nie wiedzą, z którym
backendem rozmawiają. Czytanie stanu idzie przez ``linumert.cnc.linuxcnc_reader`` (wspólny
model ``MachineSnapshot``), polecenia przez ``linuxcnc.command``.

Zasady bezpieczeństwa (CLAUDE.md §6):
- brak odblokowania E-STOP przez GUI: ``estop_reset`` wymaga jawnej zgody i roli serwisu,
- polecenia zatrzymujące są wysyłane bezwarunkowo,
- błędy z ``linuxcnc.error`` trafiają do migawki (``errors``) i do dziennika, nie do tracebacka.

Wymaga LinuxCNC 2.9 (RIP albo pakiet Debiana). NIEZWERYFIKOWANE NA SPRZĘCIE.
"""

from __future__ import annotations

import importlib
import time
from typing import Any

from linumert.cnc.axis_map import AxisMap, AxisMapError
from linumert.cnc.linuxcnc_reader import LinuxCNCReader
from linumert.cnc.model import MachineSnapshot, Mode

from ..errors import BackendUnavailable, Conflict, SafetyRefused

_MODE = {Mode.MANUAL: "MODE_MANUAL", Mode.AUTO: "MODE_AUTO", Mode.MDI: "MODE_MDI"}


class LinuxCNCBackend:
    """``MachinePort`` na ``linuxcnc.command``/``linuxcnc.stat``."""

    name = "linuxcnc"
    # Interpreter LinuxCNC wykonuje podprogramy o<...> call (makra M6, lrt_probe).
    capabilities = frozenset({"subroutines"})

    def __init__(self, module: Any = None, reader: LinuxCNCReader | None = None,
                 timeout: float = 2.0):
        self._module = module
        self._timeout = timeout
        self._command: Any = None
        # Czytnik wiąże INI działającej instancji z jej stanem NML.
        self.reader = reader or LinuxCNCReader(module=module)
        # Wiek migawki liczymy tym samym zegarem, którym czytnik ją stempluje.
        self._clock = getattr(self.reader, "_clock", time.monotonic)

    # ---- dostęp do modułu --------------------------------------------------
    def _lc(self) -> Any:
        if self._module is None:
            try:
                self._module = importlib.import_module("linuxcnc")
            except ImportError as exc:
                raise BackendUnavailable(
                    "brak modułu linuxcnc — uruchom aplikację na LinuxCNC 2.9 "
                    "albo użyj backendu 'fake'") from exc
        return self._module

    def _cmd(self) -> Any:
        if self._command is None:
            self._command = self._lc().command()
        return self._command

    def _wait(self) -> None:
        cmd = self._cmd()
        result = cmd.wait_complete(self._timeout)
        if result == -1:
            raise BackendUnavailable("LinuxCNC: timeout potwierdzenia polecenia")
        if result == self._lc().RCS_ERROR:
            raise Conflict("LinuxCNC odrzucił polecenie")

    # ---- stan --------------------------------------------------------------
    def tick(self) -> None:
        """Stan LinuxCNC płynie sam; odpytanie zdarza się w ``snapshot``."""

    def now(self) -> float:
        """Zegar czytaka — migawki LinuxCNC są stemplowane czasem systemowym."""
        return self._clock()

    def snapshot(self) -> MachineSnapshot:
        try:
            return self.reader.read()
        except AxisMapError as exc:
            raise SafetyRefused(str(exc)) from exc
        except Exception as exc:
            raise BackendUnavailable(f"odczyt stanu LinuxCNC nie powiódł się: {exc}") from exc

    # ---- polecenia ---------------------------------------------------------
    def estop(self) -> None:
        self._cmd().state(self._lc().STATE_ESTOP)

    def estop_reset(self) -> None:
        self._cmd().state(self._lc().STATE_ESTOP_RESET)
        self._wait()

    def power_on(self) -> None:
        self._cmd().state(self._lc().STATE_ON)
        self._wait()

    def power_off(self) -> None:
        self._cmd().state(self._lc().STATE_OFF)
        self._wait()

    def set_mode(self, mode: Mode) -> None:
        self._cmd().mode(getattr(self._lc(), _MODE[mode]))
        self._wait()

    def home(self, axis: str | None) -> None:
        try:
            target = self._mapping().home_target(axis)
        except AxisMapError as exc:
            raise SafetyRefused(str(exc)) from exc
        cmd = self._cmd()
        cmd.mode(self._lc().MODE_MANUAL)
        self._wait()
        cmd.teleop_enable(0)
        self._wait()
        cmd.home(target)

    def mdi(self, text: str) -> None:
        self._cmd().mode(self._lc().MODE_MDI)
        self._wait()
        self._cmd().mdi(text)

    def load_program(self, name: str, text: str) -> None:
        """LinuxCNC czyta program z pliku — backend przyjmuje ścieżkę w ``name``."""
        self._cmd().mode(self._lc().MODE_AUTO)
        self._wait()
        self._cmd().program_open(name)
        self._wait()
        _ = text  # treść jest już w pliku; parametr zachowuje kształt portu

    def run(self, from_line: int = 1) -> None:
        self._cmd().mode(self._lc().MODE_AUTO)
        self._wait()
        self._cmd().auto(self._lc().AUTO_RUN, from_line)

    def pause(self) -> None:
        self._cmd().auto(self._lc().AUTO_PAUSE)

    def resume(self) -> None:
        self._cmd().auto(self._lc().AUTO_RESUME)

    def stop(self) -> None:
        self._cmd().abort()
        self._wait()

    def set_override(self, feed: float | None = None, rapid: float | None = None,
                     spindle: float | None = None) -> None:
        cmd = self._cmd()
        if feed is not None:
            cmd.feedrate(feed)
        if rapid is not None:
            cmd.rapidrate(rapid)
        if spindle is not None:
            cmd.spindleoverride(spindle)

    def spindle(self, speed: float, direction: int) -> None:
        cmd = self._cmd()
        cmd.mode(self._lc().MODE_MDI)
        self._wait()
        code = {1: "M3", -1: "M4", 0: "M5"}[direction]
        cmd.mdi(f"S{speed:g} {code}")

    def jog(self, axis: str, speed: float) -> None:
        if speed == 0.0:
            self.jog_stop(axis)
            return
        index = self._axis(axis)
        cmd = self._cmd()
        cmd.mode(self._lc().MODE_MANUAL)
        self._wait()
        cmd.teleop_enable(1)
        self._wait()
        cmd.jog(self._lc().JOG_CONTINUOUS, False, index, speed)

    def jog_increment(self, axis: str, speed: float, distance: float) -> None:
        index = self._axis(axis)
        cmd = self._cmd()
        cmd.mode(self._lc().MODE_MANUAL)
        self._wait()
        cmd.teleop_enable(1)
        self._wait()
        cmd.jog(self._lc().JOG_INCREMENT, False, index, speed, distance)

    def jog_stop(self, axis: str | None) -> None:
        # Wysyłamy ABORT również w trybie joint i przy uszkodzonym INI/NML.
        # Nie uzależniamy zatrzymania od poprawności mapowania ani odczytu stanu.
        self._cmd().abort()

    def set_work_offset(self, name: str, values: dict[str, float]) -> None:
        raise Conflict("ustawienie offsetu w LinuxCNC idzie przez MDI (G10 L2); "
                       "użyj machine.mdi albo offset.set z generacją G10")

    # ---- pomocnicze --------------------------------------------------------
    def _mapping(self) -> AxisMap:
        try:
            return self.reader.axis_mapping()
        except AxisMapError as exc:
            raise SafetyRefused(str(exc)) from exc
        except Exception as exc:
            raise BackendUnavailable(f"brak aktualnego mapowania LinuxCNC: {exc}") from exc

    def _axis(self, axis: str) -> int:
        try:
            self._mapping().joints_for(axis)
        except AxisMapError as exc:
            raise SafetyRefused(str(exc)) from exc
        return "XYZABCUVW".index(axis.upper())

    def close(self) -> None:
        self._command = None


def available() -> bool:
    """Czy moduł LinuxCNC jest importowalny (bez uruchamiania maszyny)."""
    try:
        importlib.import_module("linuxcnc")
    except ImportError:
        return False
    return True


__all__ = ["LinuxCNCBackend", "available"]
