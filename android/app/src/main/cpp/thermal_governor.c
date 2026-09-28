/*
 * thermal_governor.c -- an opt-in thermal governor core (#557)
 *
 * See thermal_governor.h for the policy. This file is plain C on libc, plus
 * <android/log.h> on Android, so docs/lanes/remote/thermal557_harness.c can
 * build and drive it on the desktop.
 */

#include "thermal_governor.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __ANDROID__
#include <android/log.h>
#endif

#define THERMAL_TICK_PERIOD_S 1.0

static const char *const rung_names[THERMAL_RUNG_COUNT] = {
    "cap30", "no-occl", "scale1x", "rp-mode",
};

const char *thermal_governor_rung_name(int rung)
{
    return rung >= 0 && rung < THERMAL_RUNG_COUNT ? rung_names[rung] : "?";
}

/*
 * A rung can be registered from another thread while the governor runs. The
 * opaque is published before the function, and the function is read first,
 * so a caller never sees a function without its opaque.
 */
static void rungs_store(ThermalRungs *t, int r, ThermalRungFn fn, void *opaque)
{
    __atomic_store_n(&t->opaque[r], opaque, __ATOMIC_RELAXED);
    __atomic_store_n(&t->fn[r], fn, __ATOMIC_RELEASE);
}

static ThermalRungFn rungs_fn(const ThermalRungs *t, int r)
{
    return __atomic_load_n(&t->fn[r], __ATOMIC_ACQUIRE);
}

static void *rungs_opaque(const ThermalRungs *t, int r)
{
    return __atomic_load_n(&t->opaque[r], __ATOMIC_RELAXED);
}

void thermal_governor_params_default(ThermalGovernorParams *p)
{
    /*
     * tau comes from the GTA pilot on the Thor (#507, thermal507-3751184):
     * xo-therm climbed 54.3 -> 78.0 C in 538 s at MAX. Its climb rate fell
     * in a straight line with temperature, as a first-order approach does.
     * A least-squares line through the rates between samples gives 210 s
     * toward 80.3 C without the launch interval, 250 s toward 81.3 C with it.
     */
    p->tau_s = 210.0;
    p->window_s = 60.0;
    p->min_span_s = 45.0;
    p->down_c = 72.0;
    p->down_hold_s = 60.0;
    p->up_c = 64.0;
    p->up_hold_s = 300.0;
    p->min_gap_s = 120.0;
    p->gap_reset_s = 10.0;
    p->status_every_s = 30.0;
}

void thermal_governor_init(ThermalGovernor *g, const ThermalGovernorParams *p)
{
    memset(g, 0, sizeof(*g));
    if (p) {
        g->p = *p;
    } else {
        thermal_governor_params_default(&g->p);
    }
    g->rungs = &g->own_rungs;
    g->last_change_t = -INFINITY;
    g->hot_since = g->cool_since = NAN;
    g->slope_c_s = g->teq_c = NAN;
    g->last.xo_c = NAN;
    g->last.pause = g->last.mitig = g->last.read_us = -1;
}

void thermal_governor_set_rung_fn(ThermalGovernor *g, ThermalRung rung,
                                  ThermalRungFn fn, void *opaque)
{
    if ((int)rung >= 0 && rung < THERMAL_RUNG_COUNT) {
        rungs_store(g->rungs, rung, fn, opaque);
    }
}

void thermal_governor_set_log_fn(ThermalGovernor *g, ThermalLogFn fn,
                                 void *opaque)
{
    g->log_fn = fn;
    g->log_opaque = opaque;
}

int thermal_governor_wired(const ThermalGovernor *g)
{
    int n = 0;
    for (int r = 0; r < THERMAL_RUNG_COUNT; r++) {
        n += rungs_fn(g->rungs, r) != NULL;
    }
    return n;
}

static void emit(ThermalLogFn fn, void *opaque, const char *line)
{
    if (fn) {
        fn(opaque, line);
        return;
    }
#ifdef __ANDROID__
    /*
     * hakuX-perf, because the dispatcher's LOGCAT_SPEC ends in *:S and keeps
     * only the tags it names.
     */
    __android_log_print(ANDROID_LOG_INFO, "hakuX-perf", "%s", line);
#else
    fprintf(stderr, "hakuX-perf: %s\n", line);
#endif
}

static void gov_log(ThermalGovernor *g, const char *fmt, ...)
    __attribute__((format(printf, 2, 3)));

