/*
 * #433 [pmu433]: what the CPU's own counters say about the vCPU thread.
 *
 * Off unless HAKUX_PMU is set; unset costs one load and a branch at the
 * [tlb68] gate (1 in 1024 loop returns) and opens nothing.
 *
 *   HAKUX_PMU=1         count, one line per ~1 s slice
 *   HAKUX_PMU_CTL=1     first, run the control kernels below on this thread
 *                       through the same counters, one line each
 *   HAKUX_PMU_GSZ=N     events per group, cycles and instructions included
 *                       (default 5, 3..7); see GROUPS
 *   HAKUX_PMU_EVS=a,b   the events after cycles and instructions (hex PMUv3
 *                       numbers), replacing the default list below
 *   HAKUX_PMU_PERCPU=0  one counter set for every CPU instead of one per CPU
 *   HAKUX_PMU=2         sample instead (R2): HAKUX_PMU_EV is a list of up to
 *                       four raw events, each hex with an optional decimal
 *                       period (`11:1500000,22:20000`; default 11 = cycles),
 *                       sampled every that many of its own events (default
 *                       HAKUX_PMU_PERIOD, else 100000); see SAMPLING
 *
 * ONE PMU, MANY CORE TYPES. The SD 8 Gen 2 has A510 (cpu0-2), A715 (cpu3-4),
 * A710 (cpu5-6) and X3 (cpu7), and both handhelds' kernels expose them as ONE
 * event source, armv8_pmuv3 (type 8, cpus 0-7; R0, Thor 10-05 and Nova
 * 10-09). A per-thread event then counts on whatever core the thread is on and
 * a slice mixes core types. So by default each group is opened once per CPU
 * (pid = this thread, cpu = N): such an event is scheduled only while the
 * thread runs on CPU N, the groups of different CPUs never compete for a
 * counter, and each unit's running time is the thread's time on that CPU.
 * The unit is named "c<cpu>-<core>" from /proc/cpuinfo's CPU part. Where an
 * SoC exposes one source per core type, every source gets its units the same
 * way, restricted to its own `cpus`.
 *
 * GROUPS. A PMU counts a group only if all of it fits at once. R0 on the Nova
 * (10-09, pmuprobe sched) read the largest group that ever runs as 5 events
 * on the A715 and the A510: 6 and 7 open without error and never run
 * (time_running stays 0), 8 or more fail EINVAL. So each group is cycles +
 * instructions + (GSZ - 2) events, by default
 *
 *   g0  cyc ins sfe sbe brm    0x11 0x08 0x23 0x24 0x22
 *   g1  cyc ins l1i itl iwk    0x11 0x08 0x01 0x02 0x35
 *   g2  cyc ins l1d dtl dwk    0x11 0x08 0x03 0x05 0x34
 *   g3  cyc ins l2d l3d brr    0x11 0x08 0x17 0x2a 0x21
 *   g4  cyc ins bis l1ia l1da  0x11 0x08 0x7a 0x14 0x04
 *
 * multiplexed by the kernel. Every group carries cycles and instructions, so a
 * ratio is always taken inside one group, exact over that group's running
 * time. sfe/sbe STALL_FRONTEND/BACKEND (cycles), brm BR_MIS_PRED_RETIRED, brr
 * BR_RETIRED, bis BR_INDIRECT_SPEC, l1i/itl/l1d/dtl/l2d/l3d the L1I, L1I TLB,
 * L1D, L1D TLB, L2D and L3D refills, iwk/dwk ITLB/DTLB walks, l1ia/l1da L1I/L1D
 * accesses. One `[pmu433] layout` line names the groups; the reader takes the
 * event names from it. User mode only (exclude_kernel), which is where the JIT
 * runs and all that perf_event_paranoid 1 or 2 allows.
 *
 * Software counters (any CPU): task-clock ns, context switches, migrations.
 *
 * Per slice, from g_nv2a_stats (written by the pgraph thread, read racily;
 * telemetry): fr frames flipped in the slice and fmax the longest of them in
 * ms, so a slow window (> 33 ms) is read apart from a good one on the same
 * line. cpus is the set of CPUs getcpu saw at the gate.
 *
 * A failed open is a result, not an error: the line names errno and
 * perf_event_paranoid (3 after a reboot until `setprop security.perf_harden
 * 0`; EACCES then) and the thread runs on with the counters off.
 */
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sched.h>
#include <dirent.h>
#include <errno.h>
#include <dlfcn.h>

#ifndef PMU433_LOG
#define PMU433_LOG(...) JC425_LOG(__VA_ARGS__)
#endif

#define PMU433_MAXSRC 4
#define PMU433_MAXUNIT 16
#define PMU433_MAXCPU 16
#define PMU433_NGRP 8
#define PMU433_NEV 7
#define PMU433_MAXEV 24
#define PMU433_NSEV 4
#define PMU433_RING_PAGES 128
/* a log line's payload stays under the 1024 bytes Android formats into */
#ifndef PMU433_LINE
#define PMU433_LINE 1000
#endif

/* The events after cycles and instructions, in group order. */
static const uint16_t pmu433_evdef[] = {
    0x23, 0x24, 0x22,       /* STALL_FRONTEND, STALL_BACKEND, BR_MIS_PRED_RET */
    0x01, 0x02, 0x35,       /* L1I_CACHE_REFILL, L1I_TLB_REFILL, ITLB_WALK */
    0x03, 0x05, 0x34,       /* L1D_CACHE_REFILL, L1D_TLB_REFILL, DTLB_WALK */
    0x17, 0x2a, 0x21,       /* L2D_CACHE_REFILL, L3D_CACHE_REFILL, BR_RETIRED */
    0x7a, 0x14, 0x04,       /* BR_INDIRECT_SPEC, L1I_CACHE, L1D_CACHE */
};

/* An event source with a `cpus` file (arm_pmu's). */
typedef struct {
    char name[32];
    int type;
    char cpus[24];
} Pmu433Src;

/* One counter set: a source on one CPU (cpu >= 0) or on any CPU (-1). */
typedef struct {
    char name[40];
    int type, cpu;
    bool sub[PMU433_NGRP][PMU433_NEV];    /* refused; slot counts ins */
    int fd[PMU433_NGRP][PMU433_NEV];      /* [g][0] is the leader */
    uint64_t prev[PMU433_NGRP][2 + PMU433_NEV];  /* en, run, values */
    struct perf_event_mmap_page *ring[PMU433_NGRP];  /* mode 2, per event */
} Pmu433Unit;

