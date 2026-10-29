/* SPDX-License-Identifier: GPL-2.0-or-later
 * Model-Author: Claude
 *
 * Petla symulacji offline: wierny odpowiednik linumert_sim/engine.py::SimEngine.step oraz
 * petli probkowania z linumert_sim/offline.py::simulate. Kolejnosc zdarzen, klucze
 * wygaszania (_active/_warned) i okno mocy skrawania sa takie same jak w wersji Python.
 */
#include "lrt_sim.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MIN_RPM 10.0
#define MIN_REMOVED 0.01
#define LOAD_WINDOW 0.2
#define PI 3.14159265358979323846

typedef struct {
    int code, a, b;
} Key;

typedef struct {
    Key *k;
    size_t n, cap;
} KeySet;

typedef struct {
    double t, nose[3], rpm;
    int tool, motion, line;      /* motion: 0 rapid, 1 feed */
} Sample;

typedef struct {
    double t, removed, dt;
} WinItem;

struct lrt_sim {
    lrt_sim_config c;
    KeySet active, warned;
    Sample prev;
    int has_prev, idle;
    WinItem *win;
    size_t win_head, win_n, win_cap;
    lrt_sim_event *ev;
    size_t ev_n, ev_cap;
    double t, t_rapid, t_feed;
    int oom;
};

/* ------------------------------------------------------------ zbiory kluczy */

static int ks_has(const KeySet *s, int code, int a, int b)
{
    size_t i;
    for (i = 0; i < s->n; i++)
        if (s->k[i].code == code && s->k[i].a == a && s->k[i].b == b)
            return 1;
    return 0;
}

static int ks_add(KeySet *s, int code, int a, int b)
{
    if (s->n == s->cap) {
        size_t cap = s->cap ? s->cap * 2 : 16;
        Key *t = realloc(s->k, cap * sizeof *t);
        if (!t)
            return -1;
        s->k = t;
        s->cap = cap;
    }
    s->k[s->n].code = code;
    s->k[s->n].a = a;
    s->k[s->n].b = b;
    s->n++;
    return 0;
}

/* Usuwa klucze o danym kodzie; keep_a >= 0 oznacza: zostaw te z a == keep_a. */
static void ks_drop(KeySet *s, int code, int keep_a)
{
    size_t i, w = 0;
    for (i = 0; i < s->n; i++)
        if (!(s->k[i].code == code && (keep_a < 0 || s->k[i].a != keep_a)))
            s->k[w++] = s->k[i];
    s->n = w;
}

static void ks_discard(KeySet *s, int code, int a, int b)
{
    size_t i, w = 0;
    for (i = 0; i < s->n; i++)
        if (!(s->k[i].code == code && s->k[i].a == a && s->k[i].b == b))
            s->k[w++] = s->k[i];
    s->n = w;
}

/* ------------------------------------------------------------------ zdarzenia */

static lrt_sim_event *emit(lrt_sim *s, int code, int kind, const Sample *smp, const double pos[3])
{
    lrt_sim_event *e;
    if (s->ev_n == s->ev_cap) {
        size_t cap = s->ev_cap ? s->ev_cap * 2 : 64;
        lrt_sim_event *t = realloc(s->ev, cap * sizeof *t);
        if (!t) {
            s->oom = 1;
            return NULL;
        }
        s->ev = t;
        s->ev_cap = cap;
    }
    e = &s->ev[s->ev_n++];
    memset(e, 0, sizeof *e);
    e->code = code;
    e->kind = kind;
    e->line = smp->line;
    e->tool = smp->tool;
    e->id_a = e->id_b = -1;
    memcpy(e->pos, pos, 3 * sizeof(double));
    return e;
}

/* Jak SimEngine._once: zdarzenie tylko przy wejsciu w stan (klucz nieaktywny). */
static lrt_sim_event *once(lrt_sim *s, int code, int kind, int a, int b, const Sample *smp,
                           const double pos[3])
{
    if (ks_has(&s->active, code, a, b))
        return NULL;
    if (ks_add(&s->active, code, a, b)) {
        s->oom = 1;
        return NULL;
    }
    return emit(s, code, kind, smp, pos);
}

