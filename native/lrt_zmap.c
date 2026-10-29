/* SPDX-License-Identifier: GPL-2.0-or-later
 * Model-Author: Claude */
#include "lrt_zmap.h"

#include <math.h>
#include <stddef.h>

#define EPS 1e-3

static double lower(const lrt_cutter *c, double r)
{
    const double R = c->radius;
    if (r > R)
        return INFINITY;
    switch (c->profile) {
    case LRT_PROFILE_BALL: {
        double t = R * R - r * r;
        return R - sqrt(t > 0.0 ? t : 0.0);
    }
    case LRT_PROFILE_BULL: {
        double d = r - (R - c->corner);
        double t;
        if (d < 0.0)
            d = 0.0;
        t = c->corner * c->corner - d * d;
        return c->corner - sqrt(t > 0.0 ? t : 0.0);
    }
    case LRT_PROFILE_CONE:
        return r / c->cone_tan;
    default:
        return 0.0;
    }
}

static double clip_bottom(double v, double bottom)
{
    return v < bottom ? bottom : v;
}

static int clamp_i(int v, int lo, int hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

/* Jedno stemplowanie. Dwa przebiegi na jednej mapie: najpierw czesci nietnace (okno `reach`,
 * test wysokosci przed liczeniem odleglosci), potem czesc tnaca (okno promienia ostrza).
 * Wynik jest taki sam jak w wersji komorka po komorce: kazda komorka jest czytana przed
 * wlasnym obnizeniem, a komorki sa niezalezne. */
static void stamp(const lrt_zmap *m, const lrt_cutter *c, const double *part_r,
                  const double *part_z, int nparts, const double p[3], double reach,
                  lrt_cut_result *res)
{
    const double x = p[0], y = p[1], z = p[2];
    const double R = c->radius;
    double removed = 0.0, zmin = 0.0;
    int touched = 0;
    int ix, iy, i;

    for (i = 0; i < nparts; i++)
        if (i == 0 || part_z[i] < zmin)
            zmin = part_z[i];
    /* skoro zadna komorka nie siega powyzej z + zmin + EPS, przebieg nie moze nic trafic */
    if (nparts > 0 && m->top_bound > z + zmin + EPS) {
        const int ix0 = clamp_i((int)((x - reach - m->x0) / m->cell), 0, m->nx);
        const int ix1 = clamp_i((int)((x + reach - m->x0) / m->cell) + 1, 0, m->nx);
        const int iy0 = clamp_i((int)((y - reach - m->y0) / m->cell), 0, m->ny);
        const int iy1 = clamp_i((int)((y + reach - m->y0) / m->cell) + 1, 0, m->ny);
        for (iy = iy0; iy < iy1; iy++) {
            const float *row = m->h + (size_t)iy * m->nx;
            const double dy = (m->y0 + (iy + 0.5) * m->cell) - y;
            for (ix = ix0; ix < ix1; ix++) {
                const double hv = (double)row[ix];
                for (i = 0; i < nparts; i++) {
                    if (hv > z + part_z[i] + EPS) {
                        const double dx = (m->x0 + (ix + 0.5) * m->cell) - x;
                        if (sqrt(dx * dx + dy * dy) <= part_r[i]) {
                            res->parts_mask |= (uint64_t)1 << i;
                            touched = 1;
                        }
                    }
                }
            }
        }
    }

    {
        const int ix0 = clamp_i((int)((x - R - m->x0) / m->cell), 0, m->nx);
        const int ix1 = clamp_i((int)((x + R - m->x0) / m->cell) + 1, 0, m->nx);
        const int iy0 = clamp_i((int)((y - R - m->y0) / m->cell), 0, m->ny);
        const int iy1 = clamp_i((int)((y + R - m->y0) / m->cell) + 1, 0, m->ny);
        const double r2max = R * R * (1.0 + 1e-9);
        for (iy = iy0; iy < iy1; iy++) {
            float *row = m->h + (size_t)iy * m->nx;
            const double dy = (m->y0 + (iy + 0.5) * m->cell) - y;
            for (ix = ix0; ix < ix1; ix++) {
                const double hv = (double)row[ix];
                double dx, r2, surface;
                if (hv <= z + EPS)
                    continue;  /* surface >= z, wiec nic do obnizenia */
                dx = (m->x0 + (ix + 0.5) * m->cell) - x;
                r2 = dx * dx + dy * dy;
                if (r2 > r2max)
                    continue;
                surface = z + lower(c, sqrt(r2));
                if (hv > surface + EPS) {
                    const double newh = (double)(float)surface;
                    removed += clip_bottom(hv, m->z_bottom) - clip_bottom(newh, m->z_bottom);
                    row[ix] = (float)surface;
                    touched = 1;
                }
            }
        }
    }
    res->removed += removed * m->cell * m->cell;
    if (touched && !res->has_contact) {
        res->has_contact = 1;
        res->contact[0] = x;
        res->contact[1] = y;
        res->contact[2] = z;
    }
}

int lrt_zmap_cut(const lrt_zmap *map, const lrt_cutter *cutter, const double *part_r,
                 const double *part_z, int nparts, const double p0[3], const double p1[3],
                 double step, double reach, lrt_cut_result *out)
{
    double dist, n_f;
    long n, i;

    if (!map || !cutter || !p0 || !p1 || !out || !map->h || map->nx <= 0 || map->ny <= 0
        || map->cell <= 0.0 || step <= 0.0 || nparts < 0 || nparts > LRT_ZMAP_MAX_PARTS
        || (nparts > 0 && (!part_r || !part_z)))
        return -1;
    if (cutter->profile == LRT_PROFILE_CONE && cutter->cone_tan <= 0.0)
        return -1;

    out->removed = 0.0;
    out->parts_mask = 0;
    out->has_contact = 0;
    out->contact[0] = out->contact[1] = out->contact[2] = 0.0;

    dist = sqrt((p1[0] - p0[0]) * (p1[0] - p0[0]) + (p1[1] - p0[1]) * (p1[1] - p0[1])
                + (p1[2] - p0[2]) * (p1[2] - p0[2]));
    n_f = ceil(dist / step);
    n = n_f < 1.0 ? 1 : (long)n_f;
    for (i = (dist == 0.0 ? 0 : 1); i <= n; i++) {
        const double t = (double)i / (double)n;
        const double p[3] = {p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t,
                             p0[2] + (p1[2] - p0[2]) * t};
        stamp(map, cutter, part_r, part_z, nparts, p, reach, out);
    }
    return 0;
}

double lrt_zmap_volume(const lrt_zmap *map, const float *h_override)
{
    const float *h;
    double sum = 0.0;
    size_t i, count;

    if (!map)
        return 0.0;
    h = h_override ? h_override : map->h;
    if (!h)
        return 0.0;
    count = (size_t)map->nx * (size_t)map->ny;
    for (i = 0; i < count; i++)
        sum += clip_bottom((double)h[i], map->z_bottom) - map->z_bottom;
    return sum * map->cell * map->cell;
}
