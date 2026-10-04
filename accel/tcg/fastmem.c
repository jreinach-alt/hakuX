/*
 * hakuX fastmem (lane.memfast, #507): see fastmem.h for what it is, and
 * docs/lanes/memfast/NOTES.md for the design and the measurements.
 *
 * Two things live here, both off unless an env var asks:
 *
 *   F0a (HAKUX_F0A=<s>): a microbenchmark that prices the operations F1 is
 *   built from, inside the app, under libsigchain and with the emulator's
 *   other threads running: a SIGSEGV round trip, mmap/mprotect/unmap of one
 *   memfd page in a 4 GiB reservation, a first touch, a "drop everything"
 *   remap, the cold path (fault, map, retouch), and a two-level page walk.
 *   Lines start "[f0a]". Reader: docs/lanes/memfast/f0a_read.py.
 *
 *   F1 (HAKUX_FASTMEM=1): the shadow, its coherence with the softmmu TLB,
 *   the fault handler and the per-site table it uses. Lines start "[fm]".
 *
 * Threads: everything that changes the shadow runs on the vCPU thread (the
 * Xbox has one), or in exclusive work while that thread is stopped. The
 * signal handler runs on the vCPU thread too, inside generated code, so it
 * never interrupts a change to the site table or the shadow.
 */
#include "qemu/osdep.h"
#include "fastmem.h"

#if HAKUX_FM_BUILD
#include <android/log.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <pthread.h>
#include "qemu/cacheflush.h"
#include "qemu/timer.h"
#include "exec/page-protection.h"
#include "tcg/tcg.h"
#include "tb-context.h"

#define FM_LOG(...) __android_log_print(ANDROID_LOG_WARN, "hakuX", __VA_ARGS__)

#define FM_SPAN   ((uintptr_t)1 << 32)
#define FM_GUARD  ((uintptr_t)64 << 10)
#define FM_PAGES  (1u << 20)
#define FM_CAP    24576     /* most listed pages; see fm_cap */
#define FM_K      8         /* uncured faults before a site is patched */

#define FM_ST_MAPPED 1
#define FM_ST_LARGE  2
#define FM_ST_LISTED 0x80

bool hakux_fm_want;
bool hakux_fm_on;
uintptr_t hakux_fm_base;
hakux_fm_walk_fn hakux_fm_walk;
uintptr_t hakux_fm_ram_host;
uint64_t hakux_fm_ram_size;
bool hakux_fm_one;
bool hakux_fm_stale;
uint32_t *hakux_fm_off;

static int fm_mode = -1;        /* 0 off, 1 F1, 2 RAM on a memfd only */
static int fm_fd = -1;
static uint8_t *fm_st;          /* per guest VA page */
static uint32_t *fm_pa;         /* ... its physical page */
static uint32_t *fm_off;        /* ... its page in the RAM memfd */
static uint32_t *fm_list;       /* listed VA pages, FM_CAP at most */
static uint32_t fm_nlist, fm_nmapped;
static uint32_t fm_cap = FM_CAP; /* set from the VMA headroom at init */
static uint8_t fm_lp4m[1024];   /* a 4 MiB region holds a large-page piece */

/* The site table: inline load (rx) -> its slow path, and uncured faults. */
static uint64_t *fm_skey;
static int32_t *fm_sdelta;
static uint8_t *fm_scnt;
static uint32_t fm_smask, fm_sn;
static unsigned fm_sflush;
static int64_t fm_fault_h = -1; /* the site whose fault the stub serves */
static uint32_t fm_fault_vpn;

static struct sigaction fm_old_segv, fm_old_bus;
static bool fm_handler_in;

/* Counters, vCPU thread; the [fm] line prints the deltas. */
static uint64_t c_map, c_mapf, c_unmap, c_drop, c_dropns, c_rv, c_rvw,
                c_rvk, c_rvns, c_flt, c_pat, c_shit, c_cap, c_inv, c_ram,
                c_sadd;

/* F0a's faulting page: the handler steps over a load from it. */
static volatile uintptr_t f0a_pg;
static volatile uint64_t f0a_nflt;

static void fm_env(void)
{
    const char *e;

    if (fm_mode >= 0) {
        return;
    }
    e = getenv("HAKUX_FASTMEM");
    if (!e || !e[0] || strcmp(e, "0") == 0) {
        fm_mode = 0;
    } else if (strcmp(e, "ram") == 0) {
        fm_mode = 2;
    } else if (strcmp(e, "one") == 0) {
        fm_mode = 1;
        hakux_fm_one = true;
    } else {
        fm_mode = 1;
    }
}

/* ---- the signal handler, shared by F0a and F1 ---- */

static void fm_chain(int sig, siginfo_t *si, void *ctx)
{
    struct sigaction *old = sig == SIGBUS ? &fm_old_bus : &fm_old_segv;
    struct sigaction dfl;

    if ((old->sa_flags & SA_SIGINFO) && old->sa_sigaction) {
        old->sa_sigaction(sig, si, ctx);
        return;
    }
    if (!(old->sa_flags & SA_SIGINFO) && old->sa_handler != SIG_DFL &&
        old->sa_handler != SIG_IGN) {
        old->sa_handler(sig);
        return;
    }
    /* Default: re-fault on return with nothing installed, and die of it. */
    memset(&dfl, 0, sizeof(dfl));
    dfl.sa_handler = SIG_DFL;
    sigaction(sig, &dfl, NULL);
}