static void gov_log(ThermalGovernor *g, const char *fmt, ...)
{
    char line[512];
    va_list ap;

    va_start(ap, fmt);
    vsnprintf(line, sizeof(line), fmt, ap);
    va_end(ap);
    emit(g->log_fn, g->log_opaque, line);
}

/* --- the slope window --- */

static int win_index(const ThermalGovernor *g, int i)
{
    /* i = 0 is the oldest sample in the window */
    return (g->win_head - g->win_n + i + THERMAL_GOVERNOR_MAX_SAMPLES) %
           THERMAL_GOVERNOR_MAX_SAMPLES;
}

static void window_reset(ThermalGovernor *g)
{
    g->win_head = g->win_n = 0;
    g->hot_since = g->cool_since = NAN;
    g->slope_c_s = g->teq_c = NAN;
}

static void window_push(ThermalGovernor *g, double t, double c)
{
    while (g->win_n > 0 &&
           (g->win_n == THERMAL_GOVERNOR_MAX_SAMPLES ||
            t - g->win_t[win_index(g, 0)] > g->p.window_s)) {
        g->win_n--;
    }
    g->win_t[g->win_head] = t;
    g->win_c[g->win_head] = c;
    g->win_head = (g->win_head + 1) % THERMAL_GOVERNOR_MAX_SAMPLES;
    g->win_n++;
}

/* The least-squares slope, in C per second, once the window spans enough. */
static bool window_slope(const ThermalGovernor *g, double *slope)
{
    int n = g->win_n;
    double tn, st = 0, sc = 0, sxx = 0, sxy = 0;

    if (n < 3) {
        return false;
    }
    tn = g->win_t[win_index(g, n - 1)];
    if (tn - g->win_t[win_index(g, 0)] < g->p.min_span_s) {
        return false;
    }
    /* Times relative to the newest sample, so their squares stay small. */
    for (int i = 0; i < n; i++) {
        st += g->win_t[win_index(g, i)] - tn;
        sc += g->win_c[win_index(g, i)];
    }
    for (int i = 0; i < n; i++) {
        double dt = g->win_t[win_index(g, i)] - tn - st / n;
        sxx += dt * dt;
        sxy += dt * (g->win_c[win_index(g, i)] - sc / n);
    }
    if (!(sxx > 0)) {
        return false;
    }
    *slope = sxy / sxx;
    return true;
}

/* --- the rungs --- */

static bool rung_engaged(const ThermalGovernor *g, int r)
{
    for (int i = 0; i < g->level; i++) {
        if (g->engaged[i] == r) {
            return true;
        }
    }
    return false;
}

/* The next rung to engage: the first in order that is wired and not engaged. */
static int next_rung(const ThermalGovernor *g)
{
    for (int r = 0; r < THERMAL_RUNG_COUNT; r++) {
        if (!rung_engaged(g, r) && rungs_fn(g->rungs, r)) {
            return r;
        }
    }
    return -1;
}

static void log_event(ThermalGovernor *g, double now, const char *what,
                      int rung, const char *why)
{
    gov_log(g, "[thermal557] %s rung=%d/%d %s t=%.0f xo=%.2f dTdt=%+.2f "
            "teq=%.2f pause=%d cdev=%d why=%s",
            what, g->level, thermal_governor_wired(g),
            rung >= 0 ? thermal_governor_rung_name(rung) : "-", now - g->t0,
            g->last.xo_c, g->slope_c_s * 60.0, g->teq_c, g->last.pause,
            g->last.mitig, why);
}

static void step_down(ThermalGovernor *g, double now, int r, bool paused)
{
    char why[48];
    ThermalRungFn fn;

    if (paused) {
        snprintf(why, sizeof(why), "pause");
    } else {
        snprintf(why, sizeof(why), "teq>%.1f/%.0fs", g->p.down_c,
                 g->p.down_hold_s);
    }
    g->engaged[g->level++] = r;
    g->n_down++;
    /* Announce first, then act. */
    log_event(g, now, "down", r, why);
    fn = rungs_fn(g->rungs, r);
    if (fn) {
        fn(rungs_opaque(g->rungs, r), true);
    }
}

static void step_up(ThermalGovernor *g, double now)
{
    char why[48];
    int r = g->engaged[--g->level];
    ThermalRungFn fn;

    snprintf(why, sizeof(why), "teq<%.1f/%.0fs", g->p.up_c, g->p.up_hold_s);
    g->n_up++;
    log_event(g, now, "up", r, why);
    fn = rungs_fn(g->rungs, r);
    if (fn) {
        fn(rungs_opaque(g->rungs, r), false);
    }
}

