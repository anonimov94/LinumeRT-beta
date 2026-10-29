/* SPDX-License-Identifier: GPL-2.0-or-later
 * Model-Author: Claude
 *
 * Interpreter podzbioru G-code. Wierny odpowiednik linumert_sim/path.py::SubsetInterpreter:
 * te same reguly komentarzy, O-slow, grup G/M, lukow i cykli wiercenia. Swiadome odstepstwa
 * (tylko skrajne przypadki): wielkie litery sa wielkimi tylko dla ASCII, a luk o wiecej niz
 * LRT_MAX_CHORDS ciecwach jest bledem zamiast proby alokacji gigabajtow.
 */
#include "lrt_gcode.h"

#include <math.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define INCH 25.4
#define CHORD_TOL 0.01
#define PECK_CLEARANCE (0.010 * INCH)
#define LRT_MAX_CHORDS 10000000L
#define TAU (2.0 * 3.14159265358979323846)

typedef struct {
    lrt_gcode_moves *r;
    size_t cap;
    size_t notes_cap;
    size_t *note_off;       /* poczatki uwag (do wykrywania duplikatow w jednej linii) */
    size_t note_count, note_off_cap, line_first_note;

    double pos[3];
    int motion;             /* -1 brak, inaczej kod G: 0 1 2 3 73 81 82 83 */
    int absolute, arc_absolute, plane;
    double scale, feed;
    int tool, pending_tool;
    double speed, direction;
    int retract;            /* 98 / 99 */
    int has_initial_z;
    double initial_z;
    int cyc_has[3];         /* Z R Q */
    double cyc_val[3];
    int ended;
} Interp;

/* ------------------------------------------------------------------ bufory */

static int fail(Interp *p, const char *fmt, ...)
{
    va_list ap;
    if (!p->r->error) {
        p->r->error = 1;
        va_start(ap, fmt);
        vsnprintf(p->r->error_msg, sizeof p->r->error_msg, fmt, ap);
        va_end(ap);
    }
    return -1;
}

static int reserve_moves(Interp *p, size_t need)
{
    lrt_gcode_moves *r = p->r;
    size_t cap;
    void *t;
    if (need <= p->cap)
        return 0;
    cap = p->cap ? p->cap * 2 : 1024;
    while (cap < need)
        cap *= 2;
#define GROW(field, type, mult)                                                           \
    do {                                                                                  \
        t = realloc(r->field, cap * (mult) * sizeof(type));                               \
        if (!t)                                                                           \
            return fail(p, "brak pamieci");                                               \
        r->field = (type *)t;                                                             \
    } while (0)
    GROW(start, float, 3);
    GROW(end, float, 3);
    GROW(line, int32_t, 1);
    GROW(tool, int32_t, 1);
    GROW(kind, int8_t, 1);
    GROW(feed, float, 1);
    GROW(spindle, float, 1);
#undef GROW
    p->cap = cap;
    return 0;
}

static int add_move(Interp *p, const double a[3], const double b[3], int line, int kind,
                    double feed)
{
    lrt_gcode_moves *r;
    size_t i, k;
    for (k = 0; k < 3; k++)
        if (!isfinite(a[k]) || !isfinite(b[k]))
            return fail(p, "linia %d: współrzędne ruchu nie są skończone", line);
    if (reserve_moves(p, (size_t)p->r->n + 1))
        return -1;
    r = p->r;
    i = (size_t)r->n++;
    for (k = 0; k < 3; k++) {
        r->start[i * 3 + k] = (float)a[k];
        r->end[i * 3 + k] = (float)b[k];
    }
    r->line[i] = line;
    r->tool[i] = p->tool;
    r->kind[i] = (int8_t)kind;
    r->feed[i] = (float)feed;
    r->spindle[i] = (float)(p->direction * p->speed);
    return 0;
}