static int pmu433_state;        /* 0 unread, 1 counting, -1 off */
static int pmu433_mode;         /* 1 count, 2 sample */
static uint64_t pmu433_sper = 100000;              /* the default period */
static uint64_t pmu433_sperg[PMU433_NGRP];        /* each sampled event's */
static Pmu433Src pmu433_src[PMU433_MAXSRC];
static int pmu433_nsrc;
static Pmu433Unit pmu433_unit[PMU433_MAXUNIT];
static int pmu433_nunit;
static int pmu433_ngrp;                           /* the layout, every unit */
static int pmu433_nev[PMU433_NGRP];
static uint16_t pmu433_ev[PMU433_NGRP][PMU433_NEV];
static char pmu433_core[PMU433_MAXCPU][8];        /* "x3", "a510", ... */
static int pmu433_sw[3] = { -1, -1, -1 };
static uint64_t pmu433_swprev[3];

/* sched_getcpu() needs _GNU_SOURCE before the first <sched.h>; the syscall
 * does not. */
static int pmu433_getcpu(void)
{
    unsigned cpu = 0;
    return syscall(__NR_getcpu, &cpu, NULL, NULL) ? -1 : (int)cpu;
}

static int pmu433_open(struct perf_event_attr *a, int cpu, int group)
{
    return (int)syscall(__NR_perf_event_open, a, 0, cpu, group,
                        PERF_FLAG_FD_CLOEXEC);
}

static void pmu433_attr(struct perf_event_attr *a, uint32_t type,
                        uint64_t config, bool leader)
{
    memset(a, 0, sizeof(*a));
    a->size = sizeof(*a);
    a->type = type;
    a->config = config;
    a->disabled = leader;
    a->exclude_kernel = 1;
    a->exclude_hv = 1;
    a->read_format = PERF_FORMAT_GROUP | PERF_FORMAT_TOTAL_TIME_ENABLED |
                     PERF_FORMAT_TOTAL_TIME_RUNNING;
#ifdef PMU433_TEST_SW
    /* host test of the plumbing only (pmuprobe built with -DPMU433_TEST_SW) */
    if (type != PERF_TYPE_SOFTWARE) {
        a->type = PERF_TYPE_SOFTWARE;
        a->config = PERF_COUNT_SW_TASK_CLOCK;
    }
#endif
}

static bool pmu433_readfile(const char *path, char *buf, size_t n)
{
    FILE *f = fopen(path, "r");
    if (!f) {
        return false;
    }
    bool ok = fgets(buf, (int)n, f) != NULL;
    fclose(f);
    if (ok) {
        buf[strcspn(buf, "\n")] = 0;
    }
    return ok;
}

/* The core-type PMUs: an event_source with a `cpus` file. */
static void pmu433_find(void)
{
    DIR *d = opendir("/sys/bus/event_source/devices");
    struct dirent *e;
    char path[160], buf[64];

    if (!d) {
        PMU433_LOG("[pmu433] sysfs event_source unreadable errno=%d; "
                   "falling back to PERF_TYPE_RAW", errno);
    }
    while (d && (e = readdir(d)) && pmu433_nsrc < PMU433_MAXSRC) {
        Pmu433Src *p = &pmu433_src[pmu433_nsrc];
        if (e->d_name[0] == '.') {
            continue;
        }
        snprintf(path, sizeof(path), "/sys/bus/event_source/devices/%.100s/cpus",
                 e->d_name);
        if (!pmu433_readfile(path, p->cpus, sizeof(p->cpus))) {
            continue;
        }
        snprintf(path, sizeof(path), "/sys/bus/event_source/devices/%.100s/type",
                 e->d_name);
        if (!pmu433_readfile(path, buf, sizeof(buf))) {
            continue;
        }
        p->type = atoi(buf);
        snprintf(p->name, sizeof(p->name), "%.31s", e->d_name);
        pmu433_nsrc++;
    }
    if (d) {
        closedir(d);
    }
    if (!pmu433_nsrc) {
        Pmu433Src *p = &pmu433_src[0];
        snprintf(p->name, sizeof(p->name), "raw");
        snprintf(p->cpus, sizeof(p->cpus), "?");
#ifdef PMU433_TEST_SW
        /* the host test: exercise the per-CPU units with software events */
        snprintf(p->cpus, sizeof(p->cpus), "0-%ld",
                 sysconf(_SC_NPROCESSORS_ONLN) - 1);
#endif
        p->type = PERF_TYPE_RAW;
        pmu433_nsrc = 1;
    }
}

/* Each CPU's core type from /proc/cpuinfo's CPU part (Arm's part numbers). */
static void pmu433_cores(void)
{
    static const struct { uint16_t part; const char *name; } parts[] = {
        { 0xd05, "a55" }, { 0xd0b, "a76" }, { 0xd0d, "a77" },
        { 0xd41, "a78" }, { 0xd44, "x1" }, { 0xd46, "a510" },
        { 0xd47, "a710" }, { 0xd48, "x2" }, { 0xd4d, "a715" },
        { 0xd4e, "x3" }, { 0xd80, "a520" }, { 0xd81, "a720" },
        { 0xd82, "x4" },
    };
    FILE *f = fopen("/proc/cpuinfo", "r");
    char line[160], buf[PMU433_MAXCPU * 10] = "";
    int cpu = -1, off = 0;
    unsigned part;

    for (int c = 0; c < PMU433_MAXCPU; c++) {
        snprintf(pmu433_core[c], sizeof(pmu433_core[c]), "?");
    }
    while (f && fgets(line, sizeof(line), f)) {
        if (sscanf(line, "processor : %d", &cpu) == 1) {
            continue;
        }
        if (cpu < 0 || cpu >= PMU433_MAXCPU ||
            sscanf(line, "CPU part : %x", &part) != 1) {
            continue;
        }
        snprintf(pmu433_core[cpu], sizeof(pmu433_core[cpu]), "p%03x", part);
        for (size_t k = 0; k < sizeof(parts) / sizeof(parts[0]); k++) {
            if (parts[k].part == part) {
                snprintf(pmu433_core[cpu], sizeof(pmu433_core[cpu]), "%s",
                         parts[k].name);
            }
        }
    }
    if (f) {
        fclose(f);
    }
    for (int c = 0; c < PMU433_MAXCPU; c++) {
        if (strcmp(pmu433_core[c], "?")) {
            off += snprintf(buf + off, sizeof(buf) - off, " %d=%s", c,
                            pmu433_core[c]);
        }
    }
    PMU433_LOG("[pmu433] cores%s", buf);
}

