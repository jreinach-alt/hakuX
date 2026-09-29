/*
 * thermal557_harness.c -- drives the #557 governor core on the desktop.
 *
 * It includes thermal_governor.c whole, so it can reach the process-wide
 * governor's statics (the sysfs root, the injected clock). The core is no
 * longer in the tree: #557 was stopped and its core reverted, and
 * thermal557_replay.py builds this harness against the core as it stood at
 * the fold that carried it (git history), which it writes beside the
 * harness's build. Build and run it through thermal557_replay.py, which also
 * writes the scenarios:
 *
 *   thermal557_harness feed < script   feed samples, print what happens
 *   thermal557_harness sysfs           the reader and the tick, on a fake tree
 *
 * The feed script, one command per line:
 *   param NAME VALUE    a ThermalGovernorParams field, before the first sample
 *   wire R...           wire only these rungs (default: all four)
 *   s T XO PAUSE        a sample at T seconds: XO in C or "nan", PAUSE -1/0/N
 *
 * What it prints:
 *   P T TEQ LEVEL       after every sample (TEQ "nan" until the window fills)
 *   C T RUNG 0|1        a rung callback, engaged or released
 *   L T LINE            a log line
 */

#include "thermal_governor.c" /* from git history; see above */

#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>

static double feed_now;

static void on_rung(void *opaque, bool engaged)
{
    printf("C %.3f %d %d\n", feed_now, (int)(intptr_t)opaque, engaged);
}

static void on_log(void *opaque, const char *line)
{
    (void)opaque;
    printf("L %.3f %s\n", feed_now, line);
}

static int set_param(ThermalGovernorParams *p, const char *name, double v)
{
    static const struct {
        const char *name;
        size_t off;
    } fields[] = {
#define F(x) { #x, offsetof(ThermalGovernorParams, x) }
        F(tau_s), F(window_s), F(min_span_s), F(down_c), F(down_hold_s),
        F(up_c), F(up_hold_s), F(min_gap_s), F(gap_reset_s),
        F(status_every_s),
#undef F
    };
    for (size_t i = 0; i < sizeof(fields) / sizeof(fields[0]); i++) {
        if (!strcmp(fields[i].name, name)) {
            *(double *)((char *)p + fields[i].off) = v;
            return 0;
        }
    }
    return -1;
}

static int run_feed(void)
{
    ThermalGovernorParams p;
    ThermalGovernor *g = calloc(1, sizeof(*g));
    bool wired[THERMAL_RUNG_COUNT] = { true, true, true, true };
    bool started = false;
    char line[256];
    int lineno = 0;

    thermal_governor_params_default(&p);
    while (fgets(line, sizeof(line), stdin)) {
        char name[64], xo[32];
        double t, v;
        int pause;

        lineno++;
        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        if (sscanf(line, "param %63s %lf", name, &v) == 2 && !started) {
            if (set_param(&p, name, v) < 0) {
                fprintf(stderr, "line %d: no param %s\n", lineno, name);
                return 2;
            }
        } else if (!strncmp(line, "wire", 4) && !started) {
            char *tok = strtok(line + 4, " \t\n");
            memset(wired, 0, sizeof(wired));
            for (; tok; tok = strtok(NULL, " \t\n")) {
                int r = atoi(tok);
                if (r >= 0 && r < THERMAL_RUNG_COUNT) {
                    wired[r] = true;
                }
            }
        } else if (sscanf(line, "s %lf %31s %d", &t, xo, &pause) == 3) {
            ThermalSample s = { .mitig = -1, .read_us = -1 };
            if (!started) {
                thermal_governor_init(g, &p);
                thermal_governor_set_log_fn(g, on_log, NULL);
                for (int r = 0; r < THERMAL_RUNG_COUNT; r++) {
                    if (wired[r]) {
                        thermal_governor_set_rung_fn(g, r, on_rung,
                                                     (void *)(intptr_t)r);
                    }
                }
                started = true;
            }
            s.xo_c = strcmp(xo, "nan") ? atof(xo) : NAN;
            s.pause = pause;
            feed_now = t;
            thermal_governor_feed(g, t, &s);
            printf("P %.3f %.9f %d\n", t, g->teq_c, g->level);
        } else {
            fprintf(stderr, "line %d: cannot read: %s", lineno, line);
            return 2;
        }
    }
    free(g);
    return 0;
}

/* --- the sysfs reader and the tick, against a fake /sys/class/thermal --- */

static int fails;

#define CHECK(cond, ...) do { \
    if (cond) { printf("PASS "); } else { printf("FAIL "); fails++; } \
    printf(__VA_ARGS__); printf("\n"); \
} while (0)

