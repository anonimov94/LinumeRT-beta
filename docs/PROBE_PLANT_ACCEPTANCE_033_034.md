# Odbiór dokładności sondowania LinuxCNC/Plant (033/034)

Status: **BLOCKED** do czasu pomiaru na działającym interpreterze LinuxCNC 2.9 z Plant.
Kryterium właściciela: `abs(zapisany_punkt_styku - idealna_geometria_Plant) < 0.001 mm`.
Dotychczas raportowany błąd: ok. 0.012 mm (FAIL). Nie stosować stałego offsetu,
nie obniżać progu i nie traktować poprawnego G10 L20 jako potwierdzenia dokładności.

## Fakty z kodu

- `src/linumert_plant/server.py`: jedna ramka sterowania → `machine.step_cycle`
  (domyślnie 4 podkroki) → odczyt `machine.inputs` → ramka odpowiedzi.
- `hal/lrt_net.comp`: w każdym cyklu servo najpierw odbiera najnowszą odpowiedź,
  potem wysyła komendę. Stan sondy pochodzi z `lrt-net.0.din-NN`.
- `src/linumert/machine/configgen.py`: `lrt-net.0.din-NN => motion.probe-input`.
- `probe_macro.py`: offset liczy z wartości `#5061..#5063` G38.2, a nie
  z pozycji maszyny po hamowaniu.

Przy posuwie 100 mm/min jeden cykl 1 ms odpowiada **0.001667 mm** przemieszczenia.
Opóźnienie ok. 7 cykli dawałoby ~0.0117 mm, ale to **hipoteza**, a nie dowód.
Podkroki dynamiki Plant nie zmieniają częstotliwości odczytu sygnału przez HAL.

## Wymagane dane dla każdej próby

Zarejestrować: numer cyklu/ramki LRT-NET, `reply-age`, `missed`,
`plant-late`, `plant-jitter-us`, `motion.probe-input`,
`joint.2.motor-pos-cmd`, `joint.2.motor-pos-fb`, `lrt-net.0.axis.2.pos-fb`,
`#5063` i `#<_z>` bezpośrednio po G38.2, geometryczny Z powierzchni Plant,
aktywny WCS i G43. Nie zakładać, że Z jest jointem 2 dla wszystkich konfiguracji;
ustalić indeks ze `[TRAJ] COORDINATES`.

Wykonać po ≥10 prób na posuwach 25, 50, 100 i 200 mm/min, na tej samej geometrii,
przy domyślnym `cycle_ns=1000000`. Oddzielnie porównać dokładnie tę samą
geometrię z `substeps=4` i `substeps=8`.

Porównać nachylenie błędu względem posuwu: narastanie liniowe sugeruje
opóźnienie detekcji/transportu; zależność od parametrów napędu może wskazywać
na uchyb nadążania; stała różnica może oznaczać błąd geometrii / długości narzędzia.
Dopiero potem poprawiać właściwą warstwę.

## Kryteria zaliczenia

1. 100% prób z wymaganym stykiem kończy się G38.2 z pozycją styku,
   a brak styku zgłasza błąd bez zmiany offsetu.
2. Błąd bezwzględny względem powierzchni Plant <0.001 mm dla każdej próby
   w zadanym zakresie prędkości; raportować także rozrzut.
3. Po T2/M6/G43 i T0/M6/G49 nie występuje zmiana interpretacji długości narzędzia.
4. Zanik połączenia z Plant i rozwarcie każdego kanału E-STOP niezależnie
   blokują ruch. Nie zastępować zabezpieczeń wymuszeniem `TRUE` w HAL.

Nie wykonywać odbioru na fizycznej obrabiarce bez oddzielnej procedury bezpieczeństwa.