static void note(Interp *p, const char *fmt, ...)
{
    char buf[400];
    va_list ap;
    size_t len, i, need;
    lrt_gcode_moves *r = p->r;

    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    len = strlen(buf);
    /* duplikat tej samej uwagi moze powstac tylko w obrebie jednej linii (tekst ma numer) */
    for (i = p->line_first_note; i < p->note_count; i++) {
        const char *s = r->notes + p->note_off[i];
        if (strncmp(s, buf, len) == 0 && (s[len] == '\n' || s[len] == '\0'))
            return;
    }
    need = (size_t)r->notes_len + len + 2;
    if (need > p->notes_cap) {
        size_t cap = p->notes_cap ? p->notes_cap * 2 : 1024;
        char *t;
        while (cap < need)
            cap *= 2;
        t = realloc(r->notes, cap);
        if (!t)
            return;
        r->notes = t;
        p->notes_cap = cap;
    }
    if (p->note_count == p->note_off_cap) {
        size_t cap = p->note_off_cap ? p->note_off_cap * 2 : 64;
        size_t *t = realloc(p->note_off, cap * sizeof *t);
        if (!t)
            return;
        p->note_off = t;
        p->note_off_cap = cap;
    }
    if (r->notes_len > 0)
        r->notes[r->notes_len++] = '\n';
    p->note_off[p->note_count++] = (size_t)r->notes_len;
    memcpy(r->notes + r->notes_len, buf, len + 1);
    r->notes_len += (int64_t)len;
}

/* ---------------------------------------------------------------- pomocnicze */

static int is_space(unsigned char c)
{
    return c == ' ' || (c >= 0x09 && c <= 0x0d) || (c >= 0x1c && c <= 0x1f);
}

static int is_word(unsigned char c)
{
    return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_'
           || c >= 0x80;
}

static int is_digit(unsigned char c)
{
    return c >= '0' && c <= '9';
}

/* Python: f"{f:g}" po int(f)==f daje str(int(f)). */
static void norm_code(const char *num, size_t len, char out[32])
{
    char tmp[64];
    double f;
    if (len >= sizeof tmp)
        len = sizeof tmp - 1;
    memcpy(tmp, num, len);
    tmp[len] = '\0';
    f = strtod(tmp, NULL);
    if (f == floor(f) && fabs(f) < 1e15)
        snprintf(out, 32, "%lld", (long long)f);
    else
        snprintf(out, 32, "%g", f);
}

/* Python: x % tau dla dodatniego dzielnika. */
static double pymod(double x, double m)
{
    double r = fmod(x, m);
    if (r != 0.0) {
        if (r < 0.0)
            r += m;
    } else {
        r = copysign(0.0, m);
    }
    return r;
}

static long chord_count(double radius, double sweep)
{
    double max_angle, c;
    if (radius <= CHORD_TOL)
        return 1;
    max_angle = 2.0 * acos(1.0 - CHORD_TOL / radius);
    c = ceil(fabs(sweep) / max_angle - 1e-9);
    if (!(c >= 1.0))
        return 1;
    if (c > (double)LRT_MAX_CHORDS + 1.0)
        return LRT_MAX_CHORDS + 1;
    return (long)c;
}

/* ------------------------------------------------------------------- ruch */

static const int PLANE_AXES[4][3] = {{0, 0, 0}, {0, 1, 2}, {2, 0, 1}, {1, 2, 0}};

static int arc_move(Interp *p, int line, const double end[3], const double c[2], int rotation,
                    const int axes[3])
{
    const int a1 = axes[0], a2 = axes[1], ax = axes[2];
    const double *s = p->pos;
    const double r0 = hypot(s[a1] - c[0], s[a2] - c[1]);
    const double r1 = hypot(end[a1] - c[0], end[a2] - c[1]);
    const double t0 = atan2(s[a2] - c[1], s[a1] - c[0]);
    const double t1 = atan2(end[a2] - c[1], end[a1] - c[0]);
    double sweep, step, prev[3], cur[3];
    long n, i;
    int turns;

    if (rotation == 0)
        return fail(p, "łuk bez kierunku (rotation = 0)");
    sweep = rotation > 0 ? pymod(t1 - t0, TAU) : pymod(t0 - t1, TAU);
    if (sweep < 1e-9)
        sweep = TAU;
    turns = rotation < 0 ? -rotation : rotation;
    sweep = copysign(sweep + TAU * (turns - 1), (double)rotation);
    n = chord_count(r0 > r1 ? r0 : r1, sweep);
    if (n > LRT_MAX_CHORDS)
        return fail(p, "linia %d: łuk ma zbyt wiele cięciw", line);
    step = 1.0 / (double)n;           /* numpy.linspace: t[i] = i * (1/n), t[n] = 1 */
    memcpy(prev, s, sizeof prev);
    for (i = 0; i <= n; i++) {
        const double t = (i == n) ? 1.0 : (double)i * step;
        const double ang = t0 + sweep * t;
        const double r = r0 + (r1 - r0) * t;
        cur[0] = s[0];
        cur[1] = s[1];
        cur[2] = s[2];
        cur[a1] = c[0] + r * cos(ang);
        cur[a2] = c[1] + r * sin(ang);
        cur[ax] = s[ax] + (end[ax] - s[ax]) * t;
        if (i == n)
            memcpy(cur, end, sizeof cur);
        if (i > 0 && add_move(p, prev, cur, line, LRT_KIND_ARC, p->feed))
            return -1;
        memcpy(prev, cur, sizeof prev);
    }
    return 0;
}

