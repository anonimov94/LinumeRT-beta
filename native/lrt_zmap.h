/* linumeRT - jadro usuwania materialu 2.5D (mapa wysokosci), C11, tylko libc/libm.
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Model-Author: Claude
 *
 * Ta sama matematyka co linumert_sim/zmap.py (numpy); wersja numpy zostaje jako wzorzec i
 * zapasowa sciezka, a test parytetu pilnuje zgodnosci wynikow.
 */
#ifndef LRT_ZMAP_H
#define LRT_ZMAP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LRT_ZMAP_MAX_PARTS 64

/* Rodzaje profilu czesci tnacej (Cutter.lower). */
enum { LRT_PROFILE_FLAT = 0, LRT_PROFILE_BALL = 1, LRT_PROFILE_BULL = 2, LRT_PROFILE_CONE = 3 };

typedef struct {
    double removed;       /* [mm^3] */
    uint64_t parts_mask;  /* bit i = czesc nietnaca i w materiale */
    int has_contact;      /* 1 = contact_* ustawione */
    double contact[3];    /* pierwsza probka z kontaktem */
} lrt_cut_result;

typedef struct {
    float *h;             /* ny * nx, wiersz = y */
    int nx, ny;
    double x0, y0, cell;
    double z_bottom;
    double top_bound;     /* h[i] <= top_bound zawsze (np. z_top przygotowki) */
} lrt_zmap;

typedef struct {
    int profile;
    double radius, corner, cone_tan;
} lrt_cutter;

/* Przejazd wierzcholka p0 -> p1 probkowany krokiem <= step; parts: promien i dolna krawedz
 * (wzgledem wierzcholka) czesci nietnacych. Zwraca 0 albo -1 przy blednych argumentach. */
int lrt_zmap_cut(const lrt_zmap *map, const lrt_cutter *cutter, const double *part_r,
                 const double *part_z, int nparts, const double p0[3], const double p1[3],
                 double step, double reach, lrt_cut_result *out);

/* Objetosc materialu nad z_bottom [mm^3] (double, bez utraty precyzji float32). */
double lrt_zmap_volume(const lrt_zmap *map, const float *h_override);

#ifdef __cplusplus
}
#endif
#endif
