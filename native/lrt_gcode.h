/* linumeRT - interpreter podzbioru G-code -> lista ruchow (C11, tylko libc/libm).
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Model-Author: Claude
 *
 * Odpowiednik linumert_sim/path.py::SubsetInterpreter (wersja Python zostaje wzorcem
 * i sciezka zapasowa; test parytetu pilnuje zgodnosci). Wejscie: tekst UTF-8.
 */
#ifndef LRT_GCODE_H
#define LRT_GCODE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum { LRT_KIND_RAPID = 0, LRT_KIND_FEED = 1, LRT_KIND_ARC = 2 };

typedef struct {
    int64_t n;                 /* liczba ruchow */
    float *start, *end;        /* n * 3 */
    int32_t *line, *tool;
    int8_t *kind;
    float *feed, *spindle;
    char *notes;               /* uwagi rozdzielone '\n', zakonczone NUL */
    int64_t notes_len;
    int error;                 /* 0 = ok; inaczej error_msg opisuje blad (UTF-8) */
    char error_msg[320];
} lrt_gcode_moves;

/* Zwraca wynik (zawsze nie-NULL poza brakiem pamieci); zwolnic lrt_gcode_free. */
lrt_gcode_moves *lrt_gcode_parse(const char *text, int64_t len, const double start[3],
                                 int metric);
void lrt_gcode_free(lrt_gcode_moves *r);

#ifdef __cplusplus
}
#endif
#endif