static const lrt_sim_tool *find_tool(const lrt_sim *s, int number)
{
    int i;
    for (i = 0; i < s->c.n_tools; i++)
        if (s->c.tools[i].number == number)
            return &s->c.tools[i];
    return NULL;
}

/* ------------------------------------------------------------- reguly (K-3xx) */

static void warnings(lrt_sim *s, const lrt_sim_tool *tool, const Sample *smp, const double tip[3])
{
    lrt_sim_event *e;
    if (tool->substitute && !ks_has(&s->warned, 320, smp->tool, 0)) {
        ks_add(&s->warned, 320, smp->tool, 0);
        emit(s, 320, 2, smp, tip);
    }
    if (tool->undercut && !ks_has(&s->warned, 322, smp->tool, 0)) {
        ks_add(&s->warned, 322, smp->tool, 0);
        emit(s, 322, 2, smp, tip);
    }
    if (tool->max_rpm > 0.0 && fabs(smp->rpm) > tool->max_rpm * 1.001) {
        e = once(s, 309, 1, smp->tool, 0, smp, tip);
        if (e) {
            e->i1 = (long)nearbyint(fabs(smp->rpm));
            e->i2 = (long)nearbyint(tool->max_rpm);
        }
    } else {
        ks_discard(&s->active, 309, smp->tool, 0);
    }
}

static void material_rules(lrt_sim *s, const lrt_sim_tool *tool, const Sample *smp,
                           const Sample *prev, const double pos[3])
{
    const double rpm = fabs(smp->rpm) >= fabs(prev->rpm) ? smp->rpm : prev->rpm;
    lrt_sim_event *e;
    if (smp->motion == 0 && prev->motion == 0) {
        e = once(s, 302, 0, 0, 0, smp, pos);
        if (e)
            e->id_a = -2;       /* para (narzedzie, przygotowka) */
    } else if (fabs(rpm) < MIN_RPM) {
        e = once(s, 301, 0, 0, 0, smp, pos);
        if (e)
            e->id_a = -2;
    } else if (!tool->tap && (rpm > 0 ? 1 : -1) != tool->hand) {
        e = once(s, 308, 0, 0, 0, smp, pos);
        if (e) {
            e->id_a = -2;
            snprintf(e->s1, sizeof e->s1, "%s", rpm < 0 ? "M4, lewe" : "M3, prawe");
        }
    }
}

static int cyl_hits(double cx, double cy, double r, double z0, double z1,
                    const lrt_sim_body *b)
{
    const double h = b->cylinder ? b->size[1] : b->size[2];
    const double b0 = b->pos[2] - h / 2, b1 = b->pos[2] + h / 2;
    const double hi = z1 < b1 ? z1 : b1, lo = z0 > b0 ? z0 : b0;
    if (hi - lo <= 0)
        return 0;
    if (b->cylinder)
        return hypot(cx - b->pos[0], cy - b->pos[1]) < r + b->size[0] / 2;
    {
        const double hx = b->size[0] / 2, hy = b->size[1] / 2;
        double nx = cx, ny = cy;
        if (nx < b->pos[0] - hx) nx = b->pos[0] - hx;
        if (nx > b->pos[0] + hx) nx = b->pos[0] + hx;
        if (ny < b->pos[1] - hy) ny = b->pos[1] - hy;
        if (ny > b->pos[1] + hy) ny = b->pos[1] + hy;
        return hypot(cx - nx, cy - ny) < r;
    }
}

typedef struct {
    int name_id;
    double r, z0, z1, cx, cy;
} Moving;