/* "0-2,5" -> bits; "?" or unparsable -> 0 */
static uint64_t pmu433_cpulist(const char *s)
{
    uint64_t m = 0;
    while (*s >= '0' && *s <= '9') {
        char *end;
        long a = strtol(s, &end, 10), b = a;
        if (*end == '-') {
            b = strtol(end + 1, &end, 10);
        }
        for (long c = a; c <= b && c < 64; c++) {
            m |= 1ull << c;
        }
        s = *end == ',' ? end + 1 : end;
    }
    return m;
}

/* hex list "23,24:5000,0x22" -> out[] (and per[], the decimal after `:`,
 * else 0), at most n; returns the count */
static int pmu433_hexlist(const char *s, uint16_t *out, uint64_t *per, int n)
{
    int k = 0;
    while (s && *s && k < n) {
        char *end;
        unsigned long v = strtoul(s, &end, 16);
        if (end == s) {
            break;
        }
        if (per) {
            per[k] = *end == ':' ? strtoull(end + 1, &end, 10) : 0;
        }
        out[k++] = (uint16_t)v;
        s = *end == ',' ? end + 1 : end;
    }
    return k;
}

/* The groups every unit opens, and the one line that names them. */
static void pmu433_layout(void)
{
    uint16_t evs[PMU433_MAXEV];
    int nevs = 0, gsz = 5, off;
    const char *e;
    char buf[512];

    if (pmu433_mode == 2) {
        /* each sampled event leads its own group; cycles, ins follow */
        e = getenv("HAKUX_PMU_EV");
        nevs = pmu433_hexlist(e && *e ? e : "11", evs, pmu433_sperg,
                              PMU433_NSEV);
        for (int g = 0; g < nevs; g++) {
            pmu433_sperg[g] = pmu433_sperg[g] ? pmu433_sperg[g] : pmu433_sper;
            pmu433_nev[g] = 3;
            pmu433_ev[g][0] = evs[g];
            pmu433_ev[g][1] = 0x11;
            pmu433_ev[g][2] = 0x08;
        }
        pmu433_ngrp = nevs;
    } else {
        e = getenv("HAKUX_PMU_EVS");
        if (e && *e) {
            nevs = pmu433_hexlist(e, evs, NULL, PMU433_MAXEV);
        } else {
            nevs = sizeof(pmu433_evdef) / sizeof(pmu433_evdef[0]);
            memcpy(evs, pmu433_evdef, sizeof(pmu433_evdef));
        }
        e = getenv("HAKUX_PMU_GSZ");
        if (e && *e) {
            gsz = atoi(e);
        }
        gsz = gsz < 3 ? 3 : gsz > PMU433_NEV ? PMU433_NEV : gsz;
        pmu433_ngrp = 0;
        for (int i = 0; i < nevs && pmu433_ngrp < PMU433_NGRP; i += gsz - 2) {
            int g = pmu433_ngrp++;
            pmu433_nev[g] = 2;
            pmu433_ev[g][0] = 0x11;
            pmu433_ev[g][1] = 0x08;
            for (int k = i; k < i + gsz - 2 && k < nevs; k++) {
                pmu433_ev[g][pmu433_nev[g]++] = evs[k];
            }
        }
        if (nevs > pmu433_ngrp * (gsz - 2)) {
            PMU433_LOG("[pmu433] layout: %d events dropped (at most %d groups)",
                       nevs - pmu433_ngrp * (gsz - 2), PMU433_NGRP);
        }
    }
    off = snprintf(buf, sizeof(buf), "[pmu433] layout mode=%d gsz=%d",
                   pmu433_mode, gsz);
    for (int g = 0; g < pmu433_ngrp && off < (int)sizeof(buf); g++) {
        off += snprintf(buf + off, sizeof(buf) - off, " g%d=", g);
        for (int k = 0; k < pmu433_nev[g] && off < (int)sizeof(buf); k++) {
            off += snprintf(buf + off, sizeof(buf) - off, "%s%02x",
                            k ? "," : "", pmu433_ev[g][k]);
        }
    }
    PMU433_LOG("%s", buf);
}

/* The units: every source on each of its CPUs, or once on any CPU. */
static void pmu433_units(bool percpu)
{
    pmu433_nunit = 0;
    for (int s = 0; s < pmu433_nsrc; s++) {
        uint64_t m = percpu ? pmu433_cpulist(pmu433_src[s].cpus) : 0;
        for (int c = 0; c < PMU433_MAXCPU && pmu433_nunit < PMU433_MAXUNIT;
             c++) {
            if (!(m >> c & 1)) {
                continue;
            }
            Pmu433Unit *u = &pmu433_unit[pmu433_nunit++];
            memset(u, 0, sizeof(*u));
            snprintf(u->name, sizeof(u->name), "c%d-%.7s", c, pmu433_core[c]);
            u->type = pmu433_src[s].type;
            u->cpu = c;
        }
        if (!m && pmu433_nunit < PMU433_MAXUNIT) {
            Pmu433Unit *u = &pmu433_unit[pmu433_nunit++];
            memset(u, 0, sizeof(*u));
            snprintf(u->name, sizeof(u->name), "%.31s", pmu433_src[s].name);
            u->type = pmu433_src[s].type;
            u->cpu = -1;
        }
    }
}

static void pmu433_close(Pmu433Unit *u, int g)
{
    for (int k = 0; k < PMU433_NEV; k++) {
        if (u->fd[g][k] >= 0) {
            close(u->fd[g][k]);
        }
        u->fd[g][k] = -1;
    }
}

