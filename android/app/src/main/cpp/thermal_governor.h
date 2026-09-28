/*
 * thermal_governor.h -- an opt-in thermal governor core (#557)
 *
 * On the handhelds a sustained session ends in the kernel's thermal pause.
 * On the AYN Thor, thermal-pause-F8 parks cpu3-7 when xo-therm reaches 78 C,
 * and holds until xo-therm falls below 70 C, so fps drops 5-7x in an on/off
 * cycle (#507). This governor predicts where xo-therm is heading, steps
 * quality down before the trip one rung at a time, and steps back up once
 * the device has cooled.
 *
 *   T_eq = T + tau * dT/dt, where dT/dt is the least-squares slope over 60 s
 *   down one rung: T_eq > 72 C, or a pause device set, for 60 s unbroken
 *   up one rung:   T_eq < 64 C, with no pause device set, for 300 s unbroken
 *   at most one change per 120 s
 *
 * The sensors are read from /sys/class/thermal, never through Android's
 * thermal API: on these ROMs that API reads 0 even during a pause.
 *
 * The core never reaches into the renderer. Each rung is a callback that its
 * owner registers, and a rung nobody registered is skipped. Every change is
 * logged on hakuX-perf as "[thermal557] down|up ...", so a benchmark never
 * measures an unannounced quality change.
 *
 * It is off unless HAKUX_THERMAL_ADAPT=1, and it is not hooked into the frame
 * loop yet. The hook is one call to thermal_governor_tick() per display
 * refresh (docs/lanes/remote/NOTES.md, "#557").
 */

#ifndef HAKUX_THERMAL_GOVERNOR_H
#define HAKUX_THERMAL_GOVERNOR_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The rungs, in the order they are engaged. They are released in reverse. */
typedef enum ThermalRung {
    THERMAL_RUNG_PRESENT_CAP_30,   /* cap presents at 30 fps */
    THERMAL_RUNG_SKIP_OCCLUSION,   /* skip occlusion queries */
    THERMAL_RUNG_SURFACE_SCALE_1X, /* surface scale 2x -> 1x where 2x is used */
    THERMAL_RUNG_RENDER_PASS_MODE, /* change the render-pass mode */
    THERMAL_RUNG_COUNT
} ThermalRung;

/*
 * engaged is true when the governor steps down to the rung, and false when
 * it releases it. The call is made on the thread that feeds the governor
 * (the one calling thermal_governor_tick()), once per change. Keep it cheap:
 * set a flag that the rung's owner reads at a safe point.
 */
typedef void (*ThermalRungFn)(void *opaque, bool engaged);
typedef void (*ThermalLogFn)(void *opaque, const char *line);

typedef struct ThermalRungs {
    ThermalRungFn fn[THERMAL_RUNG_COUNT];
    void *opaque[THERMAL_RUNG_COUNT];
} ThermalRungs;

typedef struct ThermalGovernorParams {
    double tau_s;          /* time constant of the T_eq prediction */
    double window_s;       /* slope window */
    double min_span_s;     /* the window must span this much to predict */
    double down_c;         /* step down above this T_eq ... */
    double down_hold_s;    /* ... held this long */
    double up_c;           /* step up below this T_eq ... */
    double up_hold_s;      /* ... held this long */
    double min_gap_s;      /* at most one change per this long */
    double gap_reset_s;    /* a silence longer than this restarts the window */
    double status_every_s; /* a "state" line this often; 0 for none */
} ThermalGovernorParams;

/* One reading. */
typedef struct ThermalSample {
    double xo_c; /* the zone's temperature in C; NAN when unread */
    int pause;   /* pause-class cooling devices above 0; -1 when unread */
    int mitig;   /* other cooling devices above 0 (logged only); -1 unread */
    int read_us; /* what the read cost (logged only); -1 when unknown */
} ThermalSample;

#define THERMAL_GOVERNOR_MAX_SAMPLES 256

typedef struct ThermalGovernor {
    ThermalGovernorParams p;
    ThermalRungs *rungs; /* &own_rungs, or a table shared with registrants */
    ThermalRungs own_rungs;
    ThermalLogFn log_fn;
    void *log_opaque;

    /* The slope window: a ring of (time, temperature). */
    double win_t[THERMAL_GOVERNOR_MAX_SAMPLES];
    double win_c[THERMAL_GOVERNOR_MAX_SAMPLES];
    int win_head, win_n;

    int engaged[THERMAL_RUNG_COUNT]; /* the rungs, in the order engaged */
    int level;                       /* how many are engaged */

    bool started;
    bool floor_logged;
    double t0, last_t, last_change_t, next_status_t;
    double hot_since, cool_since; /* NAN when not in that state */

    /* The latest reading and prediction, for the log lines. */
    ThermalSample last;
    double slope_c_s, teq_c; /* NAN until the window spans min_span_s */
    unsigned n_samples, n_bad, n_down, n_up;
} ThermalGovernor;

void thermal_governor_params_default(ThermalGovernorParams *p);
/* p may be NULL for the defaults. */
void thermal_governor_init(ThermalGovernor *g, const ThermalGovernorParams *p);
void thermal_governor_set_rung_fn(ThermalGovernor *g, ThermalRung rung,
                                  ThermalRungFn fn, void *opaque);
/* NULL logs to hakuX-perf on Android and to stderr elsewhere. */
void thermal_governor_set_log_fn(ThermalGovernor *g, ThermalLogFn fn,
                                 void *opaque);
/*
 * Feed one reading taken at now_s, in seconds on any monotonic clock.
 * Returns +1 after a step down, -1 after a step up, and 0 otherwise.
 */
int thermal_governor_feed(ThermalGovernor *g, double now_s,
                          const ThermalSample *s);
/* How many rungs have a callback. */
int thermal_governor_wired(const ThermalGovernor *g);
const char *thermal_governor_rung_name(int rung);

/* The sysfs reader: one zone found by its type, and every cooling device. */
#define THERMAL_SENSORS_MAX_PAUSE 32
#define THERMAL_SENSORS_MAX_OTHER 64

typedef struct ThermalSensors {
    int zone;    /* thermal_zone number; -1 when not found */
    int temp_fd; /* its temp file, kept open and re-read with pread() */
    int n_pause, n_other, n_skipped;
    int pause_fd[THERMAL_SENSORS_MAX_PAUSE]; /* thermal-pause-*, pause-cpu* */
    int other_fd[THERMAL_SENSORS_MAX_OTHER];
    int err; /* errno of the first failed open, 0 if none */
} ThermalSensors;

/*
 * root is normally "/sys/class/thermal". Returns 0 when a zone of type
 * zone_type was found and -1 when not. Close it either way.
 */
int thermal_sensors_open(ThermalSensors *s, const char *root,
                         const char *zone_type);
void thermal_sensors_read(const ThermalSensors *s, ThermalSample *out);
void thermal_sensors_close(ThermalSensors *s);

/*
 * The frame-loop hook. Call it once per display refresh, always from the
 * same thread. It samples at most once a second. Unless
 * HAKUX_THERMAL_ADAPT=1, it returns at once and reads nothing.
 * HAKUX_THERMAL_TAU_S overrides tau, and HAKUX_THERMAL_ZONE the zone type
 * (xo-therm).
 */
void thermal_governor_tick(void);
/*
 * For the rungs' owners: register each rung once, from any thread, before or
 * after the first tick.
 */
void thermal_governor_register_rung(ThermalRung rung, ThermalRungFn fn,
                                    void *opaque);

#ifdef __cplusplus
}
#endif

#endif /* HAKUX_THERMAL_GOVERNOR_H */