static void machine_rules(lrt_sim *s, const lrt_sim_tool *tool, const Sample *smp,
                          const double tip[3])
{
    const lrt_sim_config *c = &s->c;
    Moving *mv;
    size_t nm = 0;
    int i, j;
    KeySet hits = {0};

    mv = malloc(((size_t)(tool ? tool->n_cyl + 1 : 0) + (size_t)c->n_bodies + 1) * sizeof *mv);
    if (!mv) {
        s->oom = 1;
        return;
    }
    if (tool) {
        mv[nm++] = (Moving){c->tool_name_id, tool->radius, tip[2], tip[2] + tool->cut_top,
                            smp->nose[0], smp->nose[1]};
        for (i = 0; i < tool->n_cyl; i++) {
            const lrt_sim_cyl *p = &c->cyls[tool->cyl_off + i];
            mv[nm++] = (Moving){p->name_id, p->r, tip[2] + p->z0, tip[2] + p->z1,
                                smp->nose[0], smp->nose[1]};
        }
    }
    for (i = 0; i < c->n_bodies; i++) {
        const lrt_sim_body *b = &c->bodies[i];
        if (b->moving && b->cylinder) {
            const double h = b->size[1];
            const double zc = b->pos[2] + smp->nose[2];
            mv[nm++] = (Moving){b->name_id, b->size[0] / 2, zc - h / 2, zc + h / 2,
                                smp->nose[0] + b->pos[0], smp->nose[1] + b->pos[1]};
        }
    }
    for (i = 0; i < (int)nm; i++) {
        for (j = 0; j < c->n_bodies; j++) {
            const lrt_sim_body *b = &c->bodies[j];
            const lrt_sim_body *first = b;
            int code, k;
            lrt_sim_event *e;
            if (b->moving)
                continue;
            if (!cyl_hits(mv[i].cx, mv[i].cy, mv[i].r, mv[i].z0, mv[i].z1, b))
                continue;
            for (k = 0; k < c->n_bodies; k++)       /* next(b for b in bodies if name == fixed) */
                if (c->bodies[k].name_id == b->name_id) {
                    first = &c->bodies[k];
                    break;
                }
            if (first->toolsetter && mv[i].name_id == c->tool_name_id)
                continue;
            if (first->magazine && mv[i].name_id == c->tool_name_id)
                continue;
            code = first->fixture ? 304 : 305;
            if (ks_add(&hits, code, mv[i].name_id, b->name_id)) {
                s->oom = 1;
                break;
            }
            e = once(s, code, 0, mv[i].name_id, b->name_id, smp, tip);
            if (e) {
                e->id_a = mv[i].name_id;
                e->id_b = b->name_id;
            }
        }
    }
    /* _active -= {k for k in _active if k[0] in (304, 305) and k not in hits} */
    {
        size_t w = 0, q;
        for (q = 0; q < s->active.n; q++) {
            const Key k = s->active.k[q];
            if ((k.code == 304 || k.code == 305) && !ks_has(&hits, k.code, k.a, k.b))
                continue;
            s->active.k[w++] = k;
        }
        s->active.n = w;
    }
    free(hits.k);
    free(mv);
}

static double torque_limit(const lrt_sim_config *c, double rpm)
{
    const double omega = fabs(rpm) * 2 * PI / 60;
    int i;
    if (c->n_curve > 0) {
        if (omega <= c->curve_w[0])
            return c->curve_t[0];
        for (i = 0; i + 1 < c->n_curve; i++)
            if (omega <= c->curve_w[i + 1]) {
                const double w1 = c->curve_w[i + 1], w0 = c->curve_w[i];
                const double den = (w1 - w0) > 1e-9 ? (w1 - w0) : 1e-9;
                return c->curve_t[i] + (c->curve_t[i + 1] - c->curve_t[i]) * (omega - w0) / den;
            }
        return 0.0;
    }
    return c->spindle_power / (omega > 1.0 ? omega : 1.0);
}

