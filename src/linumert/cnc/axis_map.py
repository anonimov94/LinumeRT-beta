"""Jawne mapowanie jointów trivkins z INI i walidacja stanu NML.

SPDX-License-Identifier: GPL-2.0-or-later

Inne kinematyki wymagają osobnego modelu; nie zgadujemy mapowania z axis_mask.
NIEZWERYFIKOWANE NA SPRZĘCIE ani na LinuxCNC SIM.
"""

from dataclasses import dataclass
from typing import Any

from .model import AXIS_LETTERS


class AxisMapError(ValueError):
    """Brak jednoznacznej konfiguracji jointów: należy odmówić ruchu."""


def _letters(value: str) -> tuple[str, ...]:
    result = tuple("".join(value.split()).upper())
    if not result or any(letter not in AXIS_LETTERS for letter in result):
        raise AxisMapError("niepoprawne litery osi w konfiguracji")
    return result


@dataclass(frozen=True)
class AxisMap:
    joint_axes: tuple[str, ...]
    home_sequences: tuple[int | None, ...]
    kinematics_type: int

    @classmethod
    def from_ini(cls, ini: Any, module: Any) -> "AxisMap":
        def value(section, key, required=True):
            items = ini.findall(section, key)
            if len(items) > 1 or (required and not items):
                raise AxisMapError(f"brak lub wieloznaczne [{section}]{key}")
            return items[0].strip() if items else None

        try:
            count = int(value("KINS", "JOINTS"))
            if not 1 <= count <= len(AXIS_LETTERS):
                raise AxisMapError("liczba jointów poza zakresem")
            parts = value("KINS", "KINEMATICS").split()
            if not parts or parts[0] != "trivkins":
                raise AxisMapError("obsługiwane jest wyłącznie jawne mapowanie trivkins")
            options = {}
            for part in parts[1:]:
                key, sep, item = part.partition("=")
                if not sep or key not in {"coordinates", "kinstype"} or key in options:
                    raise AxisMapError("nieobsługiwane lub wieloznaczne parametry trivkins")
                options[key] = item
            # Bez coordinates trivkins używa XYZABCUVW, a nie kolejności TRAJ.
            coordinates = options.get("coordinates")
            axes = _letters(coordinates) if coordinates is not None else AXIS_LETTERS[:count]
            if len(axes) != count:
                raise AxisMapError("za mało współrzędnych trivkins dla jointów")
            traj = _letters(value("TRAJ", "COORDINATES"))
            if set(axes) != set(traj):
                raise AxisMapError("osie TRAJ nie odpowiadają jointom trivkins")
            kind = options.get("kinstype", "1").upper()
            if kind == "1":
                kin_type = module.KINEMATICS_IDENTITY
            elif kind in {"B", "BOTH"}:
                kin_type = module.KINEMATICS_BOTH
            else:
                raise AxisMapError("nieobsługiwany kinstype trivkins")
            if len(set(axes)) < count and kind not in {"B", "BOTH"}:
                raise AxisMapError("gantry wymaga trivkins kinstype=BOTH")
            sequences = []
            for joint, axis in enumerate(axes):
                section = f"JOINT_{joint}"
                expected = "ANGULAR" if axis in "ABC" else "LINEAR"
                if value(section, "TYPE").upper() != expected:
                    raise AxisMapError(f"typ jointa {joint} nie odpowiada osi {axis}")
                sequence = value(section, "HOME_SEQUENCE", required=False)
                sequences.append(int(sequence) if sequence is not None else None)
            return cls(axes, tuple(sequences), kin_type)
        except (TypeError, ValueError, AttributeError) as exc:
            raise AxisMapError(f"niepoprawna konfiguracja jointów: {exc}") from exc

    @property
    def axes(self) -> tuple[str, ...]:
        return tuple(letter for letter in AXIS_LETTERS if letter in self.joint_axes)

    def joints_for(self, axis: str) -> tuple[int, ...]:
        result = tuple(i for i, letter in enumerate(self.joint_axes) if letter == axis.upper())
        if not result:
            raise AxisMapError(f"nieznana oś {axis!r}")
        return result

    def axis_kind(self, axis: str) -> str:
        self.joints_for(axis)
        return "angular" if axis.upper() in "ABC" else "linear"

    def validate_state(self, stat: Any) -> None:
        count = len(self.joint_axes)
        mask = sum(1 << AXIS_LETTERS.index(letter) for letter in self.axes)
        if (getattr(stat, "joints", None) != count or stat.axis_mask != mask
                or getattr(stat, "kinematics_type", None) != self.kinematics_type):
            raise AxisMapError("stan NML jest niespójny z mapowaniem INI")
        for field in ("homed", "limit"):
            data = getattr(stat, field, ())
            if len(data) < count:
                raise AxisMapError(f"niepełne dane jointów: {field}")

    def home_target(self, axis: str | None, *, all_axes: bool = False) -> int:
        """Jedno polecenie dla jointa lub synchronizowanej grupy; -1 = HOME ALL.

        Grupę uruchamia joint z ujemną sekwencją. Nigdy nie bazujemy bramy
        niesynchronizowanymi poleceniami ani nie obejmujemy nieżądanych osi.
        """
        if axis is None:
            if any(seq is None for seq in self.home_sequences):
                raise AxisMapError("HOME ALL wymaga HOME_SEQUENCE dla każdego jointa")
            levels = sorted({abs(seq) for seq in self.home_sequences})
            if levels[0] not in (0, 1) or levels != list(range(levels[0], levels[-1] + 1)):
                raise AxisMapError("HOME_SEQUENCE zawiera lukę")
            for letter in self.axes:
                if len(self.joints_for(letter)) > 1:
                    self.home_target(letter, all_axes=True)
            return -1
        joints = self.joints_for(axis)
        sequences = [self.home_sequences[j] for j in joints]
        if len(joints) > 1:
            if (any(seq is None for seq in sequences)
                    or len({abs(seq) for seq in sequences}) != 1
                    or not any(seq < 0 for seq in sequences)):
                raise AxisMapError("bazowanie gantry wymaga wspólnej synchronizowanej sekwencji")
            target = next(j for j in joints if self.home_sequences[j] < 0)
        else:
            target = joints[0]
        sequence = self.home_sequences[target]
        if sequence is not None and any(
                seq is not None and seq < 0 and abs(seq) == abs(sequence)
                for seq in self.home_sequences):
            group = tuple(j for j, seq in enumerate(self.home_sequences)
                          if seq is not None and abs(seq) == abs(sequence))
            if group != joints and not all_axes:
                raise AxisMapError("grupa bazowania obejmuje inne osie; użyj HOME ALL")
        return target