typedef struct {
    int has[26];
    double v[26];
} Vals;

#define HAS(vals, ch) ((vals)->has[(ch) - 'A'])
#define VAL(vals, ch) ((vals)->v[(ch) - 'A'])

static int center_from_r(Interp *p, int line, const Vals *val, const double end[3],
                         const int axes[3], double out[2])
{
    const int a1 = axes[0], a2 = axes[1];
    const double r = VAL(val, 'R') * p->scale;
    const double px = p->pos[a1], py = p->pos[a2], qx = end[a1], qy = end[a2];
    const double dx = qx - px, dy = qy - py;
    const double d = sqrt(dx * dx + dy * dy);
    double h, side, t;
    if (d < 1e-12 || d > 2.0 * fabs(r) + 1e-6)
        return fail(p, "linia %d: łuk R — promień %g za mały", line,
                    fabs(r));
    t = r * r - d * d / 4.0;
    h = sqrt(t > 0.0 ? t : 0.0);
    side = ((p->motion == 3) == (r > 0)) ? 1.0 : -1.0;
    out[0] = (px + qx) / 2.0 + side * h * (-dy / d);
    out[1] = (py + qy) / 2.0 + side * h * (dx / d);
    return 0;
}

static void target(const Interp *p, const Vals *val, double end[3])
{
    static const char L[3] = {'X', 'Y', 'Z'};
    int i;
    memcpy(end, p->pos, 3 * sizeof(double));
    for (i = 0; i < 3; i++)
        if (HAS(val, L[i])) {
            const double v = VAL(val, L[i]) * p->scale;
            end[i] = p->absolute ? v : end[i] + v;
        }
}

static int go(Interp *p, int line, int kind, double x, double y, double z)
{
    const double pt[3] = {x, y, z};
    if (add_move(p, p->pos, pt, line, kind, kind == LRT_KIND_RAPID ? 0.0 : p->feed))
        return -1;
    memcpy(p->pos, pt, sizeof pt);
    return 0;
}

