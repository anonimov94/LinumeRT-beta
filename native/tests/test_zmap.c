/* SPDX-License-Identifier: GPL-2.0-or-later
 * Model-Author: Claude */
#include "../lrt_zmap.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static int failures;
#define CHECK(cond, msg)                                                                  \
    do {                                                                                  \
        if (!(cond)) {                                                                    \
            printf("FAIL %s:%d %s\n", __FILE__, __LINE__, msg);                           \
            failures++;                                                                   \
        }                                                                                 \
    } while (0)

static lrt_zmap make_map(float *h, int nx, int ny, float top)
{
    lrt_zmap m = {h, nx, ny, 0.0, 0.0, 1.0, -10.0, (double)top};
    for (int i = 0; i < nx * ny; i++)
        h[i] = top;
    return m;
}

int main(void)
{
    float h[20 * 20];
    lrt_zmap m = make_map(h, 20, 20, 0.0f);
    lrt_cutter flat = {LRT_PROFILE_FLAT, 2.0, 0.0, 0.0};
    lrt_cut_result r;
    const double a[3] = {10, 10, -3}, b[3] = {10, 10, -3};
    double part_r[1] = {5.0}, part_z[1] = {10.0};

    /* wcisniecie w miejscu: obnizenie okola ok. pi*R^2 do z=-3 */
    CHECK(lrt_zmap_cut(&m, &flat, NULL, NULL, 0, a, b, 0.5, 2.0, &r) == 0, "cut");
    CHECK(r.removed > 3.0 * 10.0 && r.removed < 3.0 * 16.0, "objetosc walca ~ pi R^2 h");
    CHECK(r.has_contact && r.contact[2] == -3.0, "kontakt");
    CHECK(fabs(lrt_zmap_volume(&m, NULL) - (20 * 20 * 10.0 - r.removed)) < 1e-6, "objetosc");

    /* powtorzenie nie usuwa nic wiecej */
    CHECK(lrt_zmap_cut(&m, &flat, NULL, NULL, 0, a, b, 0.5, 2.0, &r) == 0, "cut2");
    CHECK(r.removed == 0.0 && !r.has_contact, "idempotentnie");

    /* oprawka nad materialem zglasza kontakt (bit 0) */
    m = make_map(h, 20, 20, 0.0f);
    const double c[3] = {10, 10, -9};
    CHECK(lrt_zmap_cut(&m, &flat, part_r, part_z, 1, c, c, 0.5, 5.0, &r) == 0, "cut3");
    CHECK((r.parts_mask & 1u) == 0, "oprawka 10 mm nad wierzcholkiem (z=1) nie dotyka z=0");
    part_z[0] = 5.0;
    m = make_map(h, 20, 20, 0.0f);
    CHECK(lrt_zmap_cut(&m, &flat, part_r, part_z, 1, c, c, 0.5, 5.0, &r) == 0, "cut4");
    CHECK((r.parts_mask & 1u) == 1u, "oprawka 5 mm nad wierzcholkiem (z=-4) zahacza o z=0");

    /* bledne argumenty */
    CHECK(lrt_zmap_cut(&m, &flat, NULL, NULL, 0, a, b, 0.0, 2.0, &r) == -1, "krok 0");
    CHECK(lrt_zmap_cut(NULL, &flat, NULL, NULL, 0, a, b, 0.5, 2.0, &r) == -1, "brak mapy");
    lrt_cutter bad = {LRT_PROFILE_CONE, 2.0, 0.0, 0.0};
    CHECK(lrt_zmap_cut(&m, &bad, NULL, NULL, 0, a, b, 0.5, 2.0, &r) == -1, "stozek bez kata");

    /* przejazd poza mapa nic nie robi i nie wychodzi poza pamiec */
    const double far0[3] = {-100, -100, -3}, far1[3] = {-90, -100, -3};
    m = make_map(h, 20, 20, 0.0f);
    CHECK(lrt_zmap_cut(&m, &flat, NULL, NULL, 0, far0, far1, 0.5, 2.0, &r) == 0, "poza");
    CHECK(r.removed == 0.0, "poza mapa: brak usuniecia");

    if (failures)
        return 1;
    printf("OK: test_zmap\n");
    return 0;
}