/* Open one unit's groups; returns how many opened, `res` says what failed. */
static int pmu433_open_unit(Pmu433Unit *u, char *res, size_t rn)
{
    struct perf_event_attr a;
    int opened = 0, off = 0;

    res[0] = 0;
    for (int g = 0; g < pmu433_ngrp; g++) {
        int err = 0;
        for (int k = 0; k < PMU433_NEV; k++) {
            u->fd[g][k] = -1;
        }
        for (int k = 0; k < pmu433_nev[g] && !err; k++) {
            pmu433_attr(&a, u->type, pmu433_ev[g][k], k == 0);
            if (k == 0 && pmu433_mode == 2) {
                a.sample_period = pmu433_sperg[g];
                a.sample_type = PERF_SAMPLE_IP | PERF_SAMPLE_CPU;
            }
            u->fd[g][k] = pmu433_open(&a, u->cpu, k ? u->fd[g][0] : -1);
            if (u->fd[g][k] < 0 && k > 0) {
                /*
                 * A follower this core does not count: keep the group,
                 * count instructions in its slot and print it as `x`.
                 */
                off += snprintf(res + off, rn - off, " g%d:ev%02x:errno%d",
                                g, pmu433_ev[g][k], errno);
                u->sub[g][k] = true;
                pmu433_attr(&a, u->type, 0x08, false);
                u->fd[g][k] = pmu433_open(&a, u->cpu, u->fd[g][0]);
            }
            if (u->fd[g][k] < 0) {
                err = errno;
                off += snprintf(res + off, rn - off, " g%d:ev%02x:errno%d",
                                g, pmu433_ev[g][k], err);
            }
        }
        if (err) {
            pmu433_close(u, g);
            continue;
        }
        if (pmu433_mode == 2) {
            size_t len = (1 + PMU433_RING_PAGES) * getpagesize();
            u->ring[g] = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_SHARED,
                              u->fd[g][0], 0);
            if (u->ring[g] == MAP_FAILED) {
                u->ring[g] = NULL;
                off += snprintf(res + off, rn - off, " g%d:mmap:errno%d", g,
                                errno);
            }
        }
        ioctl(u->fd[g][0], PERF_EVENT_IOC_RESET, PERF_IOC_FLAG_GROUP);
        ioctl(u->fd[g][0], PERF_EVENT_IOC_ENABLE, PERF_IOC_FLAG_GROUP);
        opened++;
    }
    return opened;
}

static void pmu433_start(void)
{
    struct perf_event_attr a;
    char par[16] = "?", res[256];
    const char *e = getenv("HAKUX_PMU_PERCPU");
    bool percpu = pmu433_mode == 1 && !(e && !strcmp(e, "0"));
    int opened = 0;

    pmu433_readfile("/proc/sys/kernel/perf_event_paranoid", par, sizeof(par));
    pmu433_find();
    pmu433_cores();
    pmu433_layout();
    for (int pass = 0; pass < 2 && !opened; pass++) {
        pmu433_units(percpu);
        for (int i = 0; i < pmu433_nunit; i++) {
            Pmu433Unit *u = &pmu433_unit[i];
            int n = pmu433_open_unit(u, res, sizeof(res));
            opened += n;
            PMU433_LOG("[pmu433] open unit=%s type=%d cpu=%d mode=%d "
                       "groups=%d/%d%s%s paranoid=%s tid=%d", u->name,
                       u->type, u->cpu, pmu433_mode, n, pmu433_ngrp,
                       res[0] ? " failed:" : "", res, par, (int)gettid());
        }
        if (!opened && percpu) {
            /* a kernel that refuses a per-CPU task event: count on any CPU */
            PMU433_LOG("[pmu433] open: no per-CPU group opened; "
                       "counting on any CPU instead");
            percpu = false;
        }
    }

    static const uint64_t swc[3] = {
        PERF_COUNT_SW_TASK_CLOCK, PERF_COUNT_SW_CONTEXT_SWITCHES,
        PERF_COUNT_SW_CPU_MIGRATIONS,
    };
    /*
     * Switches and migrations happen in the scheduler, in kernel mode, so
     * with exclude_kernel they never count (r0 on the Nova read cs=0 mig=0
     * while the thread visited five CPUs in a slice). They are counted with
     * the kernel included where paranoid allows it (<= 1), else excluded
     * and logged as `kern=0`.
     */
    bool kern = true;
    for (int k = 0; k < 3; k++) {
        pmu433_attr(&a, PERF_TYPE_SOFTWARE, swc[k], false);
        a.read_format = 0;
        a.exclude_kernel = k ? 0 : 1;
        pmu433_sw[k] = pmu433_open(&a, -1, -1);
        if (pmu433_sw[k] < 0 && k) {
            a.exclude_kernel = 1;
            pmu433_sw[k] = pmu433_open(&a, -1, -1);
            kern = false;
        }
    }
    PMU433_LOG("[pmu433] open sw task=%d cs=%d mig=%d kern=%d groups=%d "
               "units=%d", pmu433_sw[0] >= 0, pmu433_sw[1] >= 0,
               pmu433_sw[2] >= 0, kern, opened, pmu433_nunit);
    pmu433_state = opened ? 1 : -1;
}

/*
 * A group that reads short, with the wrong nr, or never gets a counter while
 * its unit's other groups do, reads as zero, and a zero is silent in the
 * slice line. So the first dozen such reads are logged (errno and the raw
 * nr / enabled / running), and a reader can tell an unreadable group from one
 * the PMU cannot schedule. A per-CPU unit whose CPU the thread never visited
 * is not one of them: all its groups read running 0, which is its record.
 */
static int pmu433_nodiag = 12;

static void pmu433_diag(const Pmu433Unit *u, int g, ssize_t got, int err,
                        const uint64_t *r)
{
    if (pmu433_nodiag <= 0) {
        return;
    }
    pmu433_nodiag--;
    if (got < 3 * (ssize_t)sizeof(uint64_t)) {
        PMU433_LOG("[pmu433] read unit=%s g%d got=%lld errno=%d",
                   u->name, g, (long long)got, got < 0 ? err : 0);
        return;
    }
    PMU433_LOG("[pmu433] read unit=%s g%d got=%lld nr=%llu en=%llu run=%llu",
               u->name, g, (long long)got, (unsigned long long)r[0],
               (unsigned long long)r[1], (unsigned long long)r[2]);
}