static void loads(lrt_sim *s, const lrt_sim_tool *tool, const Sample *smp, const Sample *prev,
                  const double tip[3], double removed)
{
    const lrt_sim_config *c = &s->c;
    double dt = 0.0, span = 0.0, rsum = 0.0, mrr, power = 0.0, torque = 0.0, force = 0.0, tlim;
    int have_axis = 0;
    double axis_force[3] = {0, 0, 0};
    size_t i;
    lrt_sim_event *e;

    if (prev) {
        dt = smp->t - prev->t;
        if (dt < 0.0) dt = 0.0;
        if (dt > 1.0) dt = 1.0;
    }
    if (s->win_n == s->win_cap) {
        size_t cap = s->win_cap ? s->win_cap * 2 : 64;
        WinItem *t = malloc(cap * sizeof *t);
        if (!t) {
            s->oom = 1;
            return;
        }
        if (s->win_n)
            memcpy(t, s->win + s->win_head, s->win_n * sizeof *t);
        free(s->win);
        s->win = t;
        s->win_head = 0;
        s->win_cap = cap;
    } else if (s->win_head + s->win_n == s->win_cap) {
        memmove(s->win, s->win + s->win_head, s->win_n * sizeof *s->win);
        s->win_head = 0;
    }
    s->win[s->win_head + s->win_n++] = (WinItem){smp->t, removed, dt};
    while (s->win_n > 0 && smp->t - s->win[s->win_head].t > LOAD_WINDOW) {
        s->win_head++;
        s->win_n--;
    }
    for (i = 0; i < s->win_n; i++)
        span += s->win[s->win_head + i].dt;
    for (i = 0; i < s->win_n; i++)
        rsum += s->win[s->win_head + i].removed;
    mrr = span > 1e-3 ? rsum / span : 0.0;

    if (tool && fabs(smp->rpm) >= MIN_RPM && mrr > 0) {
        const double omega = fabs(smp->rpm) * 2 * PI / 60;
        const double rad = tool->radius * 1e-3;
        power = c->kc * mrr * 1e-3;
        torque = power / omega;
        force = torque / (rad > 1e-4 ? rad : 1e-4);
    }
    tlim = fabs(smp->rpm) != 0.0 ? torque_limit(c, smp->rpm) : 0.0;
    if (prev && force > 0) {
        const double feed = force * ((tool && tool->tap) ? 0.1 : 0.5);
        double d[3], n;
        int a;
        for (a = 0; a < 3; a++)
            d[a] = smp->nose[a] - prev->nose[a];
        n = sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
        if (n == 0.0)
            n = 1.0;
        for (a = 0; a < 3; a++)
            axis_force[a] = feed * fabs(d[a]) / n;
        have_axis = 1;
    }
    if (torque > 0 && torque > tlim && tlim > 0) {
        e = once(s, 306, 1, 0, 0, smp, tip);
        if (e) {
            e->id_a = -3;       /* para (wrzeciono, "") */
            snprintf(e->s1, sizeof e->s1, "%.2f", torque);
            snprintf(e->s2, sizeof e->s2, "%.2f", tlim);
        }
    } else if (torque == 0 || torque < 0.8 * tlim) {
        ks_discard(&s->active, 306, 0, 0);
    }
    if (!have_axis)
        ks_drop(&s->active, 307, -1);
    else {
        int a;
        for (a = 0; a < 3; a++) {
            const double limit = c->axis_force[a];
            if (axis_force[a] > limit) {
                e = once(s, 307, 1, a, 0, smp, tip);
                if (e) {
                    e->id_a = -4;   /* para (os X|Y|Z, "") */
                    e->i1 = a;
                    e->i2 = (long)nearbyint(axis_force[a]);
                    e->i3 = (long)nearbyint(limit);
                }
            } else if (axis_force[a] < 0.8 * limit) {
                ks_discard(&s->active, 307, a, 0);
            }
        }
    }
}

/* ------------------------------------------------------------------ krok */