static void maybe_status(ThermalGovernor *g, double now)
{
    if (g->p.status_every_s <= 0 || now < g->next_status_t) {
        return;
    }
    g->next_status_t = now + g->p.status_every_s;
    gov_log(g, "[thermal557] state rung=%d/%d t=%.0f xo=%.2f dTdt=%+.2f "
            "teq=%.2f pause=%d cdev=%d hot_s=%.0f cool_s=%.0f rd_us=%d "
            "n=%u bad=%u down=%u up=%u",
            g->level, thermal_governor_wired(g), now - g->t0, g->last.xo_c,
            g->slope_c_s * 60.0, g->teq_c, g->last.pause, g->last.mitig,
            isnan(g->hot_since) ? 0.0 : now - g->hot_since,
            isnan(g->cool_since) ? 0.0 : now - g->cool_since,
            g->last.read_us, g->n_samples, g->n_bad, g->n_down, g->n_up);
}

int thermal_governor_feed(ThermalGovernor *g, double now,
                          const ThermalSample *s)
{
    bool valid, paused, hot, cool, may_change;
    double slope;
    int change = 0;

    if (!g->started) {
        g->started = true;
        g->t0 = g->last_t = now;
        g->next_status_t = now + g->p.status_every_s;
    }
    if (g->win_n > 0 && now <= g->win_t[win_index(g, g->win_n - 1)]) {
        return 0; /* not after the last sample: ignore it */
    }
    g->n_samples++;
    g->last = *s;
    if (!isfinite(s->xo_c)) {
        /* No reading. A run of these longer than gap_reset_s is a silence. */
        g->n_bad++;
        g->slope_c_s = g->teq_c = NAN;
        maybe_status(g, now);
        return 0;
    }
    /*
     * The dwell times measure an unbroken stretch, so a silence (the app
     * paused, or the reads failing) restarts the window and both dwells.
     */
    if (now - g->last_t > g->p.gap_reset_s) {
        window_reset(g);
    }
    g->last_t = now;
    window_push(g, now, s->xo_c);
    if (window_slope(g, &slope)) {
        g->slope_c_s = slope;
        g->teq_c = s->xo_c + g->p.tau_s * slope;
    } else {
        g->slope_c_s = g->teq_c = NAN;
    }
    valid = isfinite(g->teq_c);
    /*
     * A pause counts as hot: the kernel has already found the budget
     * exceeded, and the fall it causes would otherwise read as cooling.
     */
    paused = s->pause > 0;
    hot = paused || (valid && g->teq_c > g->p.down_c);
    cool = s->pause == 0 && valid && g->teq_c < g->p.up_c;

    if (!hot) {
        g->hot_since = NAN;
        g->floor_logged = false;
    } else if (isnan(g->hot_since)) {
        g->hot_since = now;
    }
    if (!cool) {
        g->cool_since = NAN;
    } else if (isnan(g->cool_since)) {
        g->cool_since = now;
    }

    may_change = now - g->last_change_t >= g->p.min_gap_s;
    if (hot && may_change && now - g->hot_since >= g->p.down_hold_s) {
        int r = next_rung(g);
        if (r >= 0) {
            step_down(g, now, r, paused);
            change = 1;
        } else if (!g->floor_logged) {
            log_event(g, now, "floor", -1, paused ? "pause" : "teq");
            g->floor_logged = true;
        }
    } else if (cool && may_change && g->level > 0 &&
               now - g->cool_since >= g->p.up_hold_s) {
        step_up(g, now);
        change = -1;
    }
    if (change) {
        /* A change must be earned again from its own effect. */
        g->last_change_t = now;
        g->hot_since = g->cool_since = NAN;
    }
    maybe_status(g, now);
    return change;
}

/* --- the sysfs reader --- */

static int read_text(const char *path, char *buf, size_t size)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    ssize_t n;

    if (fd < 0) {
        return -1;
    }
    n = read(fd, buf, size - 1);
    close(fd);
    if (n < 0) {
        return -1;
    }
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r' ||
                     buf[n - 1] == ' ')) {
        n--;
    }
    buf[n] = '\0';
    return (int)n;
}