/*
 * Read every group of every unit; out[i][g] gets the deltas since the last
 * read (en, run, values) and prev is advanced. A group that did not open or
 * read short reads as all zero.
 */
static void pmu433_read(uint64_t out[PMU433_MAXUNIT][PMU433_NGRP]
                                    [2 + PMU433_NEV])
{
    for (int i = 0; i < pmu433_nunit; i++) {
        Pmu433Unit *u = &pmu433_unit[i];
        uint64_t maxrun = 0;
        for (int g = 0; g < pmu433_ngrp; g++) {
            /* nr, time_enabled, time_running, values[nr] */
            uint64_t r[3 + PMU433_NEV];
            ssize_t want = (3 + pmu433_nev[g]) * sizeof(uint64_t);
            memset(out[i][g], 0, sizeof(out[i][g]));
            if (u->fd[g][0] < 0) {
                continue;
            }
            ssize_t got = read(u->fd[g][0], r, want);
            int err = errno;
            if (got != want || r[0] != (uint64_t)pmu433_nev[g]) {
                pmu433_diag(u, g, got, err, r);
                continue;
            }
            for (int k = 0; k < 2 + pmu433_nev[g]; k++) {
                out[i][g][k] = r[1 + k] - u->prev[g][k];
                u->prev[g][k] = r[1 + k];
            }
            maxrun = out[i][g][1] > maxrun ? out[i][g][1] : maxrun;
        }
        /* the unit ran >= 50 ms and a group of it never did */
        for (int g = 0; g < pmu433_ngrp && maxrun >= 50000000; g++) {
            if (u->fd[g][0] >= 0 && out[i][g][0] && !out[i][g][1]) {
                uint64_t r[3] = { pmu433_nev[g], out[i][g][0], 0 };
                pmu433_diag(u, g, sizeof(r), 0, r);
            }
        }
    }
}

static bool pmu433_ran(uint64_t d[PMU433_NGRP][2 + PMU433_NEV])
{
    for (int g = 0; g < pmu433_ngrp; g++) {
        if (d[g][1]) {
            return true;
        }
    }
    return false;
}

/*
 * One unit's groups as " p=NAME g0=RUNMS:v,v,... g1=...", a refused follower
 * as `x`. Mode 2 prints each sampled group as gN=RUNMS:sampled,cyc,ins.
 */
static int pmu433_fmt(char *buf, size_t n, int i,
                      uint64_t d[PMU433_NGRP][2 + PMU433_NEV])
{
    Pmu433Unit *u = &pmu433_unit[i];
    int off = snprintf(buf, n, " p=%s", u->name);
    for (int g = 0; g < pmu433_ngrp && off < (int)n; g++) {
        off += snprintf(buf + off, n - off, " g%d=%.1f", g, d[g][1] / 1e6);
        for (int k = 0; k < pmu433_nev[g] && off < (int)n; k++) {
            if (u->sub[g][k]) {
                off += snprintf(buf + off, n - off, "%cx", k ? ',' : ':');
            } else {
                off += snprintf(buf + off, n - off, "%c%" PRIu64,
                                k ? ',' : ':', d[g][2 + k]);
            }
        }
    }
    return off < (int)n ? off : (int)n - 1;
}

static uint64_t pmu433_swread(int k)
{
    uint64_t v = 0;
    if (pmu433_sw[k] < 0 || read(pmu433_sw[k], &v, sizeof(v)) != sizeof(v)) {
        return 0;
    }
    uint64_t d = v - pmu433_swprev[k];
    pmu433_swprev[k] = v;
    return d;
}

/* ---- control kernels: known IPC, mispredict rate and miss rates ---- */

static volatile uint64_t pmu433_sink;

static uint64_t pmu433_k_alu1(uint64_t n)
{
    uint64_t x = 0;
    for (uint64_t i = 0; i < n; i++) {
#if defined(__aarch64__)
        /* 64 dependent adds: one per cycle at add latency 1 */
#define A1 "add %0, %0, #1\n\t"
#define A8 A1 A1 A1 A1 A1 A1 A1 A1
        __asm__ volatile(A8 A8 A8 A8 A8 A8 A8 A8 : "+r"(x));
#undef A8
#undef A1
#else
        x += 64;
#endif
    }
    return x;
}

static uint64_t pmu433_k_mul1(uint64_t n)
{
    uint64_t x = 3;
    for (uint64_t i = 0; i < n; i++) {
#if defined(__aarch64__)
        /* 64 dependent multiplies: latency 2 on X3/A715 */
#define M1 "mul %0, %0, %0\n\t"
#define M8 M1 M1 M1 M1 M1 M1 M1 M1
        __asm__ volatile(M8 M8 M8 M8 M8 M8 M8 M8 : "+r"(x));
#undef M8
#undef M1
#else
        x *= x;
#endif
    }
    return x;
}

/* Computed goto among `mask + 1` targets picked by xorshift: an indirect
 * branch whose target is random, so (mask) / (mask + 1) of them mispredict. */
static uint64_t pmu433_k_ind(uint64_t n, unsigned mask)
{
    static void *const tgt[8] = { &&t0, &&t1, &&t2, &&t3,
                                  &&t4, &&t5, &&t6, &&t7 };
    uint64_t s = 0x9e3779b97f4a7c15ull, acc = 0, i = 0;

next:
    if (i++ == n) {
        return acc;
    }
    s ^= s << 13; s ^= s >> 7; s ^= s << 17;
    goto *tgt[(s >> 29) & mask];
t0: acc += 1; goto next;
t1: acc += 3; goto next;
t2: acc += 5; goto next;
t3: acc += 7; goto next;
t4: acc += 11; goto next;
t5: acc += 13; goto next;
t6: acc += 17; goto next;
t7: acc += 19; goto next;
}

/*
 * Pointer chase over a random cycle of 64-byte lines spanning `bytes`. The
 * ring is built before the counters are read: on r0 the build (a shuffle
 * and a link pass, ~2/3 of chase64m's instructions, each line a miss) sat
 * inside the window and the per-load L1D/L2D refill counts could not be
 * judged.
 */