static void put(const char *root, const char *entry, const char *attr,
                const char *text)
{
    char path[512];
    FILE *f;

    snprintf(path, sizeof(path), "%s/%s", root, entry);
    mkdir(path, 0755);
    snprintf(path, sizeof(path), "%s/%s/%s", root, entry, attr);
    /* Truncate in place: the reader keeps the file open and re-reads it. */
    f = fopen(path, "r+");
    if (!f) {
        f = fopen(path, "w");
    }
    if (!f || ftruncate(fileno(f), 0) != 0 || fputs(text, f) < 0) {
        perror(path);
        exit(2);
    }
    fclose(f);
}

static char captured[16][512];
static int n_captured;

static void capture(void *opaque, const char *line)
{
    (void)opaque;
    if (n_captured < 16) {
        snprintf(captured[n_captured++], sizeof(captured[0]), "%s", line);
    }
}

static int engaged_calls;

static void count_rung(void *opaque, bool engaged)
{
    (void)opaque;
    engaged_calls += engaged ? 1 : -1;
}

static void reset_singleton(const char *root)
{
    if (gov_state == 1) {
        thermal_sensors_close(&sens); /* a zeroed one would close fd 0 */
    }
    memset(&registry, 0, sizeof(registry));
    memset(&gov, 0, sizeof(gov));
    memset(&sens, 0, sizeof(sens));
    sens.temp_fd = -1;
    gov_state = 0;
    gov_config_logged = false;
    gov_root = root;
    snprintf(gov_zone, sizeof(gov_zone), "xo-therm");
    gov_log_fn = capture;
    n_captured = 0;
}