static bool pread_long(int fd, long *out)
{
    char buf[32];
    char *end;
    ssize_t n = pread(fd, buf, sizeof(buf) - 1, 0);
    long v;

    if (n <= 0) {
        return false;
    }
    buf[n] = '\0';
    errno = 0;
    v = strtol(buf, &end, 10);
    if (end == buf || errno) {
        return false;
    }
    *out = v;
    return true;
}

/* "thermal_zone12" -> 12 for prefix "thermal_zone"; -1 if it is not one. */
static int entry_number(const char *name, const char *prefix)
{
    size_t len = strlen(prefix);
    int n = 0;

    if (strncmp(name, prefix, len) != 0 || name[len] == '\0') {
        return -1;
    }
    for (const char *c = name + len; *c; c++) {
        if (*c < '0' || *c > '9' || n > 100000) {
            return -1;
        }
        n = n * 10 + (*c - '0');
    }
    return n;
}

static int open_attr(ThermalSensors *s, const char *root, const char *entry,
                     const char *attr)
{
    char path[512];
    int fd;

    snprintf(path, sizeof(path), "%s/%s/%s", root, entry, attr);
    fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0 && !s->err) {
        s->err = errno;
    }
    return fd;
}

int thermal_sensors_open(ThermalSensors *s, const char *root,
                         const char *zone_type)
{
    DIR *dir;
    struct dirent *e;
    char path[512], type[128];

    memset(s, 0, sizeof(*s));
    s->zone = s->temp_fd = -1;
    dir = opendir(root);
    if (!dir) {
        s->err = errno;
        return -1;
    }
    while ((e = readdir(dir)) != NULL) {
        int n = entry_number(e->d_name, "thermal_zone");
        int fd;

        if (n >= 0) {
            snprintf(path, sizeof(path), "%s/%s/type", root, e->d_name);
            /* the lowest-numbered zone of the type, whatever readdir's order */
            if (read_text(path, type, sizeof(type)) < 0 ||
                strcmp(type, zone_type) != 0 || (s->zone >= 0 && n > s->zone)) {
                continue;
            }
            fd = open_attr(s, root, e->d_name, "temp");
            if (fd >= 0) {
                if (s->temp_fd >= 0) {
                    close(s->temp_fd);
                }
                s->temp_fd = fd;
                s->zone = n;
            }
            continue;
        }
        if (entry_number(e->d_name, "cooling_device") < 0) {
            continue;
        }
        snprintf(path, sizeof(path), "%s/%s/type", root, e->d_name);
        if (read_text(path, type, sizeof(type)) < 0) {
            continue;
        }
        /* thermal_state.py's PAUSE_PREFIXES */
        if (!strncmp(type, "thermal-pause", 13) ||
            !strncmp(type, "pause-cpu", 9)) {
            if (s->n_pause == THERMAL_SENSORS_MAX_PAUSE) {
                s->n_skipped++;
            } else if ((fd = open_attr(s, root, e->d_name, "cur_state")) >= 0) {
                s->pause_fd[s->n_pause++] = fd;
            }
        } else if (s->n_other == THERMAL_SENSORS_MAX_OTHER) {
            s->n_skipped++;
        } else if ((fd = open_attr(s, root, e->d_name, "cur_state")) >= 0) {
            s->other_fd[s->n_other++] = fd;
        }
    }
    closedir(dir);
    return s->temp_fd >= 0 ? 0 : -1;
}

/* Devices above 0, or -1 when any of them could not be read. */
static int count_set(const int *fds, int n)
{
    int set = 0;
    long v;

    for (int i = 0; i < n; i++) {
        if (!pread_long(fds[i], &v)) {
            return -1;
        }
        set += v > 0;
    }
    return set;
}

void thermal_sensors_read(const ThermalSensors *s, ThermalSample *out)
{
    long v;

    /* thermal zones report milli-C; anything outside -20..130 C is unread */
    out->xo_c = NAN;
    if (s->temp_fd >= 0 && pread_long(s->temp_fd, &v) && v > -20000 &&
        v < 130000) {
        out->xo_c = v / 1000.0;
    }
    out->pause = count_set(s->pause_fd, s->n_pause);
    out->mitig = count_set(s->other_fd, s->n_other);
    out->read_us = -1;
}

void thermal_sensors_close(ThermalSensors *s)
{
    if (s->temp_fd >= 0) {
        close(s->temp_fd);
    }
    for (int i = 0; i < s->n_pause; i++) {
        close(s->pause_fd[i]);
    }
    for (int i = 0; i < s->n_other; i++) {
        close(s->other_fd[i]);
    }
    s->temp_fd = -1;
    s->n_pause = s->n_other = 0;
}