static void do_cut(lrt_sim *s, const lrt_sim_tool *tool, const double p0[3], const double p1[3],
                   lrt_cut_result *out)
{
    const lrt_zmap *m = s->c.stock;
    double pr[LRT_ZMAP_MAX_PARTS], pz[LRT_ZMAP_MAX_PARTS], step, cell_step, rad_step;
    double lo_x, hi_x, lo_y, hi_y;
    int i;

    memset(out, 0, sizeof *out);
    lo_x = (p0[0] < p1[0] ? p0[0] : p1[0]) - tool->reach;
    hi_x = (p0[0] > p1[0] ? p0[0] : p1[0]) + tool->reach;
    lo_y = (p0[1] < p1[1] ? p0[1] : p1[1]) - tool->reach;
    hi_y = (p0[1] > p1[1] ? p0[1] : p1[1]) + tool->reach;
    if (hi_x < m->x0 || lo_x > m->x0 + m->nx * m->cell || hi_y < m->y0
        || lo_y > m->y0 + m->ny * m->cell)
        return;
    for (i = 0; i < tool->n_parts; i++) {
        pr[i] = s->c.parts[tool->part_off + i].r;
        pz[i] = s->c.parts[tool->part_off + i].z;
    }
    cell_step = m->cell * 0.5;
    rad_step = tool->radius * 0.5;
    step = cell_step < rad_step ? cell_step : rad_step;
    if (step < 0.02)
        step = 0.02;
    if (lrt_zmap_cut(m, &tool->cutter, pr, pz, tool->n_parts, p0, p1, step, tool->reach, out))
        s->oom = 1;
}

static int by_rank(const lrt_sim_part *a, const lrt_sim_part *b)
{
    return a->rank - b->rank;
}

static void step(lrt_sim *s, const Sample *smp)
{
    const lrt_sim_tool *tool = smp->tool ? find_tool(s, smp->tool) : NULL;
    const double gauge = tool ? tool->gauge : 0.0;
    const double tip[3] = {smp->nose[0], smp->nose[1], smp->nose[2] - gauge};
    Sample prevc = s->prev;
    int has_prev = s->has_prev;
    double removed = 0.0;

    ks_drop(&s->active, 309, smp->tool);
    s->prev = *smp;
    s->has_prev = 1;
    if (tool)
        warnings(s, tool, smp, tip);
    if (has_prev && (prevc.tool != smp->tool || smp->t - prevc.t > 1.0))
        has_prev = 0;

    if (s->c.stock && has_prev && tool) {
        lrt_cut_result res;
        double p0[3], pos[3];
        lrt_sim_part found[LRT_ZMAP_MAX_PARTS];
        int nf = 0, i, j;

        p0[0] = prevc.nose[0];
        p0[1] = prevc.nose[1];
        p0[2] = prevc.nose[2] - gauge;
        do_cut(s, tool, p0, tip, &res);
        removed = res.removed;
        memcpy(pos, res.has_contact ? res.contact : tip, sizeof pos);
        for (i = 0; i < tool->n_parts; i++)
            if (res.parts_mask >> i & 1) {
                const lrt_sim_part *p = &s->c.parts[tool->part_off + i];
                int dup = 0;
                for (j = 0; j < nf; j++)
                    dup |= found[j].name_id == p->name_id;
                if (!dup)
                    found[nf++] = *p;
            }
        for (i = 1; i < nf; i++) {          /* sorted(res.parts) po nazwach (rank) */
            lrt_sim_part v = found[i];
            for (j = i - 1; j >= 0 && by_rank(&found[j], &v) > 0; j--)
                found[j + 1] = found[j];
            found[j + 1] = v;
        }
        for (i = 0; i < nf; i++) {
            lrt_sim_event *e = once(s, 303, 0, found[i].name_id, 0, smp, pos);
            if (e)
                e->id_a = found[i].name_id, e->id_b = -5;    /* para (czesc, przygotowka) */
        }
        if (removed > MIN_REMOVED) {
            s->idle = 0;
            material_rules(s, tool, smp, &prevc, pos);
        } else {
            s->idle++;
            if (s->idle > 20) {
                ks_drop(&s->active, 301, -1);
                ks_drop(&s->active, 302, -1);
                ks_drop(&s->active, 308, -1);
            }
        }
        if (res.parts_mask == 0)
            ks_drop(&s->active, 303, -1);
    }
    machine_rules(s, tool, smp, tip);
    loads(s, tool, smp, has_prev ? &prevc : NULL, tip, removed);
}

/* ---------------------------------------------------------------- API */

lrt_sim *lrt_sim_new(const lrt_sim_config *cfg)
{
    lrt_sim *s;
    int i;
    if (!cfg || cfg->dt <= 0.0 || cfg->n < 0)
        return NULL;
    for (i = 0; i < cfg->n_tools; i++)
        if (cfg->tools[i].n_parts > LRT_ZMAP_MAX_PARTS || cfg->tools[i].n_parts < 0)
            return NULL;
    s = calloc(1, sizeof *s);
    if (!s)
        return NULL;
    s->c = *cfg;
    return s;
}

