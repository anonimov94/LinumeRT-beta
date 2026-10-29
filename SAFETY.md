# OSTRZEŻENIE O BEZPIECZEŃSTWIE I WYŁĄCZENIE ODPOWIEDZIALNOŚCI / SAFETY NOTICE AND DISCLAIMER

SPDX-License-Identifier: GPL-2.0-or-later

## PL

**linumeRT headless (beta) jest oprogramowaniem eksperymentalnym, a nie funkcją bezpieczeństwa.**

1. **Oprogramowanie nie może być jedynym elementem zapewniającym bezpieczeństwo.** Sterowanie
   obrabiarką CNC może spowodować śmierć, poważne obrażenia ciała, pożar oraz zniszczenie maszyny,
   narzędzi, obrabianego materiału i mienia. Maszyna musi mieć sprzętowy obwód E-STOP (i, gdzie to
   potrzebne, STO, osłony, wyłączniki krańcowe, blokady drzwi), działający niezależnie od komputera,
   systemu operacyjnego i tego programu. E-STOP „w oprogramowaniu”, deadman jogu, limity, role,
   symulacja, wykrywanie kolizji i podgląd są pomocnicze i **mogą zawieść**.
2. **Brak weryfikacji na sprzęcie.** Cały kod, w szczególności generatory konfiguracji HAL/INI,
   obsługa EtherCAT, RS485, ATC, sondy i kinematyk, był sprawdzany wyłącznie na atrapach i w
   wirtualnej obrabiarce (Plant). Wszystko dotyczące prawdziwego sprzętu jest
   **NIEZWERYFIKOWANE NA SPRZĘCIE**. Wygenerowaną konfigurację sprawdź niezależnie przed pierwszym
   ruchem (bez narzędzia, bez materiału, z ręką przy fizycznym E-STOP).
3. **Brak gwarancji, brak odpowiedzialności.** Oprogramowanie jest udostępniane „TAK JAK JEST”,
   bez jakiejkolwiek gwarancji (zob. GPL-2.0, §11–12 w pliku `LICENSE`). W maksymalnym zakresie
   dozwolonym przez prawo autorzy i współtwórcy **nie ponoszą odpowiedzialności** za uszkodzenie
   sprzętu, utratę danych, szkody majątkowe, obrażenia ciała ani śmierć wynikające z użycia,
   błędnego użycia lub niemożności użycia tego oprogramowania, także gdy poinformowano ich o
   możliwości takich szkód.
4. **Odpowiedzialność użytkownika.** Używasz oprogramowania na własne ryzyko. Odpowiadasz za
   ocenę ryzyka, zgodność maszyny z obowiązującymi przepisami i normami (np. dyrektywa
   maszynowa, PN-EN ISO 13849, IEC 60204-1), przeszkolenie operatorów i nadzór nad pracą maszyny.
5. Dla wtyczek firm trzecich obowiązują te same zasady; wtyczka to kod wykonywany w procesie
   aplikacji — instaluj wyłącznie zaufane.

## EN

**linumeRT headless (beta) is experimental software and is not a safety function.**

1. **Software must never be the only safety measure.** Controlling a CNC machine can cause death,
   serious injury, fire, and damage to the machine, tooling, workpiece and property. The machine
   must have a hardware E-STOP circuit (and, where required, STO, guards, limit switches, door
   interlocks) that works independently of the computer, the operating system and this program.
   Software E-STOP, jog deadman, limits, roles, simulation, collision detection and previews are
   auxiliary and **can fail**.
2. **Not verified on hardware.** All code, in particular HAL/INI generators and EtherCAT, RS485,
   ATC, probing and kinematics support, was tested only against fakes and the virtual machine
   (Plant). Anything involving real hardware is **UNVERIFIED ON HARDWARE**. Independently verify
   any generated configuration before the first motion (no tool, no material, hand on the
   physical E-STOP).
3. **No warranty, no liability.** The software is provided "AS IS" without warranty of any kind
   (see GPL-2.0, sections 11–12 in `LICENSE`). To the maximum extent permitted by law the authors
   and contributors are **not liable** for damage to equipment, data loss, property damage,
   personal injury or death arising from the use, misuse or inability to use this software, even
   if advised of the possibility of such damage.
4. **User responsibility.** You use the software at your own risk and are responsible for risk
   assessment, compliance of your machine with applicable laws and standards, operator training
   and supervision.
5. Third-party plugins are subject to the same terms; a plugin is code executed inside the
   application process — install trusted plugins only.