/* --- the process-wide governor behind thermal_governor_tick() --- */

static ThermalRungs registry;
static ThermalGovernor gov;
static ThermalSensors sens;
static int gov_state; /* 0 before the first tick, 1 on, -1 off */
static double gov_start_t, gov_next_t;
static bool gov_config_logged;
static const char *gov_root = "/sys/class/thermal";
static char gov_zone[64] = "xo-therm";
static ThermalLogFn gov_log_fn; /* NULL: hakuX-perf */
static void *gov_log_opaque;

void thermal_governor_register_rung(ThermalRung rung, ThermalRungFn fn,
                                    void *opaque)
{
    if ((int)rung >= 0 && rung < THERMAL_RUNG_COUNT) {
        rungs_store(&registry, rung, fn, opaque);
    }
}

static double monotonic_s(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

static void gov_start(double now)
{
    const char *on = getenv("HAKUX_THERMAL_ADAPT");
    const char *e;
    ThermalGovernorParams p;
    char line[256];

    if (!on || strcmp(on, "1") != 0) {
        gov_state = -1;
        return;
    }
    thermal_governor_params_default(&p);
    e = getenv("HAKUX_THERMAL_TAU_S");
    if (e && *e) {
        char *end;
        double v = strtod(e, &end);
        if (*end == '\0' && v > 0 && v <= 3600) {
            p.tau_s = v;
        }
    }
    e = getenv("HAKUX_THERMAL_ZONE");
    if (e && *e) {
        snprintf(gov_zone, sizeof(gov_zone), "%s", e);
    }
    if (thermal_sensors_open(&sens, gov_root, gov_zone) < 0) {
        /* An enforcing SELinux policy that denies untrusted_app sysfs_thermal
         * ends here with EACCES: said once, then silent. */
        snprintf(line, sizeof(line),
                 "[thermal557] off: no readable zone of type %s under %s (%s)",
                 gov_zone, gov_root,
                 sens.err ? strerror(sens.err) : "not found");
        emit(gov_log_fn, gov_log_opaque, line);
        thermal_sensors_close(&sens);
        gov_state = -1;
        return;
    }
    thermal_governor_init(&gov, &p);
    gov.rungs = &registry;
    thermal_governor_set_log_fn(&gov, gov_log_fn, gov_log_opaque);
    gov_state = 1;
    gov_start_t = gov_next_t = now;
}

static void gov_log_config(void)
{
    char wired[64] = "";
    size_t len = 0;

    for (int r = 0; r < THERMAL_RUNG_COUNT; r++) {
        if (rungs_fn(&registry, r)) {
            len += snprintf(wired + len, sizeof(wired) - len, "%s%s",
                            len ? "," : "", thermal_governor_rung_name(r));
        }
    }
    gov_log(&gov, "[thermal557] config zone=%s tz=%d pause_dev=%d cdev=%d "
            "skipped=%d tau=%.0f window=%.0f span=%.0f down=%.1f/%.0f "
            "up=%.1f/%.0f gap=%.0f wired=%s",
            gov_zone, sens.zone, sens.n_pause, sens.n_other, sens.n_skipped,
            gov.p.tau_s, gov.p.window_s, gov.p.min_span_s, gov.p.down_c,
            gov.p.down_hold_s, gov.p.up_c, gov.p.up_hold_s, gov.p.min_gap_s,
            len ? wired : "none");
}

static void tick_at(double now)
{
    ThermalSample smp;
    double r0;

    if (gov_state == 0) {
        gov_start(now);
    }
    if (gov_state < 0 || now < gov_next_t) {
        return;
    }
    gov_next_t = now + THERMAL_TICK_PERIOD_S;
    r0 = monotonic_s();
    thermal_sensors_read(&sens, &smp);
    smp.read_us = (int)((monotonic_s() - r0) * 1e6);
    /*
     * The first line waits one status interval, so it comes after the first
     * gfps line and readers that start their clock at the first hakuX-perf
     * line (phase_read_split.py) keep their origin.
     */
    if (!gov_config_logged && now - gov_start_t >= gov.p.status_every_s) {
        gov_log_config();
        gov_config_logged = true;
    }
    thermal_governor_feed(&gov, now, &smp);
}

void thermal_governor_tick(void)
{
    if (gov_state < 0) {
        return;
    }
    tick_at(monotonic_s());
}