static inline uint32_t fm_hash(uint64_t key)
{
    return (uint32_t)((key >> 2) * 0x9E3779B97F4A7C15ull >> 32);
}

static void fm_handler(int sig, siginfo_t *si, void *ctx)
{
    ucontext_t *uc = ctx;
    uintptr_t a;
    uint64_t pc;

    if (!uc || !si) {
        /* QEMU's signalfd path calls the SIGBUS action with no context. */
        fm_chain(sig, si, ctx);
        return;
    }
    a = (uintptr_t)si->si_addr;
    pc = uc->uc_mcontext.pc;
    if (f0a_pg && a - f0a_pg < 4096) {
        uc->uc_mcontext.pc = pc + 4;
        f0a_nflt++;
        return;
    }
    /*
     * Only generated code, which only the vCPU thread runs, may probe the
     * table: another thread's wild pointer into the shadow must not read it
     * while a translation grows it.
     */
    if (hakux_fm_on && a - hakux_fm_base < FM_SPAN + FM_GUARD && fm_skey &&
        in_code_gen_buffer(tcg_splitwx_to_rw((void *)(uintptr_t)pc))) {
        uint32_t h = fm_hash(pc) & fm_smask;

        while (fm_skey[h]) {
            if (fm_skey[h] == pc) {
                uint64_t stub = pc + (int64_t)fm_sdelta[h];
                uint8_t n = fm_scnt[h];

                if (n < 255) {
                    fm_scnt[h] = ++n;
                }
                fm_fault_h = h;
                fm_fault_vpn = (uint32_t)((a - hakux_fm_base) >> 12);
                c_flt++;
                if (n == FM_K) {
                    /*
                     * This site keeps faulting with no map curing it: MMIO,
                     * or a watched page. Make it branch to its slow path for
                     * good, which is what it costs today plus the helper's
                     * own lookup. The handler runs on the only thread that
                     * executes or writes this code.
                     */
                    uint32_t insn = 0x14000000u |
                        ((uint32_t)((stub - pc) >> 2) & 0x03ffffffu);
                    uint32_t *rw = tcg_splitwx_to_rw((void *)(uintptr_t)pc);

                    *rw = insn;
                    flush_idcache_range(pc, (uintptr_t)rw, 4);
                    c_pat++;
                }
                uc->uc_mcontext.pc = stub;
                return;
            }
            h = (h + 1) & fm_smask;
        }
    }
    fm_chain(sig, si, ctx);
}

static void fm_install_handler(void)
{
    struct sigaction sa;

    if (fm_handler_in) {
        return;
    }
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = fm_handler;
    sa.sa_flags = SA_SIGINFO | SA_ONSTACK | SA_RESTART;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGSEGV, &sa, &fm_old_segv);
    sigaction(SIGBUS, &sa, &fm_old_bus);
    fm_handler_in = true;
}

static void fm_remove_handler(void)
{
    if (!fm_handler_in || fm_mode == 1) {
        return;
    }
    sigaction(SIGSEGV, &fm_old_segv, NULL);
    sigaction(SIGBUS, &fm_old_bus, NULL);
    fm_handler_in = false;
}

/* ---- F0a ---- */

static inline uint64_t fm_ns(void)
{
    struct timespec t;

    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + t.tv_nsec;
}

static inline uint32_t f0a_load(uintptr_t p)
{
    uint32_t v;

    /* One 4-byte instruction, so the handler can step over it. */
    asm volatile("ldr %w0, [%1]" : "=r"(v) : "r"(p) : "memory");
    return v;
}

static int f0a_cmp(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return x < y ? -1 : x > y;
}

/* p50 and p90 of n samples, sorted in place. */
static void f0a_pct(uint64_t *s, unsigned n, uint64_t *p50, uint64_t *p90)
{
    qsort(s, n, sizeof(*s), f0a_cmp);
    *p50 = s[n / 2];
    *p90 = s[n * 9 / 10];
}

static unsigned f0a_maps_lines(void)
{
    FILE *f = fopen("/proc/self/maps", "r");
    unsigned n = 0;
    int c;

    if (!f) {
        return 0;
    }
    while ((c = getc(f)) != EOF) {
        n += c == '\n';
    }
    fclose(f);
    return n;
}

static int f0a_cpu(void)
{
    unsigned cpu = ~0u;

    syscall(__NR_getcpu, &cpu, NULL, NULL);
    return (int)cpu;
}

static int f0a_fastest_cpu(void)
{
    long best = -1;
    int cpu = -1;

    for (int i = 0; i < 16; i++) {
        char path[96];
        long v = -1;
        FILE *f;

        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq", i);
        f = fopen(path, "r");
        if (!f) {
            continue;
        }
        if (fscanf(f, "%ld", &v) == 1 && v >= best) {
            best = v;
            cpu = i;
        }
        fclose(f);
    }
    return cpu;
}

static void f0a_sysline(const char *path, char *out, size_t n)
{
    FILE *f = fopen(path, "r");

    out[0] = 0;
    if (f) {
        if (fgets(out, n, f)) {
            out[strcspn(out, "\n")] = 0;
        }
        fclose(f);
    }
}

/*
 * Is guest RAM on huge pages, and is the shadow? The pilot pair (NOTES,
 * "F1 pilot") found F1 slower than its control in the memory-heavy scenes,
 * and the suspect is host TLB reach: anonymous RAM can sit on 2 MiB THP, a
 * memfd only if shmem THP is on, and the shadow's 4 KiB pieces never. Sums
 * /proc/self/smaps over the RAM block's range and over the shadow's.
 */