static int cycle(Interp *p, int line, const Vals *val)
{
    static const char K[3] = {'Z', 'R', 'Q'};
    double xy[3], r, bottom, q, clear;
    int i;

    if (p->plane != 1) {
        note(p, "Linia %d: cykl wiercenia poza G17 pominięty.", line);
        return 0;
    }
    for (i = 0; i < 3; i++)
        if (HAS(val, K[i])) {
            p->cyc_has[i] = 1;
            p->cyc_val[i] = VAL(val, K[i]) * p->scale;
        }
    if (!p->cyc_has[1] || !p->cyc_has[0])
        return fail(p, "linia %d: cykl G%d bez R lub Z", line, p->motion);
    if (!p->has_initial_z) {
        p->has_initial_z = 1;
        p->initial_z = p->pos[2];
    }
    r = p->cyc_val[1];
    bottom = p->cyc_val[0];
    if (!p->absolute)
        note(p, "Linia %d: cykl w G91 — R i Z traktowane jak w G90.", line);
    memcpy(xy, p->pos, sizeof xy);
    for (i = 0; i < 2; i++)
        if (HAS(val, i ? 'Y' : 'X')) {
            const double v = VAL(val, i ? 'Y' : 'X') * p->scale;
            xy[i] = p->absolute ? v : xy[i] + v;
        }

    if (p->pos[2] < r && go(p, line, LRT_KIND_RAPID, p->pos[0], p->pos[1], r))
        return -1;
    if (go(p, line, LRT_KIND_RAPID, xy[0], xy[1], p->pos[2]))
        return -1;
    if (go(p, line, LRT_KIND_RAPID, xy[0], xy[1], r))
        return -1;
    q = p->cyc_has[2] ? p->cyc_val[2] : 0.0;
    if ((p->motion == 83 || p->motion == 73) && q > 0) {
        double depth = r;
        long guard = 0;
        while (depth > bottom + 1e-9) {
            const double target_z = (depth - q) > bottom ? (depth - q) : bottom;
            if (target_z >= depth || ++guard > 10000000L)
                return fail(p, "linia %d: cykl wiercenia nie postępuje", line);
            if (go(p, line, LRT_KIND_FEED, xy[0], xy[1], target_z))
                return -1;
            if (target_z > bottom) {
                if (p->motion == 83 && go(p, line, LRT_KIND_RAPID, xy[0], xy[1], r))
                    return -1;
                if (go(p, line, LRT_KIND_RAPID, xy[0], xy[1], target_z + PECK_CLEARANCE))
                    return -1;
            }
            depth = target_z;
        }
    } else if (go(p, line, LRT_KIND_FEED, xy[0], xy[1], bottom)) {
        return -1;
    }
    clear = (p->retract == 98) ? (p->initial_z > r ? p->initial_z : r) : r;
    return go(p, line, LRT_KIND_RAPID, xy[0], xy[1], clear);
}

static int motion(Interp *p, int line, const Vals *val)
{
    double end[3];
    if (p->motion < 0) {
        note(p, "Linia %d: współrzędne bez trybu ruchu — pominięte.", line);
        return 0;
    }
    if (p->motion >= 73)
        return cycle(p, line, val);
    target(p, val, end);
    if (p->motion <= 1) {
        const int kind = p->motion == 0 ? LRT_KIND_RAPID : LRT_KIND_FEED;
        if (add_move(p, p->pos, end, line, kind, kind == LRT_KIND_RAPID ? 0.0 : p->feed))
            return -1;
    } else {
        const int *axes = PLANE_AXES[p->plane];
        double c[2];
        int turns = HAS(val, 'P') ? (int)VAL(val, 'P') : 1;
        if (HAS(val, 'R')) {
            if (center_from_r(p, line, val, end, axes, c))
                return -1;
        } else {
            static const char IJK[3] = {'I', 'J', 'K'};
            int k;
            for (k = 0; k < 2; k++) {
                const int axis = axes[k];
                const double v = HAS(val, IJK[axis]) ? VAL(val, IJK[axis]) * p->scale : 0.0;
                c[k] = p->arc_absolute ? v : p->pos[axis] + v;
            }
        }
        if (arc_move(p, line, end, c, p->motion == 3 ? turns : -turns, axes))
            return -1;
    }
    memcpy(p->pos, end, sizeof end);
    return 0;
}

/* ------------------------------------------------------------------- blok */

typedef struct {
    char (*codes)[32];
    size_t n, cap;
} CodeList;

static int push_code(CodeList *l, const char *num, size_t len)
{
    if (l->n == l->cap) {
        size_t cap = l->cap ? l->cap * 2 : 16;
        void *t = realloc(l->codes, cap * sizeof *l->codes);
        if (!t)
            return -1;
        l->codes = t;
        l->cap = cap;
    }
    norm_code(num, len, l->codes[l->n++]);
    return 0;
}

static int has_code(const CodeList *l, const char *code)
{
    size_t i;
    for (i = 0; i < l->n; i++)
        if (strcmp(l->codes[i], code) == 0)
            return 1;
    return 0;
}

static int in_list(const char *code, const char *const *list)
{
    for (; *list; list++)
        if (strcmp(code, *list) == 0)
            return 1;
    return 0;
}