static void **pmu433_chase_prep(size_t bytes)
{
    size_t lines = bytes / 64;
    char *m = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    uint32_t *perm;
    uint64_t s = 0x2545f4914f6cdd1dull;

    if (m == MAP_FAILED) {
        return NULL;
    }
    perm = g_new(uint32_t, lines);
    for (size_t i = 0; i < lines; i++) {
        perm[i] = (uint32_t)i;
    }
    for (size_t i = lines - 1; i > 0; i--) {
        s ^= s << 13; s ^= s >> 7; s ^= s << 17;
        size_t j = s % (i + 1);
        uint32_t t = perm[i]; perm[i] = perm[j]; perm[j] = t;
    }
    for (size_t i = 0; i < lines; i++) {
        *(void **)(m + (size_t)perm[i] * 64) =
            m + (size_t)perm[(i + 1) % lines] * 64;
    }
    g_free(perm);
    return (void **)m;
}

static uint64_t pmu433_k_chase(void **p, uint64_t n)
{
    if (!p) {
        return 0;
    }
    for (uint64_t i = 0; i < n; i++) {
        p = (void **)*p;
    }
    pmu433_sink = (uintptr_t)p;
    return n;
}

/*
 * Instruction footprint: `blocks` 64-byte blocks (15 NOPs + B next) chained
 * in a random order and ending in RET, called n times. Footprint larger than
 * L1I (64 KB on X3/A715) refills about once per block; 16 KB does not.
 */
static uint64_t pmu433_k_code(uint64_t n, unsigned blocks)
{
#if defined(__aarch64__)
    size_t bytes = (size_t)blocks * 64;
    uint32_t *c = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    uint32_t *order = g_new(uint32_t, blocks);
    uint64_t s = 0x853c49e6748fea9bull;

    if (c == MAP_FAILED) {
        g_free(order);
        return 0;
    }
    for (unsigned i = 0; i < blocks; i++) {
        order[i] = i;
    }
    for (unsigned i = blocks - 1; i > 1; i--) {   /* keep block 0 first */
        s ^= s << 13; s ^= s >> 7; s ^= s << 17;
        unsigned j = 1 + s % i;
        uint32_t t = order[i]; order[i] = order[j]; order[j] = t;
    }
    for (unsigned i = 0; i < blocks; i++) {
        uint32_t *b = c + order[i] * 16;
        for (int k = 0; k < 15; k++) {
            b[k] = 0xd503201f;                       /* NOP */
        }
        if (i + 1 < blocks) {
            int32_t off = (int32_t)(order[i + 1] * 16) -
                          (int32_t)(order[i] * 16 + 15);
            b[15] = 0x14000000 | ((uint32_t)off & 0x03ffffff);  /* B */
        } else {
            b[15] = 0xd65f03c0;                      /* RET */
        }
    }
    g_free(order);
    if (mprotect(c, bytes, PROT_READ | PROT_EXEC)) {
        munmap(c, bytes);
        return 0;
    }
    __builtin___clear_cache((char *)c, (char *)c + bytes);
    void (*fn)(void) = (void (*)(void))c;
    for (uint64_t i = 0; i < n; i++) {
        fn();
    }
    munmap(c, bytes);
    return n * blocks;
#else
    return 0;
#endif
}

/* Run one kernel with the counters live and log its deltas per unit. */
static void pmu433_ctl_one(const char *name, int which)
{
    static uint64_t d[PMU433_MAXUNIT][PMU433_NGRP][2 + PMU433_NEV];
    uint64_t units = 0;
    int c0, c1;
    int64_t t0;
    char buf[1024];
    size_t cbytes = which == 4 ? 16 << 10 : which == 5 ? 64 << 20 : 0;
    void **ring = cbytes ? pmu433_chase_prep(cbytes) : NULL;

    pmu433_read(d);
    c0 = pmu433_getcpu();
    t0 = get_clock();
    /*
     * Each kernel runs ~0.3-0.8 s on an X3 so every group gets time.
     * units: the instructions or iterations a reader divides by -- adds
     * (alu1), multiplies (mul1), indirect branches (ind*), loads (chase*),
     * 64-byte code blocks (code*).
     */
    switch (which) {
    case 0: pmu433_sink = pmu433_k_alu1(25000000); units = 64 * 25000000ull;
            break;
    case 1: pmu433_sink = pmu433_k_mul1(12000000); units = 64 * 12000000ull;
            break;
    case 2: pmu433_sink = pmu433_k_ind(400000000, 0); units = 400000000;
            break;
    case 3: pmu433_sink = pmu433_k_ind(100000000, 7); units = 100000000;
            break;
    case 4: units = pmu433_k_chase(ring, 300000000); break;
    case 5: units = pmu433_k_chase(ring, 4000000); break;
    case 6: units = pmu433_k_code(400000, 256); break;
    case 7: units = pmu433_k_code(8000, 8192); break;
    }
    c1 = pmu433_getcpu();
    pmu433_read(d);
    if (ring) {
        munmap(ring, cbytes);
    }
    for (int i = 0; i < pmu433_nunit; i++) {
        if (!pmu433_ran(d[i])) {
            continue;
        }
        pmu433_fmt(buf, sizeof(buf), i, d[i]);
        PMU433_LOG("[pmu433] ctl=%s units=%" PRIu64 " ms=%" PRId64
                   " cpu=%d-%d%s", name, units,
                   (get_clock() - t0) / 1000000, c0, c1, buf);
    }
}

static void pmu433_controls(void)
{
    static const char *const names[] = {
        "alu1", "mul1", "ind1", "ind8", "chase16k", "chase64m",
        "code16k", "code512k",
    };
    for (int i = 0; i < 8; i++) {
        pmu433_ctl_one(names[i], i);
    }
}

/*
 * ---- SAMPLING (HAKUX_PMU=2, R2) ----
 *
 * Each sampled event leads its own group (with cycles and instructions as
 * followers, so its rate comes from the same run) and has its own ring, which
 * this thread drains at each slice. The groups multiplex, so each event is
 * sampled for its share of the time; a table is per event. Each sample is
 * attributed here, while the TB still exists:
 *   jit   the pc is inside a TB (tcg_tb_lookup): keyed by the guest pc and
 *         the guest physical address of the block (CF_PCREL TBs carry only
 *         the latter), with its icount, host code size and tier;
 *   stub  inside the code buffer but no TB: the prologue/epilogue and the
 *         goto_ptr return path, i.e. the dispatch stub;
 *   host  anywhere else: keyed by 64-byte bucket of the pc; at report time
 *         dladdr names the library and the offset from its base, so the
 *         APK's unstripped .so symbolizes it offline (dladdr's own symbol is
 *         only the nearest exported one and is printed as a hint).
 * Every 10 slices, per event: one [pmu433] smp line with the totals and the
 * samples per CPU, then the top 20 of each table as smpj / smph lines, and
 * the tables reset.
 *
 * Skid: an ARM PMU overflow interrupt is taken some instructions after the
 * event, so the pc is near, not at, the instruction that caused it. At TB
 * granularity that blurs only the TB's last instructions into its successor.
 */