static void f0a_thp(void)
{
    uintptr_t ram = hakux_fm_ram_host ? hakux_fm_ram_host
                                      : xbox_ram_fp.host_base;
    uintptr_t rend = ram + (hakux_fm_ram_size ? hakux_fm_ram_size
                                              : (64u << 20));
    static const char *keys[] = { "Rss:", "AnonHugePages:", "ShmemPmdMapped:",
                                  "FilePmdMapped:", "ShmemHugePages:" };
    long sum[2][5] = { { 0 } };
    char en[96], sh[96], line[256];
    int which = -1, nvma[2] = { 0, 0 };
    FILE *f;

    f0a_sysline("/sys/kernel/mm/transparent_hugepage/enabled", en, sizeof(en));
    f0a_sysline("/sys/kernel/mm/transparent_hugepage/shmem_enabled", sh,
                sizeof(sh));
    f = fopen("/proc/self/smaps", "r");
    while (f && fgets(line, sizeof(line), f)) {
        unsigned long lo, hi;
        long v;

        /* A header starts with a lowercase hex address, a field with "Key:". */
        if (((line[0] >= '0' && line[0] <= '9') ||
             (line[0] >= 'a' && line[0] <= 'f')) &&
            sscanf(line, "%lx-%lx ", &lo, &hi) == 2) {
            which = -1;
            if (lo < rend && hi > ram) {
                which = 0;
            } else if (hakux_fm_base && lo >= hakux_fm_base &&
                       hi <= hakux_fm_base + FM_SPAN + FM_GUARD) {
                which = 1;
            }
            if (which >= 0) {
                nvma[which]++;
            }
            continue;
        }
        if (which < 0) {
            continue;
        }
        for (int k = 0; k < 5; k++) {
            size_t kl = strlen(keys[k]);
            if (strncmp(line, keys[k], kl) == 0 &&
                sscanf(line + kl, "%ld", &v) == 1) {
                sum[which][k] += v;
            }
        }
    }
    if (f) {
        fclose(f);
    }
    FM_LOG("[f0a] thp enabled=[%s] shmem=[%s] fm=%d", en, sh, fm_mode);
    FM_LOG("[f0a] thp ram=0x%" PRIxPTR " vmas=%d rss_kb=%ld anonhuge_kb=%ld "
           "shmempmd_kb=%ld filepmd_kb=%ld shmemhuge_kb=%ld | shadow vmas=%d "
           "rss_kb=%ld shmempmd_kb=%ld filepmd_kb=%ld",
           ram, nvma[0], sum[0][0], sum[0][1], sum[0][2], sum[0][3],
           sum[0][4], nvma[1], sum[1][0], sum[1][2], sum[1][3]);
}

#define F0A_N 8192