static int run_sysfs(void)
{
    const char *tmp = getenv("TMPDIR");
    char root[400];
    ThermalSensors s;
    ThermalSample smp;

    snprintf(root, sizeof(root), "%s/thermal557-XXXXXX",
             tmp && *tmp ? tmp : "/tmp");
    if (!mkdtemp(root)) {
        perror("mkdtemp");
        return 2;
    }
    /* Two zones before the one wanted, and a decoy of the same type after. */
    put(root, "thermal_zone0", "type", "cpu-0-0\n");
    put(root, "thermal_zone0", "temp", "95000\n");
    put(root, "thermal_zone7", "type", "battery\n");
    put(root, "thermal_zone7", "temp", "39000\n");
    put(root, "thermal_zone90", "type", "xo-therm\n");
    put(root, "thermal_zone90", "temp", "71234\n");
    put(root, "thermal_zone91", "type", "xo-therm\n");
    put(root, "thermal_zone91", "temp", "12000\n");
    put(root, "thermal_zonex", "type", "xo-therm\n"); /* not a zone name */
    put(root, "cooling_device10", "type", "thermal-pause-F8\n");
    put(root, "cooling_device10", "cur_state", "0\n");
    put(root, "cooling_device11", "type", "pause-cpu3\n");
    put(root, "cooling_device11", "cur_state", "0\n");
    put(root, "cooling_device2", "type", "devfreq-kgsl\n");
    put(root, "cooling_device2", "cur_state", "5\n");
    put(root, "cooling_device3", "type", "cpu-hotplug3\n");
    put(root, "cooling_device3", "cur_state", "0\n");

    CHECK(thermal_sensors_open(&s, root, "xo-therm") == 0 && s.zone == 90,
          "open finds xo-therm as the lowest-numbered zone of its type "
          "(zone=%d)", s.zone);
    CHECK(s.n_pause == 2 && s.n_other == 2,
          "classifies thermal-pause-* and pause-cpu* as pause devices "
          "(pause=%d other=%d)", s.n_pause, s.n_other);
    thermal_sensors_read(&s, &smp);
    CHECK(fabs(smp.xo_c - 71.234) < 1e-9 && smp.pause == 0 && smp.mitig == 1,
          "reads milli-C and counts set devices (xo=%.3f pause=%d mitig=%d)",
          smp.xo_c, smp.pause, smp.mitig);

    put(root, "thermal_zone90", "temp", "78031\n");
    put(root, "cooling_device10", "cur_state", "1\n");
    thermal_sensors_read(&s, &smp);
    CHECK(fabs(smp.xo_c - 78.031) < 1e-9 && smp.pause == 1,
          "re-reads the open files after an in-place change "
          "(xo=%.3f pause=%d)", smp.xo_c, smp.pause);

    put(root, "thermal_zone90", "temp", "garbage\n");
    thermal_sensors_read(&s, &smp);
    CHECK(isnan(smp.xo_c), "an unparsable temp is unread");
    put(root, "thermal_zone90", "temp", "4500000\n");
    thermal_sensors_read(&s, &smp);
    CHECK(isnan(smp.xo_c), "an out-of-range temp (4500 C) is unread");
    thermal_sensors_close(&s);

    CHECK(thermal_sensors_open(&s, root, "no-such-zone") < 0 && s.zone < 0,
          "open reports a missing zone type");
    thermal_sensors_close(&s);
    CHECK(thermal_sensors_open(&s, "/nonexistent-thermal557", "xo-therm") < 0 &&
          s.err == ENOENT, "open reports an unreadable root with its errno");
    thermal_sensors_close(&s);

    /* The tick: off unless HAKUX_THERMAL_ADAPT=1, and then silent. */
    put(root, "thermal_zone90", "temp", "60000\n");
    put(root, "cooling_device10", "cur_state", "0\n");
    unsetenv("HAKUX_THERMAL_ADAPT");
    reset_singleton(root);
    tick_at(1000.0);
    tick_at(1001.0);
    CHECK(gov_state == -1 && sens.temp_fd == -1 && n_captured == 0,
          "tick without HAKUX_THERMAL_ADAPT: off, nothing opened, nothing "
          "logged");
    setenv("HAKUX_THERMAL_ADAPT", "0", 1);
    reset_singleton(root);
    tick_at(1000.0);
    CHECK(gov_state == -1, "HAKUX_THERMAL_ADAPT=0 is off");

    setenv("HAKUX_THERMAL_ADAPT", "1", 1);
    setenv("HAKUX_THERMAL_TAU_S", "300", 1);
    reset_singleton(root);
    thermal_governor_register_rung(THERMAL_RUNG_PRESENT_CAP_30, count_rung,
                                   NULL);
    tick_at(1000.0);
    CHECK(gov_state == 1 && sens.zone == 90 && gov.p.tau_s == 300.0 &&
          gov.rungs == &registry,
          "HAKUX_THERMAL_ADAPT=1 opens the zone, takes HAKUX_THERMAL_TAU_S, "
          "and keeps a rung registered before the first tick");
    tick_at(1000.5);
    CHECK(gov.n_samples == 1, "samples at most once a second (n=%u)",
          gov.n_samples);
    thermal_governor_register_rung(THERMAL_RUNG_SKIP_OCCLUSION, count_rung,
                                   NULL);
    CHECK(thermal_governor_wired(&gov) == 2,
          "a rung registered after the first tick is wired too");
    for (int i = 1; i < 29; i++) {
        tick_at(1000.0 + i);
    }
    CHECK(n_captured == 0, "no line before one status interval (%d)",
          n_captured);
    /* A steep climb from here: 60 C, then +0.1 C a second. */
    for (int i = 29; i <= 160; i++) {
        char temp[32];
        snprintf(temp, sizeof(temp), "%d\n", 60000 + (i - 28) * 100);
        put(root, "thermal_zone90", "temp", temp);
        tick_at(1000.0 + i);
    }
    CHECK(n_captured >= 2 && !strncmp(captured[0], "[thermal557] config ", 20),
          "the first line is the config line: %s",
          n_captured ? captured[0] : "(none)");
    CHECK(strstr(captured[0], "zone=xo-therm tz=90 pause_dev=2 cdev=2") &&
          strstr(captured[0], "tau=300") &&
          strstr(captured[0], "wired=cap30,no-occl"),
          "the config line names the zone, the devices, tau and the wiring");
    CHECK(engaged_calls == 1 && gov.level == 1,
          "the climb engages the first rung through the registry "
          "(calls=%d level=%d)", engaged_calls, gov.level);

    setenv("HAKUX_THERMAL_ZONE", "no-such-zone", 1);
    reset_singleton(root);
    tick_at(1000.0);
    tick_at(1001.0);
    CHECK(gov_state == -1 && n_captured == 1 &&
          strstr(captured[0], "off: no readable zone of type no-such-zone"),
          "a missing zone turns it off with one line: %s",
          n_captured ? captured[0] : "(none)");
    unsetenv("HAKUX_THERMAL_ZONE");
    unsetenv("HAKUX_THERMAL_TAU_S");
    unsetenv("HAKUX_THERMAL_ADAPT");

    {
        char cmd[600];
        snprintf(cmd, sizeof(cmd), "rm -rf '%s'", root);
        if (system(cmd) != 0) {
            fprintf(stderr, "could not remove %s\n", root);
        }
    }
    printf("%s: %d failed\n", fails ? "FAIL" : "PASS", fails);
    return fails ? 1 : 0;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "feed")) {
        return run_feed();
    }
    if (argc == 2 && !strcmp(argv[1], "sysfs")) {
        return run_sysfs();
    }
    fprintf(stderr, "usage: %s feed|sysfs\n", argv[0]);
    return 2;
}