static const char *const MOTION_CODES[] = {"0", "1", "2", "3", "73", "81", "82", "83", NULL};
static const char *const IGNORED_G[] = {
    "4", "17.1", "18.1", "19.1", "43", "43.1", "49", "54", "55", "56", "57", "58", "59", "59.1",
    "59.2", "59.3", "61", "61.1", "64", "93", "94", "95", "96", "97", "40", NULL};
static const char *const CUTCOMP[] = {"41", "42", "41.1", "42.1", NULL};
static const char *const SKIPPED[] = {"28", "30", "53", "92", "10", NULL};

/* Ciag slow jak re.findall(r"([A-Z])\s*([-+]?(?:\d+\.?\d*|\.\d+))") na tekscie bez spacji. */
static int block(Interp *p, int line, const char *text, size_t n, CodeList *g, CodeList *m)
{
    Vals val;
    size_t i = 0;
    int skip = 0;
    size_t k;
    int any_xyz, any_ijkr;

    memset(&val, 0, sizeof val);
    g->n = m->n = 0;
    while (i < n) {
        const unsigned char c = (unsigned char)text[i];
        size_t j, num0;
        if (c < 'A' || c > 'Z') {
            i++;
            continue;
        }
        j = i + 1;
        while (j < n && is_space((unsigned char)text[j]))
            j++;
        num0 = j;
        if (j < n && (text[j] == '-' || text[j] == '+'))
            j++;
        if (j < n && is_digit((unsigned char)text[j])) {
            while (j < n && is_digit((unsigned char)text[j]))
                j++;
            if (j < n && text[j] == '.') {
                j++;
                while (j < n && is_digit((unsigned char)text[j]))
                    j++;
            }
        } else if (j + 1 < n && text[j] == '.' && is_digit((unsigned char)text[j + 1])) {
            j++;
            while (j < n && is_digit((unsigned char)text[j]))
                j++;
        } else {
            i++;
            continue;
        }
        if (c == 'G') {
            if (push_code(g, text + num0, j - num0))
                return fail(p, "brak pamieci");
        } else if (c == 'M') {
            if (push_code(m, text + num0, j - num0))
                return fail(p, "brak pamieci");
        } else if (c != 'N' && c != 'O') {
            char tmp[512];
            size_t len = j - num0;
            if (len >= sizeof tmp)
                len = sizeof tmp - 1;
            memcpy(tmp, text + num0, len);
            tmp[len] = '\0';
            HAS(&val, c) = 1;
            VAL(&val, c) = strtod(tmp, NULL);
        }
        i = j;
    }

    for (k = 0; k < g->n; k++) {
        const char *code = g->codes[k];
        if (!strcmp(code, "20")) {
            p->scale = INCH;
        } else if (!strcmp(code, "21")) {
            p->scale = 1.0;
        } else if (!strcmp(code, "90")) {
            p->absolute = 1;
        } else if (!strcmp(code, "91")) {
            p->absolute = 0;
        } else if (!strcmp(code, "90.1")) {
            p->arc_absolute = 1;
        } else if (!strcmp(code, "91.1")) {
            p->arc_absolute = 0;
        } else if (!strcmp(code, "17") || !strcmp(code, "18") || !strcmp(code, "19")) {
            p->plane = atoi(code) - 16;
        } else if (!strcmp(code, "98") || !strcmp(code, "99")) {
            p->retract = atoi(code);
        } else if (!strcmp(code, "80")) {
            p->motion = -1;
            p->cyc_has[0] = p->cyc_has[1] = p->cyc_has[2] = 0;
            p->has_initial_z = 0;
        } else if (in_list(code, CUTCOMP)) {
            note(p, "Linia %d: korekcja promienia G%s pominięta — tor środka "
                    "narzędzia bez korekcji (pełny tor: interpreter LinuxCNC).",
                 line, code);
        } else if (in_list(code, SKIPPED)) {
            note(p, "Linia %d: G%s pominięte w ścieżce.", line, code);
            skip = 1;
        } else if (in_list(code, MOTION_CODES)) {
            const int id = atoi(code);
            if (id >= 73 && p->motion != id)
                p->has_initial_z = 0;
            p->motion = id;
        } else if (!in_list(code, IGNORED_G)) {
            note(p, "Linia %d: G%s nieobsługiwane — pominięte.", line, code);
            skip = 1;
        }
    }
    if (HAS(&val, 'F'))
        p->feed = VAL(&val, 'F') * p->scale;
    if (HAS(&val, 'T'))
        p->pending_tool = (int)VAL(&val, 'T');
    if (has_code(m, "6"))
        p->tool = p->pending_tool;
    if (HAS(&val, 'S'))
        p->speed = VAL(&val, 'S');
    if (has_code(m, "3"))
        p->direction = 1.0;
    if (has_code(m, "4"))
        p->direction = -1.0;
    if (has_code(m, "5"))
        p->direction = 0.0;
    any_xyz = HAS(&val, 'X') || HAS(&val, 'Y') || HAS(&val, 'Z');
    any_ijkr = HAS(&val, 'I') || HAS(&val, 'J') || HAS(&val, 'K') || HAS(&val, 'R');
    if (!skip && (any_xyz || ((p->motion == 2 || p->motion == 3) && any_ijkr))) {
        if (motion(p, line, &val))
            return -1;
    }
    if (has_code(m, "2") || has_code(m, "30"))
        p->ended = 1;
    return 0;
}

