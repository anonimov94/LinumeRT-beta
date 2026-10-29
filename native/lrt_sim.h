/* linumeRT - petla symulacji offline (SimEngine.step + simulate) w C11.
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Model-Author: Claude
 *
 * Wierny odpowiednik linumert_sim/engine.py (reguly K-3xx) i petli z offline.py. Wersja Python
 * zostaje wzorcem i silnikiem trybu na zywo; test parytetu porownuje zdarzenia i wyniki.
 * Wskazniki w konfiguracji musza zyc tak dlugo, jak obiekt lrt_sim (trzyma je bez kopiowania).
 */
#ifndef LRT_SIM_H
#define LRT_SIM_H

#include <stdint.h>

#include "lrt_zmap.h"

#ifdef __cplusplus
extern "C" {
#endif

#define LRT_SIM_TEXT 40

/* Czesc nietnaca narzedzia dla mapy materialu: dolna krawedz wzgledem czubka. */
typedef struct {
    int name_id;
    int rank;        /* kolejnosc sortowania nazw (sorted(parts) w Pythonie) */
    double r, z;
} lrt_sim_part;

/* Walec narzedzia dla kolizji z bryla maszyny: z0..z1 wzgledem czubka. */
typedef struct {
    int name_id;
    double r, z0, z1;
} lrt_sim_cyl;

typedef struct {
    int number;
    double gauge, radius, cut_top, max_rpm;   /* max_rpm 0 = brak limitu */
    int tap, hand, undercut, substitute;
    double reach;                              /* max(promien, promienie czesci) */
    lrt_cutter cutter;                         /* profil czesci tnacej */
    int part_off, n_parts;                     /* w tablicy parts: czesci narzedzia + wrzeciona */
    int cyl_off, n_cyl;                        /* w tablicy cyls: czesci narzedzia */
} lrt_sim_tool;

typedef struct {
    int name_id;
    int cylinder;                              /* 1 = walec (os Z), 0 = prostopadloscian */
    int moving, fixture, toolsetter, magazine;
    double size[3], pos[3];
} lrt_sim_body;

typedef struct {
    double dt, rapid, origin[3];
    double kc;                                 /* opor wlasciwy skrawania [N/mm^2] */
    double spindle_power;                      /* [W] gdy brak krzywej */
    const double *curve_w, *curve_t;           /* krzywa momentu: [rad/s], [N*m] */
    int n_curve;
    double axis_force[3];                      /* granice sil napedow X Y Z [N] */
    int tool_name_id;                          /* nazwa "narzedzie" */

    const lrt_sim_tool *tools; int n_tools;
    const lrt_sim_part *parts;
    const lrt_sim_cyl *cyls;
    const lrt_sim_body *bodies; int n_bodies;
    const lrt_zmap *stock;                     /* NULL = bez materialu */

    int64_t n;                                 /* segmenty */
    const float *start, *end;                  /* n * 3 */
    const int32_t *line, *tool;
    const int8_t *kind;                        /* 0 = G0 */
    const float *feed, *spindle;
    const double *dist;                        /* dlugosc segmentu liczona przez Pythona (math.dist) */
} lrt_sim_config;

/* Kody zdarzen = numer K-3xx; rodzaj: 0 kolizja, 1 przeciazenie, 2 ostrzezenie. */
typedef struct {
    int code, kind, line, tool;
    double pos[3];
    int id_a, id_b;                            /* nazwy pary (indeksy tabeli nazw) albo -1 */
    long i1, i2, i3;
    char s1[LRT_SIM_TEXT], s2[LRT_SIM_TEXT];
} lrt_sim_event;

typedef struct lrt_sim lrt_sim;

lrt_sim *lrt_sim_new(const lrt_sim_config *cfg);
void lrt_sim_free(lrt_sim *s);
/* Pierwsza probka przed petla (jak w simulate); 0 albo -1. */
int lrt_sim_begin(lrt_sim *s);
/* Przetwarza segmenty [i0, i1); zwraca 0, -1 przy bledzie (np. brak pamieci). */
int lrt_sim_run(lrt_sim *s, int64_t i0, int64_t i1);
double lrt_sim_time(const lrt_sim *s);
double lrt_sim_time_rapid(const lrt_sim *s);
double lrt_sim_time_feed(const lrt_sim *s);
int64_t lrt_sim_event_count(const lrt_sim *s);
const lrt_sim_event *lrt_sim_events(const lrt_sim *s);

#ifdef __cplusplus
}
#endif
#endif