static void f0a_pass(const char *tag, uint64_t *s, uint32_t *slot,
                     uint32_t *off, uint8_t *ram, int fd)
{
    uint64_t sig50, sig90, map50, map90, t150, t190, t250, t290, mp50, mp90,
             un50, un90, pm50, pm90, pt50, pt90, cold50, cold90, w50, w90,
             wc50, wc90, drop_us, vmas;
    uintptr_t res;
    unsigned i, k;
    int cpu0 = f0a_cpu(), cpu1;
    volatile uint32_t sink = 0;

    /* 1. SIGSEGV round trip: 16 batches of 512 faulting loads. */
    res = (uintptr_t)mmap(NULL, 4096, PROT_NONE,
                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    f0a_pg = res;
    for (k = 0; k < 16; k++) {
        uint64_t t0 = fm_ns();
        for (i = 0; i < 512; i++) {
            sink += f0a_load(res);
        }
        s[k] = (fm_ns() - t0) / 512;
    }
    f0a_pct(s, 16, &sig50, &sig90);
    f0a_pg = 0;
    munmap((void *)res, 4096);

    /* The shadow-shaped reservation. */
    res = (uintptr_t)mmap(NULL, FM_SPAN + FM_GUARD, PROT_NONE,
                          MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if (res == (uintptr_t)MAP_FAILED) {
        FM_LOG("[f0a] pass=%s reserve FAILED errno=%d", tag, errno);
        return;
    }

#define F0A_TIMED(dst, stmt) do { \
        for (i = 0; i < F0A_N; i++) { \
            uintptr_t p = res + ((uintptr_t)slot[i] << 12); \
            uint64_t t0 = fm_ns(); \
            stmt; \
            s[i] = fm_ns() - t0; \
            (void)p; \
        } \
        f0a_pct(s, F0A_N, &dst##50, &dst##90); \
    } while (0)

    /* 2. map one page of the memfd at a scattered slot and offset. */
    F0A_TIMED(map, mmap((void *)p, 4096, PROT_READ, MAP_SHARED | MAP_FIXED,
                        fd, (off_t)off[i] << 12));
    vmas = f0a_maps_lines();
    /* 3. first touch (a host minor fault), then a second (a hit). */
    F0A_TIMED(t1, sink += *(volatile uint32_t *)p);
    F0A_TIMED(t2, sink += *(volatile uint32_t *)p);
    /* 4. mprotect away and back: two calls per sample. */
    F0A_TIMED(mp, (mprotect((void *)p, 4096, PROT_NONE),
                   mprotect((void *)p, 4096, PROT_READ)));
    /* 5. "unmap", the way the shadow does it. */
    F0A_TIMED(un, mmap((void *)p, 4096, PROT_NONE,
                       MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED |
                       MAP_NORESERVE, -1, 0));
    /* 6. map with MAP_POPULATE, then touch. */
    F0A_TIMED(pm, mmap((void *)p, 4096, PROT_READ,
                       MAP_SHARED | MAP_FIXED | MAP_POPULATE,
                       fd, (off_t)off[i] << 12));
    F0A_TIMED(pt, sink += *(volatile uint32_t *)p);
    /* 7. drop everything with one remap, F0A_N pages mapped. */
    {
        uint64_t t0 = fm_ns();
        mmap((void *)res, FM_SPAN + FM_GUARD, PROT_NONE,
             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED | MAP_NORESERVE, -1, 0);
        drop_us = (fm_ns() - t0) / 1000;
    }
    /* 8. the cold path: fault, map, retouch (F1's cost per refault). */
    f0a_pg = 0;
    for (i = 0; i < F0A_N / 4; i++) {
        uintptr_t p = res + ((uintptr_t)slot[i] << 12);
        uint64_t t0 = fm_ns();

        f0a_pg = p;
        sink += f0a_load(p);
        f0a_pg = 0;
        mmap((void *)p, 4096, PROT_READ, MAP_SHARED | MAP_FIXED, fd,
             (off_t)off[i] << 12);
        sink += *(volatile uint32_t *)p;
        s[i] = fm_ns() - t0;
    }
    f0a_pct(s, F0A_N / 4, &cold50, &cold90);
    munmap((void *)res, FM_SPAN + FM_GUARD);

    /*
     * 9. a two-level walk over F0A_N mapped VAs: a page directory and page
     * tables in "RAM" (the memfd's first 4 MiB), PTEs scattered. Warm, then
     * after evicting the caches with a 32 MiB sweep of the rest of RAM.
     */
    {
        uint32_t *pd = (uint32_t *)ram;
        for (i = 0; i < 1024; i++) {
            pd[i] = ((1 + i) << 12) | 0x21;     /* P, A */
        }
        for (i = 0; i < F0A_N; i++) {
            uint32_t va = slot[i] << 12;
            uint32_t *pt = (uint32_t *)(ram + (pd[va >> 22] & ~0xfffu));
            pt[(va >> 12) & 0x3ff] = (off[i] << 12) | 0x21;
        }
        for (k = 0; k < 2; k++) {
            if (k) {
                for (i = 0; i < (32u << 20); i += 64) {
                    sink += ram[(4u << 20) + i];
                }
            }
            for (i = 0; i < F0A_N; i++) {
                uint32_t va = slot[i] << 12;
                uint64_t t0 = fm_ns();
                uint32_t pde = *(volatile uint32_t *)(ram + ((va >> 22) << 2));
                uint32_t pte = *(volatile uint32_t *)
                    (ram + (pde & ~0xfffu) + (((va >> 12) & 0x3ff) << 2));
                sink += (pte & 0x21) == 0x21 && (pte >> 12) == off[i];
                s[i] = fm_ns() - t0;
            }
            if (k) {
                f0a_pct(s, F0A_N, &wc50, &wc90);
            } else {
                f0a_pct(s, F0A_N, &w50, &w90);
            }
        }
        /*
         * The per-sample clock reads (~2 x 20-40 ns) dominate a walk; the
         * batch figure below is the one to price with.
         */
        {
            uint64_t t0 = fm_ns();
            for (i = 0; i < F0A_N; i++) {
                uint32_t va = slot[i] << 12;
                uint32_t pde = *(volatile uint32_t *)(ram + ((va >> 22) << 2));
                uint32_t pte = *(volatile uint32_t *)
                    (ram + (pde & ~0xfffu) + (((va >> 12) & 0x3ff) << 2));
                sink += (pte & 0x21) == 0x21 && (pte >> 12) == off[i];
            }
            s[0] = (fm_ns() - t0) * 1000 / F0A_N;   /* ps per walk */
        }
    }
    cpu1 = f0a_cpu();
    FM_LOG("[f0a] pass=%s cpu=%d->%d sig=%" PRIu64 "/%" PRIu64
           " map=%" PRIu64 "/%" PRIu64 " touch1=%" PRIu64 "/%" PRIu64
           " touch2=%" PRIu64 "/%" PRIu64 " mprot2=%" PRIu64 "/%" PRIu64
           " unmap=%" PRIu64 "/%" PRIu64 " mappop=%" PRIu64 "/%" PRIu64
           " touchpop=%" PRIu64 "/%" PRIu64 " cold=%" PRIu64 "/%" PRIu64
           " walk=%" PRIu64 "/%" PRIu64 " walkcold=%" PRIu64 "/%" PRIu64
           " walkbatch_ps=%" PRIu64 " dropall_us=%" PRIu64 " n=%u vmas=%" PRIu64
           " sink=%u",
           tag, cpu0, cpu1, sig50, sig90, map50, map90, t150, t190, t250,
           t290, mp50, mp90, un50, un90, pm50, pm90, pt50, pt90, cold50,
           cold90, w50, w90, wc50, wc90, s[0], drop_us, F0A_N, vmas,
           (unsigned)sink);
}

static void *f0a_thread(void *arg)
{
    unsigned delay = (unsigned)(uintptr_t)arg;
    uint64_t *s = g_new(uint64_t, F0A_N);
    uint32_t *slot = g_new(uint32_t, F0A_N);
    uint32_t *off = g_new(uint32_t, F0A_N);
    uint8_t *seen = g_new0(uint8_t, FM_PAGES);
    uint64_t rng = 0x2545F4914F6CDD1Dull;
    struct utsname u;
    uint8_t *ram;
    long maxmap = -1;
    FILE *f;
    int fd, fast;
    unsigned i;

    sleep(delay);
    f0a_thp();
    fd = syscall(__NR_memfd_create, "f0a", 1u /* MFD_CLOEXEC */);
    if (fd < 0 || ftruncate(fd, 64u << 20) != 0) {
        FM_LOG("[f0a] memfd FAILED errno=%d", errno);
        return NULL;
    }
    ram = mmap(NULL, 64u << 20, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    memset(ram, 0, 64u << 20);
    /* F0A_N distinct VA slots below 4 GiB; offsets past the walk's tables. */
    for (i = 0; i < F0A_N; ) {
        uint32_t v;
        rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17;
        v = (uint32_t)(rng >> 20) & (FM_PAGES - 1);
        if (seen[v]) {
            continue;
        }
        seen[v] = 1;
        slot[i] = v;
        off[i] = 1025 + (uint32_t)((rng >> 40) % (16384 - 1025));
        i++;
    }
    g_free(seen);
    f = fopen("/proc/sys/vm/max_map_count", "r");
    if (f) {
        if (fscanf(f, "%ld", &maxmap) != 1) {
            maxmap = -1;
        }
        fclose(f);
    }
    uname(&u);
    FM_LOG("[f0a] env page=%ld kernel=%s max_map=%ld maps0=%u fm=%d",
           sysconf(_SC_PAGESIZE), u.release, maxmap, f0a_maps_lines(),
           fm_mode);

    fm_install_handler();
    f0a_pass("free", s, slot, off, ram, fd);
    fast = f0a_fastest_cpu();
    if (fast >= 0) {
        unsigned long mask = 1ul << fast;

        if (syscall(__NR_sched_setaffinity, 0, sizeof(mask), &mask) == 0) {
            f0a_pass("fastest", s, slot, off, ram, fd);
        }
    }
    fm_remove_handler();
    munmap(ram, 64u << 20);
    close(fd);
    g_free(s);
    g_free(slot);
    g_free(off);
    FM_LOG("[f0a] done");
    return NULL;
}

static void f0a_maybe_start(void)
{
    const char *e = getenv("HAKUX_F0A");
    pthread_t t;
    int d;

    if (!e || (d = atoi(e)) <= 0) {
        return;
    }
    if (pthread_create(&t, NULL, f0a_thread, (void *)(uintptr_t)d) == 0) {
        pthread_detach(t);
        FM_LOG("[f0a] armed delay=%ds", d);
    }
}

/* ---- F1: the shadow ---- */

static void fm_arm(void)
{
    if (hakux_fm_want && fm_fd >= 0 && hakux_fm_ram_host && !hakux_fm_on) {
        hakux_fm_on = true;
        FM_LOG("[fm] on base=0x%" PRIxPTR " ram=0x%" PRIxPTR " size=%" PRIu64
               " fd=%d idx=%d one=%d", hakux_fm_base, hakux_fm_ram_host,
               hakux_fm_ram_size, fm_fd, HAKUX_FM_IDX, hakux_fm_one);
    }
}

void hakux_fm_init(void)
{
    void *p;

    f0a_maybe_start();
    fm_env();
    if (fm_mode != 1) {
        if (fm_mode == 2) {
            FM_LOG("[fm] mode=ram (memfd RAM, no shadow)");
        }
        return;
    }
    if (sysconf(_SC_PAGESIZE) != 4096) {
        FM_LOG("[fm] OFF: host page %ld, not 4096", sysconf(_SC_PAGESIZE));
        fm_mode = 2;
        return;
    }
    p = mmap(NULL, FM_SPAN + FM_GUARD, PROT_NONE,
             MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if (p == MAP_FAILED) {
        FM_LOG("[fm] OFF: shadow reserve failed errno=%d", errno);
        fm_mode = 2;
        return;
    }
    fm_st = g_new0(uint8_t, FM_PAGES);
    fm_pa = g_new0(uint32_t, FM_PAGES);
    fm_off = g_new0(uint32_t, FM_PAGES);
    hakux_fm_off = fm_off;
    fm_list = g_new(uint32_t, FM_CAP);
    {
        /*
         * An isolated page costs two VMAs (F0a: 8,192 scattered pages added
         * 16,317 maps lines), and the whole process shares
         * vm.max_map_count. Keep 16,384 for everyone else.
         */
        long maxmap = 65530, now = f0a_maps_lines(), room;
        FILE *f = fopen("/proc/sys/vm/max_map_count", "r");

        if (f) {
            if (fscanf(f, "%ld", &maxmap) != 1) {
                maxmap = 65530;
            }
            fclose(f);
        }
        room = (maxmap - now - 16384) / 2;
        fm_cap = room < 1024 ? 1024 : room > FM_CAP ? FM_CAP : (uint32_t)room;
        FM_LOG("[fm] cap=%u pages (max_map_count %ld, maps now %ld)",
               fm_cap, maxmap, now);
    }
    fm_smask = (1u << 16) - 1;
    fm_skey = g_new0(uint64_t, fm_smask + 1);
    fm_sdelta = g_new0(int32_t, fm_smask + 1);
    fm_scnt = g_new0(uint8_t, fm_smask + 1);
    hakux_fm_base = (uintptr_t)p;
    fm_install_handler();
    hakux_fm_want = true;
    fm_arm();
}

bool hakux_fm_ram_wanted(void)
{
    fm_env();
    return fm_mode != 0;
}

int hakux_fm_ram_fd(uint64_t size)
{
    int fd = syscall(__NR_memfd_create, "xbox.ram", 1u /* MFD_CLOEXEC */);

    if (fd >= 0 && ftruncate(fd, size) != 0) {
        close(fd);
        fd = -1;
    }
    if (fd < 0) {
        FM_LOG("[fm] memfd for RAM FAILED errno=%d: fastmem stays off", errno);
    }
    return fd;
}

void hakux_fm_set_ram(void *host, uint64_t size, int fd)
{
    hakux_fm_ram_host = (uintptr_t)host;
    hakux_fm_ram_size = size;
    fm_fd = fd;
    FM_LOG("[fm] RAM host=%p size=%" PRIu64 " fd=%d mode=%d",
           host, size, fd, fm_mode);
    fm_arm();
}

/*
 * Returns false if the remap failed: splitting a VMA can fail at
 * vm.max_map_count, and then the old page is still mapped. Every caller
 * answers a failure with fm_drop_all(), which replaces the whole reservation
 * and so never needs a new VMA.
 */
static bool fm_unmap_raw(uint32_t vpn, uint32_t n)
{
    void *want = (void *)(hakux_fm_base + ((uintptr_t)vpn << 12));

    return mmap(want, (size_t)n << 12, PROT_NONE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED | MAP_NORESERVE,
                -1, 0) == want;
}

/* Replace the whole reservation, even if nothing is listed. */
static void fm_drop_all_force(void)
{
    uint64_t t0 = get_clock();

    if (!fm_unmap_raw(0, FM_PAGES + (FM_GUARD >> 12))) {
        /* Nothing left that keeps the shadow coherent: stop here. */
        FM_LOG("[fm] FATAL: drop-all remap failed errno=%d", errno);
        abort();
    }
    for (uint32_t i = 0; i < fm_nlist; i++) {
        fm_st[fm_list[i]] = 0;
    }
    fm_nlist = 0;
    fm_nmapped = 0;
    memset(fm_lp4m, 0, sizeof(fm_lp4m));
    /* One alias: idx-5 entries may point at what just went away. */
    hakux_fm_stale = hakux_fm_one;
    c_drop++;
    c_dropns += get_clock() - t0;
}

static void fm_drop_all(void)
{
    if (fm_nlist) {
        fm_drop_all_force();
    }
}

static void fm_unmap(uint32_t vpn)
{
    if (fm_st[vpn] & FM_ST_MAPPED) {
        if (!fm_unmap_raw(vpn, 1)) {
            c_mapf++;
            fm_drop_all();
            return;
        }
        fm_st[vpn] &= FM_ST_LISTED;
        fm_nmapped--;
        c_unmap++;
    }
}

static void fm_compact(void)
{
    uint32_t j = 0;

    for (uint32_t i = 0; i < fm_nlist; i++) {
        uint32_t vpn = fm_list[i];
        if (fm_st[vpn] & FM_ST_MAPPED) {
            fm_list[j++] = vpn;
        } else {
            fm_st[vpn] = 0;
        }
    }
    fm_nlist = j;
}

static void fm_map(uint32_t vpn, uint32_t offpn, uint32_t papn, bool large)
{
    uint8_t s = fm_st[vpn];
    void *want = (void *)(hakux_fm_base + ((uintptr_t)vpn << 12));

    if ((s & FM_ST_MAPPED) && fm_off[vpn] == offpn && fm_pa[vpn] == papn) {
        goto done;
    }
    if (!(s & FM_ST_LISTED)) {
        if (fm_nlist >= fm_cap) {
            fm_compact();
            if (fm_nlist >= fm_cap) {
                fm_drop_all();
                c_cap++;
            }
            s = fm_st[vpn];
        }
        if (!(s & FM_ST_LISTED)) {
            fm_list[fm_nlist++] = vpn;
            s |= FM_ST_LISTED;
        }
    }
    /* MAP_POPULATE: F0a priced map + first touch at 3.6 us, this at 2.4. */
    /*
     * One alias maps it writable: only softmmu stores, which still check
     * the entry's write flags, write through it; fast loads only read.
     */
    if (mmap(want, 4096, hakux_fm_one ? PROT_READ | PROT_WRITE : PROT_READ,
             MAP_SHARED | MAP_FIXED | MAP_POPULATE,
             fm_fd, (off_t)offpn << 12) != want) {
        /* A failed MAP_FIXED may have unmapped the old page already. */
        c_mapf++;
        if (s & FM_ST_MAPPED) {
            fm_nmapped--;
        }
        fm_st[vpn] = s & FM_ST_LISTED;
        if (!fm_unmap_raw(vpn, 1)) {
            fm_drop_all();
        }
        return;
    }
    if (!(s & FM_ST_MAPPED)) {
        fm_nmapped++;
    }
    fm_off[vpn] = offpn;
    fm_pa[vpn] = papn;
    c_map++;
done:
    fm_st[vpn] = (s & FM_ST_LISTED) | FM_ST_MAPPED | (large ? FM_ST_LARGE : 0);
    if (large) {
        fm_lp4m[vpn >> 10] = 1;
    }
    if (fm_fault_h >= 0 &&
        (fm_fault_vpn == vpn || fm_fault_vpn + 1 == vpn)) {
        /* The fault this stub serves was a cold one: it does not count. */
        fm_scnt[fm_fault_h] = 0;
        fm_fault_h = -1;
    }
}

/* Map only what softmmu would serve from xbox.ram with no read flags. */
static void fm_maybe_map(uint64_t va_page, uint64_t pa_page, uintptr_t host,
                         unsigned read_flags, int prot, bool large)
{
    uint32_t vpn = (uint32_t)(va_page >> 12);

    if (va_page >= FM_SPAN) {
        return;
    }
    if (!(prot & PAGE_READ) || read_flags != 0 || host < hakux_fm_ram_host ||
        host - hakux_fm_ram_host >= hakux_fm_ram_size) {
        fm_unmap(vpn);
        return;
    }
    fm_map(vpn, (uint32_t)((host - hakux_fm_ram_host) >> 12),
           (uint32_t)(pa_page >> 12), large);
}

uintptr_t hakux_fm_fill(unsigned mmu_idx, uint64_t va_page,
                        uint64_t pa_page, uintptr_t host,
                        unsigned read_flags, int prot, bool large)
{
    uint32_t vpn = (uint32_t)(va_page >> 12);

    if (mmu_idx != HAKUX_FM_IDX) {
        return 0;
    }
    host &= ~(uintptr_t)0xfff;
    fm_maybe_map(va_page, pa_page, host, read_flags, prot, large);
    if (hakux_fm_one && va_page < FM_SPAN && (fm_st[vpn] & FM_ST_MAPPED) &&
        hakux_fm_ram_host + ((uintptr_t)fm_off[vpn] << 12) == host) {
        return hakux_fm_base + (uintptr_t)va_page;
    }
    return 0;
}

void hakux_fm_slow_hit(uint64_t va, uintptr_t host, uint64_t pa,
                       unsigned read_flags, bool large)
{
    if (va >= FM_SPAN || (fm_st[va >> 12] & FM_ST_MAPPED)) {
        return;
    }
    c_shit++;
    fm_maybe_map(va & ~0xfffull, pa & ~0xfffull, host & ~(uintptr_t)0xfff,
                 read_flags, PAGE_READ, large);
}

/*
 * A full flush of the shadow's index. A reload of CR3 with the value it
 * holds (94-99% of GTA's full flushes, all of Tron's) is revalidated: each
 * mapped page is walked again and kept only if the walk gives the same
 * physical page and size, with A set, which is what a refill would install.
 * Anything else (a new CR3, CR0, CR4, A20, a memory-map commit, a watch
 * flush with W1 off) drops the whole shadow.
 */
static void fm_full_flush(CPUState *cpu, int cause_is_cr3);

/* After softmmu has flushed idx 5, so whatever is dropped here is covered. */
void hakux_fm_full_flush(CPUState *cpu, int cause_is_cr3)
{
    if (hakux_fm_on) {
        fm_full_flush(cpu, cause_is_cr3);
    }
    hakux_fm_stale = false;
}

static void fm_full_flush(CPUState *cpu, int cause_is_cr3)
{
    uint64_t t0;
    uint32_t j = 0, dropped = 0;

    if (cause_is_cr3 != 2 || !hakux_fm_walk) {
        fm_drop_all();
        return;
    }
    t0 = get_clock();
    memset(fm_lp4m, 0, sizeof(fm_lp4m));
    for (uint32_t i = 0; i < fm_nlist; i++) {
        uint32_t vpn = fm_list[i];
        uint8_t s = fm_st[vpn];
        uint64_t pa;
        int r;

        if (!(s & FM_ST_MAPPED)) {
            fm_st[vpn] = 0;
            continue;
        }
        c_rvw++;
        r = hakux_fm_walk(cpu, vpn << 12, &pa);
        if (r < 0 || (pa >> 12) != fm_pa[vpn] ||
            (r == 1) != !!(s & FM_ST_LARGE)) {
            bool ok = fm_unmap_raw(vpn, 1);

            fm_st[vpn] = 0;
            fm_nmapped--;
            c_unmap++;
            if (!ok || ++dropped > 512) {
                /* Most of it moved: one remap is cheaper than the rest. */
                for (uint32_t k = i + 1; k < fm_nlist; k++) {
                    fm_list[j++] = fm_list[k];
                }
                fm_nlist = j;
                fm_drop_all_force();
                c_rvns += get_clock() - t0;
                return;
            }
            continue;
        }
        if (r == 1) {
            fm_lp4m[vpn >> 10] = 1;
        }
        c_rvk++;
        fm_list[j++] = vpn;
    }
    fm_nlist = j;
    c_rv++;
    c_rvns += get_clock() - t0;
}

/* INVLPG (or any one-page flush): a large-page piece takes its 4 MiB. */
void hakux_fm_page_flush(uint64_t va, bool unused)
{
    uint32_t vpn = (uint32_t)(va >> 12);

    if (!hakux_fm_on || va >= FM_SPAN) {
        return;
    }
    c_inv++;
    if (fm_lp4m[vpn >> 10]) {
        uint32_t b = vpn & ~1023u;
        if (!fm_unmap_raw(b, 1024)) {
            c_mapf++;
            fm_drop_all();
            return;
        }
        for (uint32_t k = b; k < b + 1024; k++) {
            if (fm_st[k] & FM_ST_MAPPED) {
                fm_st[k] &= FM_ST_LISTED;
                fm_nmapped--;
                c_unmap++;
                if (hakux_fm_one && k != vpn) {
                    /* softmmu flushed only @va: drop the others' entries. */
                    hakux_fm_tlb_drop_page((uint64_t)k << 12);
                }
            }
        }
        fm_lp4m[vpn >> 10] = 0;
        return;
    }
    fm_unmap(vpn);
}

/* W1's walk: a watch on [host, host + len) of RAM unmaps its aliases. */
void hakux_fm_ram_range(uintptr_t host, uint64_t len)
{
    uint64_t lo, hi;

    if (!hakux_fm_on) {
        return;
    }
    if (host < hakux_fm_ram_host ||
        host - hakux_fm_ram_host >= hakux_fm_ram_size) {
        fm_drop_all();
        return;
    }
    c_ram++;
    lo = (host - hakux_fm_ram_host) >> 12;
    hi = (host - hakux_fm_ram_host + len + 4095) >> 12;
    for (uint32_t i = 0; i < fm_nlist; i++) {
        uint32_t vpn = fm_list[i];
        if ((fm_st[vpn] & FM_ST_MAPPED) && fm_off[vpn] >= lo &&
            fm_off[vpn] < hi) {
            fm_unmap(vpn);
        }
    }
}

/* ---- the site table ---- */

static void fm_sites_grow(void)
{
    uint32_t omask = fm_smask, nmask = omask * 2 + 1;
    uint64_t *k = g_new0(uint64_t, nmask + 1);
    int32_t *d = g_new0(int32_t, nmask + 1);
    uint8_t *c = g_new0(uint8_t, nmask + 1);

    for (uint32_t i = 0; i <= omask; i++) {
        if (fm_skey[i]) {
            uint32_t h = fm_hash(fm_skey[i]) & nmask;
            while (k[h]) {
                h = (h + 1) & nmask;
            }
            k[h] = fm_skey[i];
            d[h] = fm_sdelta[i];
            c[h] = fm_scnt[i];
        }
    }
    g_free(fm_skey);
    g_free(fm_sdelta);
    g_free(fm_scnt);
    fm_skey = k;
    fm_sdelta = d;
    fm_scnt = c;
    fm_smask = nmask;
    fm_fault_h = -1;
}

/*
 * Translation time, vCPU thread. A key is the rx address of an inline load;
 * a later translation at the same address overwrites it, and a tb_flush
 * (which recycles every address) empties the table.
 */
void hakux_fm_site_add(const void *rx_load, const void *rx_stub)
{
    uint64_t key = (uintptr_t)rx_load;
    uint32_t h;

    if (tb_ctx.tb_flush_count != fm_sflush) {
        memset(fm_skey, 0, (size_t)(fm_smask + 1) * sizeof(*fm_skey));
        fm_sn = 0;
        fm_sflush = tb_ctx.tb_flush_count;
        fm_fault_h = -1;
    }
    if ((fm_sn + 1) * 2 > fm_smask + 1) {
        fm_sites_grow();
    }
    h = fm_hash(key) & fm_smask;
    while (fm_skey[h] && fm_skey[h] != key) {
        h = (h + 1) & fm_smask;
    }
    if (!fm_skey[h]) {
        fm_sn++;
    }
    fm_skey[h] = key;
    fm_sdelta[h] = (int32_t)((intptr_t)rx_stub - (intptr_t)rx_load);
    fm_scnt[h] = 0;
    c_sadd++;
}

/* ---- the [fm] line, at the [tlb68] cadence ---- */

void hakux_fm_tick(int64_t dt_ms)
{
    static uint64_t p[16];
    static unsigned n;
    uint64_t v[16] = { c_map, c_mapf, c_unmap, c_drop, c_dropns, c_rv, c_rvw,
                       c_rvk, c_rvns, c_flt, c_pat, c_shit, c_cap, c_inv,
                       c_ram, c_sadd };
    if (fm_mode != 1) {
        return;
    }
    n++;
    FM_LOG("[fm] dt=%" PRId64 " on=%d map=%" PRIu64 " mapf=%" PRIu64
           " unmap=%" PRIu64 " drop=%" PRIu64 " dropus=%" PRIu64
           " rv=%" PRIu64 " rvw=%" PRIu64 " rvk=%" PRIu64 " rvus=%" PRIu64
           " flt=%" PRIu64 " pat=%" PRIu64 " shit=%" PRIu64 " cap=%" PRIu64
           " inv=%" PRIu64 " ram=%" PRIu64 " sadd=%" PRIu64
           " mapped=%u listed=%u capn=%u sites=%u patched=%" PRIu64 " n=%u",
           dt_ms, hakux_fm_on, v[0] - p[0], v[1] - p[1], v[2] - p[2],
           v[3] - p[3], (v[4] - p[4]) / 1000, v[5] - p[5], v[6] - p[6],
           v[7] - p[7], (v[8] - p[8]) / 1000, v[9] - p[9], v[10] - p[10],
           v[11] - p[11], v[12] - p[12], v[13] - p[13], v[14] - p[14],
           v[15] - p[15], fm_nmapped, fm_nlist, fm_cap, fm_sn, c_pat, n);
    memcpy(p, v, sizeof(p));
}

#endif