/* ---------------------------------------------------------------- O-slowa */

/* re.match(r"^O\s*(<[^>]*>|\d+)\s*(\w+)") z backtrackingiem jak w Pythonie. */
static int oword(const char *t, size_t n, size_t *name0, size_t *name_len, size_t *kw0,
                 size_t *kw_len)
{
    size_t i = 1, j;
    if (n == 0 || t[0] != 'O')
        return 0;
    while (i < n && is_space((unsigned char)t[i]))
        i++;
    if (i >= n)
        return 0;
    if (t[i] == '<') {
        j = i + 1;
        while (j < n && t[j] != '>')
            j++;
        if (j >= n)
            return 0;
        *name0 = i;
        *name_len = j - i + 1;
        i = j + 1;
        while (i < n && is_space((unsigned char)t[i]))
            i++;
        if (i >= n || !is_word((unsigned char)t[i]))
            return 0;
    } else if (is_digit((unsigned char)t[i])) {
        const size_t d0 = i;
        size_t digits, k;
        while (i < n && is_digit((unsigned char)t[i]))
            i++;
        digits = i - d0;
        k = i;
        while (k < n && is_space((unsigned char)t[k]))
            k++;
        if (k < n && is_word((unsigned char)t[k])) {
            *name0 = d0;
            *name_len = digits;
            i = k;
        } else if (digits >= 2) {
            *name0 = d0;
            *name_len = digits - 1;
            *kw0 = d0 + digits - 1;
            *kw_len = 1;
            return 1;
        } else {
            return 0;
        }
    } else {
        return 0;
    }
    *kw0 = i;
    while (i < n && is_word((unsigned char)t[i]))
        i++;
    *kw_len = i - *kw0;
    return 1;
}

/* --------------------------------------------------------------- wejscie */

/* Dlugosc terminatora wiersza w tekscie (jak str.splitlines), 0 gdy to nie koniec wiersza. */
static size_t eol_len(const unsigned char *s, size_t i, size_t n)
{
    const unsigned char c = s[i];
    if (c == '\r')
        return (i + 1 < n && s[i + 1] == '\n') ? 2 : 1;
    if (c == '\n' || c == 0x0b || c == 0x0c || c == 0x1c || c == 0x1d || c == 0x1e)
        return 1;
    if (c == 0xc2 && i + 1 < n && s[i + 1] == 0x85)
        return 2;
    if (c == 0xe2 && i + 2 < n && s[i + 1] == 0x80 && (s[i + 2] == 0xa8 || s[i + 2] == 0xa9))
        return 3;
    return 0;
}