#define PMU433_HBITS 12
typedef struct {
    uint64_t key;       /* 0 empty; bit 63 set on every live key */
    uint32_t n;
    uint16_t icount, tier;
    uint32_t tcsize;
} Pmu433Slot;
static Pmu433Slot pmu433_jit[PMU433_NSEV][1 << PMU433_HBITS];
static Pmu433Slot pmu433_host[PMU433_NSEV][1 << PMU433_HBITS];
enum { SN_ALL, SN_LOST, SN_JIT, SN_STUB, SN_HOST, SN_DROP, SN_N };
static uint64_t pmu433_sn[PMU433_NSEV][SN_N];
static uint32_t pmu433_scpu[PMU433_NSEV][PMU433_MAXCPU];

static Pmu433Slot *pmu433_slot(Pmu433Slot *t, uint64_t key)
{
    uint32_t h = (uint32_t)((key * 0x9e3779b97f4a7c15ull)
                            >> (64 - PMU433_HBITS));
    for (int i = 0; i < 16; i++) {
        Pmu433Slot *s = &t[(h + i) & ((1 << PMU433_HBITS) - 1)];
        if (s->key == key) {
            return s;
        }
        if (!s->key) {
            s->key = key;
            return s;
        }
    }
    return NULL;
}

static void pmu433_attribute(int g, uint64_t ip, unsigned cpu)
{
    TranslationBlock *tb;
    Pmu433Slot *s;
    uint64_t *sn = pmu433_sn[g];

    sn[SN_ALL]++;
    if (cpu < PMU433_MAXCPU) {
        pmu433_scpu[g][cpu]++;
    }
    tb = tcg_tb_lookup((uintptr_t)ip);
    if (tb) {
        uint64_t phys = (uint32_t)tb->page_addr[0] & 0x7fffffff;
        s = pmu433_slot(pmu433_jit[g],
                        1ull << 63 | phys << 32 | (uint32_t)tb->pc);
        sn[SN_JIT]++;
        if (s) {
            s->n++;
            s->icount = tb->icount;
            s->tcsize = (uint32_t)tb->tc.size;
            s->tier = tb->tier;
        } else {
            sn[SN_DROP]++;
        }
        return;
    }
    if (in_code_gen_buffer((void *)(uintptr_t)ip) ||
        in_code_gen_buffer((void *)(uintptr_t)(ip - tcg_splitwx_diff))) {
        sn[SN_STUB]++;
        return;
    }
    sn[SN_HOST]++;
    s = pmu433_slot(pmu433_host[g], 1ull << 63 | ip >> 6);
    if (s) {
        s->n++;
    } else {
        sn[SN_DROP]++;
    }
}

/* Drain one ring: PERF_RECORD_SAMPLE (ip, cpu) and PERF_RECORD_LOST. */
static void pmu433_drain(int g, struct perf_event_mmap_page *mp)
{
    size_t psz = getpagesize(), dsz = PMU433_RING_PAGES * psz;
    const uint8_t *data;
    uint64_t head, tail;

    if (!mp) {
        return;
    }
    data = (const uint8_t *)mp + psz;
    head = __atomic_load_n(&mp->data_head, __ATOMIC_ACQUIRE);
    tail = mp->data_tail;
    while (tail + sizeof(struct perf_event_header) <= head) {
        struct perf_event_header h;
        uint64_t rec[4];
        size_t len;

        for (size_t k = 0; k < sizeof(h); k++) {
            ((uint8_t *)&h)[k] = data[(tail + k) % dsz];
        }
        if (h.size < sizeof(h) || tail + h.size > head) {
            break;
        }
        len = h.size - sizeof(h);
        len = len < sizeof(rec) ? len : sizeof(rec);
        for (size_t k = 0; k < len; k++) {
            ((uint8_t *)rec)[k] = data[(tail + sizeof(h) + k) % dsz];
        }
        if (h.type == PERF_RECORD_SAMPLE && len >= 16) {
            pmu433_attribute(g, rec[0], (unsigned)(rec[1] & 0xffffffff));
        } else if (h.type == PERF_RECORD_LOST && len >= 16) {
            pmu433_sn[g][SN_LOST] += rec[1];
        }
        tail += h.size;
    }
    __atomic_store_n(&mp->data_tail, tail, __ATOMIC_RELEASE);
}

/* Index of the largest n in t (reported entries are zeroed), or -1. */
static int pmu433_top(Pmu433Slot *t)
{
    int best = -1;
    for (int i = 0; i < 1 << PMU433_HBITS; i++) {
        if (t[i].n && (best < 0 || t[i].n > t[best].n)) {
            best = i;
        }
    }
    return best;
}