void lrt_sim_free(lrt_sim *s)
{
    if (!s)
        return;
    free(s->active.k);
    free(s->warned.k);
    free(s->win);
    free(s->ev);
    free(s);
}

int lrt_sim_begin(lrt_sim *s)
{
    const lrt_sim_config *c;
    Sample smp;
    float nose[3];
    const lrt_sim_tool *tool;
    int i;
    if (!s)
        return -1;
    c = &s->c;
    if (c->n <= 0)
        return 0;
    tool = find_tool(s, c->tool[0]);
    /* nose(ml.end[0], T): float32 + liczba Pythona = float32 (NumPy 2, NEP 50) */
    nose[0] = c->end[0] + (float)c->origin[0];
    nose[1] = c->end[1] + (float)c->origin[1];
    nose[2] = c->end[2] + (float)c->origin[2];
    nose[2] = nose[2] + (float)(tool ? tool->gauge : 0.0);
    smp.t = 0.0;
    for (i = 0; i < 3; i++)
        smp.nose[i] = (double)nose[i];
    smp.tool = c->tool[0];
    smp.rpm = (double)c->spindle[0];
    smp.motion = 0;
    smp.line = c->line[0];
    step(s, &smp);
    /* simulate() odrzuca zdarzenia pierwszej probki, ale jej stan (klucze) zostaje */
    s->ev_n = 0;
    return s->oom ? -1 : 0;
}

int lrt_sim_run(lrt_sim *s, int64_t i0, int64_t i1)
{
    const lrt_sim_config *c;
    int64_t i;
    if (!s)
        return -1;
    c = &s->c;
    if (i0 < 0)
        i0 = 0;
    if (i1 > c->n)
        i1 = c->n;
    for (i = i0; i < i1 && !s->oom; i++) {
        const int rapid = c->kind[i] == 0;
        const double feed = rapid ? c->rapid : (double)c->feed[i];
        double a[3], b[3], dist, seconds;
        const lrt_sim_tool *tool = find_tool(s, c->tool[i]);
        const double gauge = tool ? tool->gauge : 0.0;
        long steps, k;
        int d;

        for (d = 0; d < 3; d++) {
            a[d] = (double)c->start[i * 3 + d];
            b[d] = (double)c->end[i * 3 + d];
        }
        dist = c->dist[i];
        seconds = feed > 0 ? dist / feed * 60.0 : 0.0;
        if (rapid)
            s->t_rapid += seconds;
        else
            s->t_feed += seconds;
        if (i == 0) {
            s->t += seconds;
            continue;
        }
        steps = (long)ceil(seconds / c->dt);
        if (steps < 1)
            steps = 1;
        for (k = 1; k <= steps; k++) {
            const double r = (double)k / (double)steps;
            Sample smp;
            smp.t = s->t + seconds * (double)k / (double)steps;
            smp.nose[0] = (a[0] + (b[0] - a[0]) * r) + c->origin[0];
            smp.nose[1] = (a[1] + (b[1] - a[1]) * r) + c->origin[1];
            smp.nose[2] = ((a[2] + (b[2] - a[2]) * r) + c->origin[2]) + gauge;
            smp.tool = c->tool[i];
            smp.rpm = (double)c->spindle[i];
            smp.motion = rapid ? 0 : 1;
            smp.line = c->line[i];
            step(s, &smp);
        }
        s->t += seconds;
    }
    return s->oom ? -1 : 0;
}

double lrt_sim_time(const lrt_sim *s) { return s->t; }
double lrt_sim_time_rapid(const lrt_sim *s) { return s->t_rapid; }
double lrt_sim_time_feed(const lrt_sim *s) { return s->t_feed; }
int64_t lrt_sim_event_count(const lrt_sim *s) { return (int64_t)s->ev_n; }
const lrt_sim_event *lrt_sim_events(const lrt_sim *s) { return s->ev; }