static int run_line(Interp *p, int number, const unsigned char *raw, size_t rawlen, char *buf,
                    CodeList *g, CodeList *m, char *skip_name, size_t *skip_len, int *skipping)
{
    size_t n = 0, i, a, b, sp;
    char *t;

    /* split(";")[0], potem usuniecie nawiasow (\([^)]*\)), strip, upper */
    for (i = 0; i < rawlen && raw[i] != ';'; i++)
        ;
    rawlen = i;
    for (i = 0; i < rawlen;) {
        if (raw[i] == '(') {
            size_t j = i + 1;
            while (j < rawlen && raw[j] != ')')
                j++;
            if (j < rawlen) {
                i = j + 1;
                continue;
            }
        }
        buf[n++] = (char)raw[i++];
    }
    for (a = 0; a < n && is_space((unsigned char)buf[a]); a++)
        ;
    for (b = n; b > a && is_space((unsigned char)buf[b - 1]); b--)
        ;
    t = buf + a;
    n = b - a;
    for (i = 0; i < n; i++)
        if (t[i] >= 'a' && t[i] <= 'z')
            t[i] = (char)(t[i] - 'a' + 'A');
    if (n == 0 || t[0] == '%')
        return 0;

    {
        size_t name0, name_len, kw0, kw_len;
        if (oword(t, n, &name0, &name_len, &kw0, &kw_len)) {
            char kw[64];
            size_t k, kl = kw_len < sizeof kw - 1 ? kw_len : sizeof kw - 1;
            for (k = 0; k < kl; k++) {
                const char c = t[kw0 + k];
                kw[k] = (c >= 'A' && c <= 'Z') ? (char)(c - 'A' + 'a') : c;
            }
            kw[kl] = '\0';
            if (!*skipping && !strcmp(kw, "sub")) {
                *skipping = 1;
                *skip_len = name_len < 255 ? name_len : 255;
                memcpy(skip_name, t + name0, *skip_len);
            } else if (*skipping && name_len == *skip_len
                       && !memcmp(skip_name, t + name0, name_len) && !strcmp(kw, "endsub")) {
                *skipping = 0;
            } else if (!*skipping) {
                note(p, "Linia %d: o-word %s pominięte (tylko interpreter LinuxCNC).", number,
                     kw);
            }
            return 0;
        }
    }
    if (*skipping)
        return 0;
    /* findall dziala na tekscie bez spacji (tylko ' ', nie tabulatorow) */
    for (i = 0, sp = 0; i < n; i++)
        if (t[i] != ' ')
            t[sp++] = t[i];
    return block(p, number, t, sp, g, m);
}

lrt_gcode_moves *lrt_gcode_parse(const char *text, int64_t len, const double start[3],
                                 int metric)
{
    lrt_gcode_moves *r = calloc(1, sizeof *r);
    Interp p;
    CodeList g = {0}, m = {0};
    char skip_name[256];
    size_t skip_len = 0;
    int skipping = 0;
    const unsigned char *s = (const unsigned char *)text;
    size_t n = len < 0 ? 0 : (size_t)len, i = 0, from = 0;
    char *buf;
    int number = 0;

    if (!r)
        return NULL;
    memset(&p, 0, sizeof p);
    p.r = r;
    p.motion = -1;
    p.absolute = 1;
    p.plane = 1;
    p.scale = metric ? 1.0 : INCH;
    p.retract = 98;
    if (start)
        memcpy(p.pos, start, sizeof p.pos);
    buf = malloc(n + 2);
    if (!buf) {
        r->error = 1;
        snprintf(r->error_msg, sizeof r->error_msg, "brak pamieci");
        return r;
    }
    while (from < n && !p.ended && !r->error) {
        size_t eol = 0;
        i = from;
        while (i < n && !(eol = eol_len(s, i, n)))
            i++;
        number++;
        p.line_first_note = p.note_count;
        run_line(&p, number, s + from, i - from, buf, &g, &m, skip_name, &skip_len, &skipping);
        from = i + eol;
        if (eol == 0)
            break;
    }
    free(buf);
    free(g.codes);
    free(m.codes);
    free(p.note_off);
    if (!r->notes) {
        r->notes = calloc(1, 1);
    }
    return r;
}

void lrt_gcode_free(lrt_gcode_moves *r)
{
    if (!r)
        return;
    free(r->start);
    free(r->end);
    free(r->line);
    free(r->tool);
    free(r->kind);
    free(r->feed);
    free(r->spindle);
    free(r->notes);
    free(r);
}