static void pmu433_report(unsigned w)
{
    for (int g = 0; g < pmu433_ngrp; g++) {
        uint64_t *sn = pmu433_sn[g];
        unsigned ev = pmu433_ev[g][0];
        char cb[PMU433_MAXCPU * 12];
        int off = 0;

        for (int c = 0; c < PMU433_MAXCPU; c++) {
            if (pmu433_scpu[g][c]) {
                off += snprintf(cb + off, sizeof(cb) - off, "%s%d:%u",
                                off ? "," : "", c, pmu433_scpu[g][c]);
            }
        }
        PMU433_LOG("[pmu433] smp w=%u ev=0x%x per=%" PRIu64 " n=%" PRIu64
                   " lost=%" PRIu64 " jit=%" PRIu64 " stub=%" PRIu64
                   " host=%" PRIu64 " drop=%" PRIu64 " cpu=%s", w, ev,
                   pmu433_sperg[g], sn[SN_ALL], sn[SN_LOST], sn[SN_JIT],
                   sn[SN_STUB], sn[SN_HOST], sn[SN_DROP], off ? cb : "-");
        for (int r = 0; r < 20; r++) {
            int i = pmu433_top(pmu433_jit[g]);
            if (i < 0) {
                break;
            }
            Pmu433Slot *s = &pmu433_jit[g][i];
            PMU433_LOG("[pmu433] smpj w=%u ev=0x%x r=%d n=%u pc=%08x "
                       "phys=%08x ic=%u sz=%u tier=%u", w, ev, r, s->n,
                       (uint32_t)s->key,
                       (uint32_t)(s->key >> 32) & 0x7fffffff, s->icount,
                       s->tcsize, s->tier);
            s->n = 0;
        }
        for (int r = 0; r < 20; r++) {
            int i = pmu433_top(pmu433_host[g]);
            Dl_info di;
            if (i < 0) {
                break;
            }
            Pmu433Slot *s = &pmu433_host[g][i];
            uintptr_t ip = (uintptr_t)(s->key & ~(1ull << 63)) << 6;
            const char *lib = "?", *sym = "?";
            uintptr_t base = 0;
            if (dladdr((void *)ip, &di)) {
                lib = di.dli_fname ? di.dli_fname : "?";
                lib = strrchr(lib, '/') ? strrchr(lib, '/') + 1 : lib;
                sym = di.dli_sname ? di.dli_sname : "?";
                base = (uintptr_t)di.dli_fbase;
            }
            PMU433_LOG("[pmu433] smph w=%u ev=0x%x r=%d n=%u lib=%s off=%"
                       PRIxPTR " hint=%s", w, ev, r, s->n, lib, ip - base,
                       sym);
            s->n = 0;
        }
    }
    memset(pmu433_jit, 0, sizeof(pmu433_jit));
    memset(pmu433_host, 0, sizeof(pmu433_host));
    memset(pmu433_sn, 0, sizeof(pmu433_sn));
    memset(pmu433_scpu, 0, sizeof(pmu433_scpu));
}

/* ---- the slice line ---- */

static void pmu433_tick(void)
{
    static int64_t prev_ns;
    static unsigned slice, prev_fc;
    static uint64_t cpus_seen;
    static uint64_t d[PMU433_MAXUNIT][PMU433_NGRP][2 + PMU433_NEV];
    int64_t now;
    char buf[4000];
    int off = 0;

    if (likely(pmu433_state < 0)) {
        return;
    }
    if (!pmu433_state) {
        const char *e = getenv("HAKUX_PMU");
        if (!e || !*e || !strcmp(e, "0")) {
            pmu433_state = -1;
            return;
        }
        pmu433_mode = strcmp(e, "2") ? 1 : 2;
        if (pmu433_mode == 2) {
            const char *per = getenv("HAKUX_PMU_PERIOD");
            if (per && *per) {
                pmu433_sper = strtoull(per, NULL, 10);
            }
        }
        pmu433_start();
        if (pmu433_state < 0) {
            return;
        }
        e = getenv("HAKUX_PMU_CTL");
        if (e && !strcmp(e, "1") && pmu433_mode == 1) {
            pmu433_controls();
        }
        pmu433_read(d);
        pmu433_swread(0); pmu433_swread(1); pmu433_swread(2);
        prev_ns = get_clock();
        prev_fc = g_nv2a_stats.frame_count;
        return;
    }
    /* a syscall on arm64 (no vDSO getcpu): 1 gate call in 16 is plenty */
    static unsigned cpu_gate;
    if (!(cpu_gate++ & 15)) {
        int cpu = pmu433_getcpu();
        if (cpu >= 0 && cpu < 64) {
            cpus_seen |= 1ull << cpu;
        }
    }
    now = get_clock();
    if (now - prev_ns < NANOSECONDS_PER_SECOND) {
        return;
    }

    /* Frames flipped in the slice and the longest of them. */
    unsigned fc = g_nv2a_stats.frame_count, nf = fc - prev_fc;
    unsigned ptr = g_nv2a_stats.frame_ptr;
    int fmax = 0;
    for (unsigned k = 1; k <= nf && k <= NV2A_PROF_NUM_FRAMES; k++) {
        int ms = g_nv2a_stats.frame_history[(ptr + NV2A_PROF_NUM_FRAMES - k)
                                            % NV2A_PROF_NUM_FRAMES].mspf;
        fmax = ms > fmax ? ms : fmax;
    }

    pmu433_read(d);
    uint64_t tclk = pmu433_swread(0), cs = pmu433_swread(1),
             mig = pmu433_swread(2);
    off = snprintf(buf, sizeof(buf), "[pmu433] s=%u dt=%" PRId64
                   " fr=%u fmax=%d tclk=%.1f cs=%" PRIu64 " mig=%" PRIu64
                   " cpus=%" PRIx64, slice, (now - prev_ns) / 1000000, nf,
                   fmax, tclk / 1e6, cs, mig, cpus_seen);
    /*
     * __android_log_print formats into 1024 bytes and cuts the rest, so a
     * slice that visited many CPUs lost its last units (c7, the X3, comes
     * last) and could end mid-number. A unit that would pass PMU433_LINE
     * goes on a continuation line, `s=N+`, which the reader joins to slice N.
     */
    for (int i = 0; i < pmu433_nunit; i++) {
        char ub[1024];
        int n;

        if (!pmu433_ran(d[i])) {
            continue;
        }
        n = pmu433_fmt(ub, sizeof(ub), i, d[i]);
        if (off + n >= PMU433_LINE) {
            PMU433_LOG("%s", buf);
            off = snprintf(buf, sizeof(buf), "[pmu433] s=%u+", slice);
        }
        memcpy(buf + off, ub, n + 1);
        off += n;
    }
    PMU433_LOG("%s", buf);
    if (pmu433_mode == 2) {
        for (int i = 0; i < pmu433_nunit; i++) {
            for (int g = 0; g < pmu433_ngrp; g++) {
                pmu433_drain(g, pmu433_unit[i].ring[g]);
            }
        }
        if (slice % 10 == 9) {
            pmu433_report(slice / 10);
        }
    }
    slice++;
    prev_ns = now;
    prev_fc = fc;
    cpus_seen = 0;
}
