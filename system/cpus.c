/*
 * QEMU System Emulator
 *
 * Copyright (c) 2003-2008 Fabrice Bellard
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#include "qemu/osdep.h"
#include "monitor/monitor.h"
#include "qemu/coroutine-tls.h"
#include "qapi/error.h"
#include "qapi/qapi-commands-machine.h"
#include "qapi/qapi-commands-misc.h"
#include "qapi/qapi-events-run-state.h"
#include "qapi/qmp/qerror.h"
#include "exec/gdbstub.h"
#include "accel/accel-cpu-ops.h"
#include "system/hw_accel.h"
#include "exec/cpu-common.h"
#include "qemu/thread.h"
#include "qemu/main-loop.h"
#include "qemu/plugin.h"
#include "system/cpus.h"
#include "qemu/guest-random.h"
#include "hw/nmi.h"
#include "system/replay.h"
#include "system/runstate.h"
#include "system/cpu-timers.h"
#include "system/whpx.h"
#include "hw/boards.h"
#include "hw/hw.h"
#include "trace.h"

#ifdef CONFIG_LINUX

#include <sys/prctl.h>

#ifndef PR_MCE_KILL
#define PR_MCE_KILL 33
#endif

#ifndef PR_MCE_KILL_SET
#define PR_MCE_KILL_SET 1
#endif

#ifndef PR_MCE_KILL_EARLY
#define PR_MCE_KILL_EARLY 1
#endif

#endif /* CONFIG_LINUX */

/* The Big QEMU Lock (BQL) */
static QemuMutex bql;

/*
 * The chosen accelerator is supposed to register this.
 */
static const AccelOpsClass *cpus_accel;

bool cpu_is_stopped(CPUState *cpu)
{
    return cpu->stopped || !runstate_is_running();
}

bool cpu_work_list_empty(CPUState *cpu)
{
    return QSIMPLEQ_EMPTY_ATOMIC(&cpu->work_list);
}

bool cpu_thread_is_idle(CPUState *cpu)
{
    if (cpu->stop || !cpu_work_list_empty(cpu)) {
        return false;
    }
    if (cpu_is_stopped(cpu)) {
        return true;
    }
    if (!cpu->halted || cpu_has_work(cpu)) {
        return false;
    }
    if (cpus_accel->cpu_thread_is_idle) {
        return cpus_accel->cpu_thread_is_idle(cpu);
    }
    return true;
}

bool all_cpu_threads_idle(void)
{
    CPUState *cpu;

    CPU_FOREACH(cpu) {
        if (!cpu_thread_is_idle(cpu)) {
            return false;
        }
    }
    return true;
}

/***********************************************************/
void hw_error(const char *fmt, ...)
{
    va_list ap;
    CPUState *cpu;

    va_start(ap, fmt);
    fprintf(stderr, "qemu: hardware error: ");
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
    CPU_FOREACH(cpu) {
        fprintf(stderr, "CPU #%d:\n", cpu->cpu_index);
        cpu_dump_state(cpu, stderr, CPU_DUMP_FPU);
    }
    va_end(ap);
    abort();
}

void cpu_synchronize_all_states(void)
{
    CPUState *cpu;

    CPU_FOREACH(cpu) {
        cpu_synchronize_state(cpu);
    }
}

void cpu_synchronize_all_post_reset(void)
{
    CPUState *cpu;

    CPU_FOREACH(cpu) {
        cpu_synchronize_post_reset(cpu);
    }
}

void cpu_synchronize_all_post_init(void)
{
    CPUState *cpu;

    CPU_FOREACH(cpu) {
        cpu_synchronize_post_init(cpu);
    }
}

void cpu_synchronize_all_pre_loadvm(void)
{
    CPUState *cpu;

    CPU_FOREACH(cpu) {
        cpu_synchronize_pre_loadvm(cpu);
    }
}

void cpu_synchronize_state(CPUState *cpu)
{
    if (cpus_accel->synchronize_state) {
        cpus_accel->synchronize_state(cpu);
    }
}

void cpu_synchronize_post_reset(CPUState *cpu)
{
    if (cpus_accel->synchronize_post_reset) {
        cpus_accel->synchronize_post_reset(cpu);
    }
}

void cpu_synchronize_post_init(CPUState *cpu)
{
    if (cpus_accel->synchronize_post_init) {
        cpus_accel->synchronize_post_init(cpu);
    }
}

void cpu_synchronize_pre_loadvm(CPUState *cpu)
{
    if (cpus_accel->synchronize_pre_loadvm) {
        cpus_accel->synchronize_pre_loadvm(cpu);
    }
}

bool cpus_are_resettable(void)
{
    if (cpus_accel->cpus_are_resettable) {
        return cpus_accel->cpus_are_resettable();
    }
    return true;
}

void cpu_exec_reset_hold(CPUState *cpu)
{
    if (cpus_accel->cpu_reset_hold) {
        cpus_accel->cpu_reset_hold(cpu);
    }
}

int64_t cpus_get_virtual_clock(void)
{
    /*
     * XXX
     *
     * need to check that cpus_accel is not NULL, because qcow2 calls
     * qemu_get_clock_ns(CLOCK_VIRTUAL) without any accel initialized and
     * with ticks disabled in some io-tests:
     * 030 040 041 060 099 120 127 140 156 161 172 181 191 192 195 203 229 249 256 267
     *
     * is this expected?
     *
     * XXX
     */
    if (cpus_accel && cpus_accel->get_virtual_clock) {
        return cpus_accel->get_virtual_clock();
    }
    return cpu_get_clock();
}

/*
 * Signal the new virtual time to the accelerator. This is only needed
 * by accelerators that need to track the changes as we warp time.
 */
void cpus_set_virtual_clock(int64_t new_time)
{
    if (cpus_accel && cpus_accel->set_virtual_clock) {
        cpus_accel->set_virtual_clock(new_time);
    }
}

/*
 * return the time elapsed in VM between vm_start and vm_stop.  Unless
 * icount is active, cpus_get_elapsed_ticks() uses units of the host CPU cycle
 * counter.
 */
int64_t cpus_get_elapsed_ticks(void)
{
    if (cpus_accel->get_elapsed_ticks) {
        return cpus_accel->get_elapsed_ticks();
    }
    return cpu_get_ticks();
}

void cpu_set_interrupt(CPUState *cpu, int mask)
{
    /* Pairs with cpu_test_interrupt(). */
    qatomic_or(&cpu->interrupt_request, mask);
}

void generic_handle_interrupt(CPUState *cpu, int mask)
{
    cpu_set_interrupt(cpu, mask);

    if (!qemu_cpu_is_self(cpu)) {
        qemu_cpu_kick(cpu);
    }
}

void cpu_interrupt(CPUState *cpu, int mask)
{
    g_assert(bql_locked());

    cpus_accel->handle_interrupt(cpu, mask);
}

/*
 * True if the vm was previously suspended, and has not been woken or reset.
 */
static int vm_was_suspended;

void vm_set_suspended(bool suspended)
{
    vm_was_suspended = suspended;
}

bool vm_get_suspended(void)
{
    return vm_was_suspended;
}

static int do_vm_stop(RunState state, bool send_stop)
{
    int ret = 0;
    RunState oldstate = runstate_get();
#ifdef __ANDROID__
    {
        extern int __android_log_print(int prio, const char *tag, const char *fmt, ...);
        __android_log_print(4, "hakuX-watchdog",
                            "do_vm_stop: new=%d old=%d send=%d", state, oldstate, send_stop);
    }
#endif

    if (runstate_is_live(oldstate)) {
        vm_was_suspended = (oldstate == RUN_STATE_SUSPENDED);
        runstate_set(state);
        cpu_disable_ticks();
        if (oldstate == RUN_STATE_RUNNING) {
            pause_all_vcpus();
        }
        ret = vm_state_notify(0, state);
        if (send_stop) {
            qapi_event_send_stop();
        }
    }

    bdrv_drain_all();
    /*
     * Even if vm_state_notify() return failure,
     * it would be better to flush as before.
     */
    ret |= bdrv_flush_all();
    trace_vm_stop_flush_all(ret);

    return ret;
}

/* Special vm_stop() variant for terminating the process.  Historically clients
 * did not expect a QMP STOP event and so we need to retain compatibility.
 */
int vm_shutdown(void)
{
    return do_vm_stop(RUN_STATE_SHUTDOWN, false);
}

bool cpu_can_run(CPUState *cpu)
{
    if (cpu->stop) {
        return false;
    }
    if (cpu_is_stopped(cpu)) {
        return false;
    }
    return true;
}

void cpu_handle_guest_debug(CPUState *cpu)
{
    if (replay_running_debug()) {
        if (!cpu->singlestep_enabled) {
            /*
             * Report about the breakpoint and
             * make a single step to skip it
             */
            replay_breakpoint();
            cpu_single_step(cpu, SSTEP_ENABLE);
        } else {
            cpu_single_step(cpu, 0);
        }
    } else {
        gdb_set_stop_cpu(cpu);
        qemu_system_debug_request();
        cpu->stopped = true;
    }
}

#ifdef CONFIG_LINUX
static void sigbus_reraise(void)
{
    sigset_t set;
    struct sigaction action;

    memset(&action, 0, sizeof(action));
    action.sa_handler = SIG_DFL;
    if (!sigaction(SIGBUS, &action, NULL)) {
        raise(SIGBUS);
        sigemptyset(&set);
        sigaddset(&set, SIGBUS);
        pthread_sigmask(SIG_UNBLOCK, &set, NULL);
    }
    perror("Failed to re-raise SIGBUS!");
    abort();
}

static void sigbus_handler(int n, siginfo_t *siginfo, void *ctx)
{
    if (siginfo->si_code != BUS_MCEERR_AO && siginfo->si_code != BUS_MCEERR_AR) {
        sigbus_reraise();
    }

    if (current_cpu) {
        /* Called asynchronously in VCPU thread.  */
        if (kvm_on_sigbus_vcpu(current_cpu, siginfo->si_code, siginfo->si_addr)) {
            sigbus_reraise();
        }
    } else {
        /* Called synchronously (via signalfd) in main thread.  */
        if (kvm_on_sigbus(siginfo->si_code, siginfo->si_addr)) {
            sigbus_reraise();
        }
    }
}

static void qemu_init_sigbus(void)
{
    struct sigaction action;

    /*
     * ALERT: when modifying this, take care that SIGBUS forwarding in
     * qemu_prealloc_mem() will continue working as expected.
     */
    memset(&action, 0, sizeof(action));
    action.sa_flags = SA_SIGINFO;
    action.sa_sigaction = sigbus_handler;
    sigaction(SIGBUS, &action, NULL);

    prctl(PR_MCE_KILL, PR_MCE_KILL_SET, PR_MCE_KILL_EARLY, 0, 0);
}
#else /* !CONFIG_LINUX */
static void qemu_init_sigbus(void)
{
}
#endif /* !CONFIG_LINUX */

static QemuThread io_thread;

/* cpu creation */
static QemuCond qemu_cpu_cond;
/* system init */
static QemuCond qemu_pause_cond;

void qemu_init_cpu_loop(void)
{
    qemu_init_sigbus();
    qemu_cond_init(&qemu_cpu_cond);
    qemu_cond_init(&qemu_pause_cond);
    qemu_mutex_init(&bql);

    qemu_thread_get_self(&io_thread);
}

void run_on_cpu(CPUState *cpu, run_on_cpu_func func, run_on_cpu_data data)
{
    do_run_on_cpu(cpu, func, data, &bql);
}

static void qemu_cpu_stop(CPUState *cpu, bool exit)
{
    g_assert(qemu_cpu_is_self(cpu));
    cpu->stop = false;
    cpu->stopped = true;
    if (exit) {
        cpu_exit(cpu);
    }
    qemu_cond_broadcast(&qemu_pause_cond);
}

void qemu_process_cpu_events_common(CPUState *cpu)
{
    qatomic_set_mb(&cpu->thread_kicked, false);
    if (cpu->stop) {
        qemu_cpu_stop(cpu, false);
    }
    process_queued_cpu_work(cpu);
}

#ifdef XBOX
/*
 * #525 HAKUX_IDLE_HALT: sleep the vCPU in the guest kernel's idle loop.
 *
 * The kernel idles in NT's idiom, sti; nop; nop; cli; <test>; jz, and never
 * executes hlt, so the vCPU thread spins at ~94% on-CPU while the guest is
 * idle 52-66% of the time (docs/lanes/retreason425/NOTES.md, sections 6-8).
 * With HAKUX_IDLE_HALT=1 the translator gives the second nop hlt semantics
 * (helper_hakux_idle_hlt): EIP past it, halted = 1, EXCP_HLT. The sti shadow
 * is over and IF = 1 there, so an interrupt is taken before the cli, where
 * the spinning loop would have taken it.
 *
 * The sleep is bounded. An idiom halt waits on halt_cond for at most
 * IH_TIMEOUT_MS; on a timeout the vCPU is un-halted and runs the loop once
 * more (and halts again), so a wake nothing delivers costs at most 1 ms
 * instead of hanging the guest. The halt is armed only once the PIT (vector
 * 0x30) has been taken, so an early-boot idle before the timer runs spins as
 * before. A real hlt keeps QEMU's unbounded wait.
 *
 * Wakes come through the ordinary path: device IRQ -> PIC -> cpu_interrupt
 * (asserts the BQL) -> tcg_handle_interrupt -> qemu_cpu_kick -> halt_cond.
 * tcg_handle_interrupt reports the first kick of each halt here, with the
 * NV2A units that had an enabled interrupt pending (hakux_nv2a_irq_units),
 * which classes the wake; the time from that kick to the vCPU leaving the
 * wait is the raise-to-run latency the halt adds.
 *
 * One [idlehalt] line per 2 s (tag hakuX), from the vCPU thread, whether
 * the halt is on or not (so an A arm reads the same host columns):
 *   on (HAKUX_IDLE_HALT), run_us and rq_us (this thread's on-CPU and
 *   run-queue wait time from /proc/thread-self/schedstat; run_us / span_us
 *   is the vCPU's on-CPU share), halts, pc (the cli of the first armed
 *   halt) and xpc (halts at any other pc: the idiom found somewhere that is
 *   not the idle loop), imm (halted with work already pending: no sleep),
 *   wake classes pg (PGRAPH ERROR, the push-buffer callback), pgo (other
 *   PGRAPH), vb (vblank), fifo (PFIFO), ot (no NV2A unit: PIT, USB, ...),
 *   to (timeouts, idle), tp (timeouts with work pending and no kick seen:
 *   a missed wake), tr (timeouts with work pending after a kick: the
 *   timedwait race), slept_us, pit (halts whose last interrupt was the PIT),
 *   and the raise-to-run histogram (us: <5 <10 <20 <50 <100 <200 >=200)
 *   and maximum for pg (lpg, lpgmax) and for all kicked wakes (lall).
 */
#include "qemu/timer.h"
#ifdef __ANDROID__
#include <android/log.h>
#define IH_LOG(...) __android_log_print(ANDROID_LOG_WARN, "hakuX", __VA_ARGS__)
#else
#define IH_LOG(...) do { \
        fprintf(stderr, __VA_ARGS__); fprintf(stderr, "\n"); } while (0)
#endif

#define IH_TIMEOUT_MS 1
/* Raise-to-run buckets, us: <5 <10 <20 <50 <100 <200 >=200. */
#define IH_LAT_BINS 7
static const int ih_lat_edge[IH_LAT_BINS - 1] = { 5, 10, 20, 50, 100, 200 };
#define IH_WINDOW_NS 2000000000LL

uint32_t hakux_nv2a_irq_units(void);

enum { IH_PG, IH_PGO, IH_VB, IH_FIFO, IH_OT, IH_NCLASS };
static const char *const ih_class_name[IH_NCLASS] = {
    "pg", "pgo", "vb", "fifo", "ot"
};

static int ih_enabled = -1;         /* HAKUX_IDLE_HALT, read once */
static bool ih_armed;               /* the PIT has been taken */
static bool ih_on;                  /* an idiom halt is in force */
static int64_t ih_t0;               /* its start */
static int64_t ih_kick_ns;          /* its first kick, 0 none */
static int ih_kick_class;
static uint32_t ih_pc;              /* the cli of the first armed halt */

static struct {
    uint64_t halts, xpc, imm, pit, to, tp, tr, slept_ns;
    uint64_t wake[IH_NCLASS];
    uint32_t lat_pg[IH_LAT_BINS], lat_all[IH_LAT_BINS];
    uint64_t lat_pg_max, lat_all_max;
} ih;
static int64_t ih_window_t;
static unsigned ih_window;

bool hakux_idle_halt_enabled(void)
{
    if (ih_enabled < 0) {
        const char *v = getenv("HAKUX_IDLE_HALT");
        ih_enabled = !v || v[0] != '0';    /* pixel arm only: default on */
        if (ih_enabled) {
            IH_LOG("[idlehalt] on: timeout %d ms, armed at the first PIT",
                   IH_TIMEOUT_MS);
        }
    }
    return ih_enabled;
}

static int ih_lat_bin(uint64_t ns)
{
    int i = 0;

    while (i < IH_LAT_BINS - 1 && ns >= ih_lat_edge[i] * 1000ull) {
        i++;
    }
    return i;
}

static int ih_hist(char *buf, size_t len, const uint32_t *h)
{
    return snprintf(buf, len, "%u/%u/%u/%u/%u/%u/%u",
                    h[0], h[1], h[2], h[3], h[4], h[5], h[6]);
}

/* This thread's schedstat: on-CPU ns and run-queue wait ns; false if none. */
static bool ih_schedstat(uint64_t *run, uint64_t *wait)
{
    char buf[96];
    FILE *f = fopen("/proc/thread-self/schedstat", "r");
    bool ok;

    if (!f) {
        return false;
    }
    ok = fgets(buf, sizeof(buf), f)
         && sscanf(buf, "%" SCNu64 " %" SCNu64, run, wait) == 2;
    fclose(f);
    return ok;
}

static void ih_tick(void)
{
    static uint64_t run0, wait0;
    static bool have0;
    int64_t now = get_clock();
    uint64_t run = 0, wait = 0;
    int64_t drun = -1, dwait = -1;
    bool have;
    char wk[128], lpg[64], lall[64];
    int off = 0;

    if (ih_window_t && now - ih_window_t < IH_WINDOW_NS) {
        return;
    }
    have = ih_schedstat(&run, &wait);
    if (!ih_window_t) {
        hakux_idle_halt_enabled();
        ih_window_t = now;
        run0 = run;
        wait0 = wait;
        have0 = have;
        return;
    }
    if (have && have0) {
        drun = (run - run0) / 1000;
        dwait = (wait - wait0) / 1000;
    }
    run0 = run;
    wait0 = wait;
    have0 = have;
    for (int i = 0; i < IH_NCLASS; i++) {
        off += snprintf(wk + off, sizeof(wk) - off, " %s=%" PRIu64,
                        ih_class_name[i], ih.wake[i]);
    }
    ih_hist(lpg, sizeof(lpg), ih.lat_pg);
    ih_hist(lall, sizeof(lall), ih.lat_all);
    IH_LOG("[idlehalt] w=%u on=%d span_us=%" PRId64 " run_us=%" PRId64
           " rq_us=%" PRId64 " halts=%" PRIu64 " pc=%08x xpc=%" PRIu64
           " imm=%" PRIu64 "%s to=%" PRIu64 " tp=%" PRIu64 " tr=%" PRIu64
           " slept_us=%" PRIu64 " pit=%" PRIu64
           " lpg=%s lpgmax=%" PRIu64 " lall=%s lallmax=%" PRIu64,
           ih_window, ih_enabled > 0, (now - ih_window_t) / 1000, drun, dwait,
           ih.halts, ih_pc, ih.xpc, ih.imm, wk,
           ih.to, ih.tp, ih.tr, ih.slept_ns / 1000, ih.pit,
           lpg, ih.lat_pg_max / 1000, lall, ih.lat_all_max / 1000);
    memset(&ih, 0, sizeof(ih));
    ih_window_t = now;
    ih_window++;
}

/*
 * helper_hakux_idle_hlt, at the idiom's second nop with IF = 1: true to halt.
 * @last_vec is the vector of the last interrupt taken (hakux_rr425_vec),
 * @pc the EIP the halt resumes at (the idiom's cli).
 */
bool hakux_idle_halt_enter(CPUState *cpu, int last_vec, uint32_t pc)
{
    if (!ih_armed) {
        if (last_vec != 0x30) {
            return false;
        }
        ih_armed = true;
        ih_pc = pc;
        IH_LOG("[idlehalt] armed at %08x", pc);
    }
    ih.halts++;
    ih.xpc += pc != ih_pc;
    ih.pit += last_vec == 0x30;
    ih_t0 = get_clock();
    qatomic_set(&ih_kick_ns, 0);
    /* Read by the kicking thread; the halt itself is ordered by the BQL. */
    qatomic_set_mb(&ih_on, true);
    return true;
}

/* tcg_handle_interrupt is kicking @cpu from another thread (BQL held). */
void hakux_idle_halt_kick(CPUState *cpu, int mask)
{
    uint32_t u;

    if (!qatomic_read(&ih_on) || ih_kick_ns
        || !(mask & CPU_INTERRUPT_HARD)) {
        return;
    }
    ih_kick_ns = get_clock();
    u = hakux_nv2a_irq_units();
    ih_kick_class = (u & 64) ? IH_PG : (u & 4) ? IH_PGO : (u & 2) ? IH_VB
                    : (u & 1) ? IH_FIFO : IH_OT;
}

/* The idiom halt ended with the vCPU runnable. */
static void ih_wake(CPUState *cpu, bool slept)
{
    int64_t now = get_clock();

    ih_on = false;
    ih.slept_ns += now - ih_t0;
    if (!slept) {
        ih.imm++;
    } else if (ih_kick_ns) {
        uint64_t lat = now - ih_kick_ns;
        int bin = ih_lat_bin(lat);

        ih.wake[ih_kick_class]++;
        ih.lat_all[bin]++;
        ih.lat_all_max = MAX(ih.lat_all_max, lat);
        if (ih_kick_class == IH_PG) {
            ih.lat_pg[bin]++;
            ih.lat_pg_max = MAX(ih.lat_pg_max, lat);
        }
    } else {
        ih.wake[IH_OT]++;       /* runnable with no HARD kick seen */
    }
}

/*
 * One wait of a halted @cpu on @cond (BQL held): QEMU's unbounded wait for a
 * real hlt, a bounded one for an idiom halt. True when the bounded wait timed
 * out and the vCPU was un-halted to run the idle loop again.
 */
bool hakux_idle_halt_wait(CPUState *cpu, QemuCond *cond)
{
    if (!ih_on) {
        qemu_cond_wait(cond, &bql);
        return false;
    }
    if (qemu_cond_timedwait(cond, &bql, IH_TIMEOUT_MS)) {
        return false;
    }
    if (!cpu->halted || !ih_on) {
        return false;
    }
    if (cpu_has_work(cpu)) {
        /* Runnable although no signal arrived. */
        if (ih_kick_ns) {
            ih.tr++;
        } else {
            ih.tp++;
        }
        return false;
    }
    ih.to++;
    ih.slept_ns += get_clock() - ih_t0;
    ih_on = false;
    cpu->halted = 0;
    return true;
}

/*
 * After the wait loop, each pass of the vCPU thread's loop: account an idiom
 * halt that has ended, and print the window when it is due.
 */
void hakux_idle_halt_after_wait(CPUState *cpu, bool slept)
{
    if (ih_on && (!cpu->halted || cpu_has_work(cpu))) {
        ih_wake(cpu, slept);
    }
    ih_tick();
}
#endif

void qemu_process_cpu_events(CPUState *cpu)
{
    bool slept = false;

    qatomic_set(&cpu->exit_request, false);
    while (cpu_thread_is_idle(cpu)) {
        if (!slept) {
            slept = true;
            qemu_plugin_vcpu_idle_cb(cpu);
        }
#ifdef XBOX
        if (hakux_idle_halt_wait(cpu, cpu->halt_cond)) {
            break;
        }
#else
        qemu_cond_wait(cpu->halt_cond, &bql);
#endif
    }
#ifdef XBOX
    hakux_idle_halt_after_wait(cpu, slept);
#endif
    if (slept) {
        qemu_plugin_vcpu_resume_cb(cpu);
    }

    qemu_process_cpu_events_common(cpu);
}

void cpus_kick_thread(CPUState *cpu)
{
    if (qatomic_read(&cpu->thread_kicked)) {
        return;
    }
    qatomic_set(&cpu->thread_kicked, true);

#ifndef _WIN32
    int err = pthread_kill(cpu->thread->thread, SIG_IPI);
    if (err && err != ESRCH) {
        fprintf(stderr, "qemu:%s: %s", __func__, strerror(err));
        exit(1);
    }
#else
    qemu_sem_post(&cpu->sem);
#endif
}

void qemu_cpu_kick(CPUState *cpu)
{
    qemu_cond_broadcast(cpu->halt_cond);
    if (cpus_accel->kick_vcpu_thread) {
        cpus_accel->kick_vcpu_thread(cpu);
    } else { /* default */
        cpus_kick_thread(cpu);
    }
}

void qemu_cpu_kick_self(void)
{
    assert(current_cpu);
    cpus_kick_thread(current_cpu);
}

bool qemu_cpu_is_self(CPUState *cpu)
{
    return qemu_thread_is_self(cpu->thread);
}

bool qemu_in_vcpu_thread(void)
{
    return current_cpu && qemu_cpu_is_self(current_cpu);
}

QEMU_DEFINE_STATIC_CO_TLS(bool, bql_locked)

bool mutex_is_bql(QemuMutex *mutex)
{
    return mutex == &bql;
}

void bql_update_status(bool locked)
{
    /* This function should only be used when an update happened.. */
    assert(bql_locked() != locked);
    set_bql_locked(locked);
}

static uint32_t bql_unlock_blocked;

void bql_block_unlock(bool increase)
{
    uint32_t new_value;

    assert(bql_locked());

    /* check for overflow! */
    new_value = bql_unlock_blocked + increase - !increase;
    assert((new_value > bql_unlock_blocked) == increase);
    bql_unlock_blocked = new_value;
}

bool bql_locked(void)
{
    return get_bql_locked();
}

bool qemu_in_main_thread(void)
{
    return bql_locked();
}

void rust_bql_mock_lock(void)
{
    error_report("This function should be used only from tests");
    abort();
}

/*
 * The BQL is taken from so many places that it is worth profiling the
 * callers directly, instead of funneling them all through a single function.
 */
void bql_lock_impl(const char *file, int line)
{
    QemuMutexLockFunc bql_lock_fn = qatomic_read(&bql_mutex_lock_func);

    g_assert(!bql_locked());
    bql_lock_fn(&bql, file, line);
}

void bql_unlock(void)
{
    g_assert(bql_locked());
    g_assert(!bql_unlock_blocked);
    qemu_mutex_unlock(&bql);
}

void qemu_cond_wait_bql(QemuCond *cond)
{
    qemu_cond_wait(cond, &bql);
}

void qemu_cond_timedwait_bql(QemuCond *cond, int ms)
{
    qemu_cond_timedwait(cond, &bql, ms);
}

/* signal CPU creation */
void cpu_thread_signal_created(CPUState *cpu)
{
    cpu->created = true;
    qemu_cond_signal(&qemu_cpu_cond);
}

/* signal CPU destruction */
void cpu_thread_signal_destroyed(CPUState *cpu)
{
    cpu->created = false;
    qemu_cond_signal(&qemu_cpu_cond);
}

void cpu_pause(CPUState *cpu)
{
    if (qemu_cpu_is_self(cpu)) {
        qemu_cpu_stop(cpu, true);
    } else {
        cpu->stop = true;
        cpu_exit(cpu);
    }
}

void cpu_resume(CPUState *cpu)
{
    cpu->stop = false;
    cpu->stopped = false;
    qemu_cpu_kick(cpu);
}

static bool all_vcpus_paused(void)
{
    CPUState *cpu;

    CPU_FOREACH(cpu) {
        if (!cpu->stopped) {
            return false;
        }
    }

    return true;
}

void pause_all_vcpus(void)
{
    CPUState *cpu;

    qemu_clock_enable(QEMU_CLOCK_VIRTUAL, false);
    CPU_FOREACH(cpu) {
        cpu_pause(cpu);
    }

    /* We need to drop the replay_lock so any vCPU threads woken up
     * can finish their replay tasks
     */
    replay_mutex_unlock();

    while (!all_vcpus_paused()) {
        qemu_cond_wait(&qemu_pause_cond, &bql);
        /* FIXME: is this needed? */
        CPU_FOREACH(cpu) {
            qemu_cpu_kick(cpu);
        }
    }

    bql_unlock();
    replay_mutex_lock();
    bql_lock();
}

void resume_all_vcpus(void)
{
    CPUState *cpu;

    if (!runstate_is_running()) {
        return;
    }

    qemu_clock_enable(QEMU_CLOCK_VIRTUAL, true);
    CPU_FOREACH(cpu) {
        cpu_resume(cpu);
    }
}

void cpu_remove_sync(CPUState *cpu)
{
    cpu->stop = true;
    cpu->unplug = true;
    cpu_exit(cpu);
    bql_unlock();
    qemu_thread_join(cpu->thread);
    bql_lock();
}

void cpus_register_accel(const AccelOpsClass *ops)
{
    assert(ops != NULL);
    assert(ops->create_vcpu_thread != NULL); /* mandatory */
    assert(ops->handle_interrupt);

    cpus_accel = ops;
}

const AccelOpsClass *cpus_get_accel(void)
{
    /* broken if we call this early */
    assert(cpus_accel);
    return cpus_accel;
}

void qemu_init_vcpu(CPUState *cpu)
{
    MachineState *ms = MACHINE(qdev_get_machine());

    cpu->nr_threads =  ms->smp.threads;
    cpu->stopped = true;
    cpu->random_seed = qemu_guest_random_seed_thread_part1();

    if (!cpu->as) {
        /* If the target cpu hasn't set up any address spaces itself,
         * give it the default one.
         */
        cpu->num_ases = 1;
        cpu_address_space_init(cpu, 0, "cpu-memory", cpu->memory);
    }

    /* accelerators all implement the AccelOpsClass */
    g_assert(cpus_accel != NULL && cpus_accel->create_vcpu_thread != NULL);
    cpus_accel->create_vcpu_thread(cpu);

    while (!cpu->created) {
        qemu_cond_wait(&qemu_cpu_cond, &bql);
    }
}

void cpu_stop_current(void)
{
    if (current_cpu) {
        current_cpu->stop = true;
        cpu_exit(current_cpu);
    }
}

int vm_stop(RunState state)
{
#ifdef __ANDROID__
    {
        /* Use android log directly since fprintf may not reach logcat */
        extern int __android_log_print(int prio, const char *tag, const char *fmt, ...);
        __android_log_print(4 /*ANDROID_LOG_INFO*/, "hakuX-watchdog",
                            "vm_stop: state=%d vcpu=%d", state, qemu_in_vcpu_thread());
    }
#endif
    if (qemu_in_vcpu_thread()) {
        qemu_system_vmstop_request_prepare();
        qemu_system_vmstop_request(state);
        /*
         * FIXME: should not return to device code in case
         * vm_stop() has been requested.
         */
        cpu_stop_current();
        return 0;
    }

    return do_vm_stop(state, true);
}

/**
 * Prepare for (re)starting the VM.
 * Returns 0 if the vCPUs should be restarted, -1 on an error condition,
 * and 1 otherwise.
 */
int vm_prepare_start(bool step_pending)
{
    int ret = vm_was_suspended ? 1 : 0;
    RunState state = vm_was_suspended ? RUN_STATE_SUSPENDED : RUN_STATE_RUNNING;
    RunState requested;

    qemu_vmstop_requested(&requested);
    if (runstate_is_running() && requested == RUN_STATE__MAX) {
        return -1;
    }

    /* Ensure that a STOP/RESUME pair of events is emitted if a
     * vmstop request was pending.  The BLOCK_IO_ERROR event, for
     * example, according to documentation is always followed by
     * the STOP event.
     */
    if (runstate_is_running()) {
        qapi_event_send_stop();
        qapi_event_send_resume();
        return -1;
    }

    /*
     * WHPX accelerator needs to know whether we are going to step
     * any CPUs, before starting the first one.
     */
    accel_pre_resume(MACHINE(qdev_get_machine()), step_pending);

    /* We are sending this now, but the CPUs will be resumed shortly later */
    qapi_event_send_resume();

    cpu_enable_ticks();
    runstate_set(state);
    vm_state_notify(1, state);
    vm_was_suspended = false;
    return ret;
}

void vm_start(void)
{
    if (!vm_prepare_start(false)) {
        resume_all_vcpus();
    }
}

void vm_resume(RunState state)
{
    if (runstate_is_live(state)) {
        vm_start();
    } else {
        runstate_set(state);
    }
}

/* does a state transition even if the VM is already stopped,
   current state is forgotten forever */
int vm_stop_force_state(RunState state)
{
    if (runstate_is_live(runstate_get())) {
        return vm_stop(state);
    } else {
        int ret;
        runstate_set(state);

        bdrv_drain_all();
        /* Make sure to return an error if the flush in a previous vm_stop()
         * failed. */
        ret = bdrv_flush_all();
        trace_vm_stop_flush_all(ret);
        return ret;
    }
}

void qmp_memsave(uint64_t addr, uint64_t size, const char *filename,
                 bool has_cpu, int64_t cpu_index, Error **errp)
{
    FILE *f;
    uint64_t l;
    CPUState *cpu;
    uint8_t buf[1024];
    uint64_t orig_addr = addr, orig_size = size;

    if (!has_cpu) {
        cpu_index = 0;
    }

    cpu = qemu_get_cpu(cpu_index);
    if (cpu == NULL) {
        error_setg(errp, QERR_INVALID_PARAMETER_VALUE, "cpu-index",
                   "a CPU number");
        return;
    }

    f = fopen(filename, "wb");
    if (!f) {
        error_setg_file_open(errp, errno, filename);
        return;
    }

    while (size != 0) {
        l = sizeof(buf);
        if (l > size)
            l = size;
        if (cpu_memory_rw_debug(cpu, addr, buf, l, 0) != 0) {
            error_setg(errp, "Invalid addr 0x%016" PRIx64 "/size %" PRIu64
                             " specified", orig_addr, orig_size);
            goto exit;
        }
        if (fwrite(buf, 1, l, f) != l) {
            error_setg(errp, "writing memory to '%s' failed",
                       filename);
            goto exit;
        }
        addr += l;
        size -= l;
    }

exit:
    fclose(f);
}

void qmp_pmemsave(uint64_t addr, uint64_t size, const char *filename,
                  Error **errp)
{
    FILE *f;
    uint64_t l;
    uint8_t buf[1024];

    f = fopen(filename, "wb");
    if (!f) {
        error_setg_file_open(errp, errno, filename);
        return;
    }

    while (size != 0) {
        l = sizeof(buf);
        if (l > size)
            l = size;
        cpu_physical_memory_read(addr, buf, l);
        if (fwrite(buf, 1, l, f) != l) {
            error_setg(errp, "writing memory to '%s' failed",
                       filename);
            goto exit;
        }
        addr += l;
        size -= l;
    }

exit:
    fclose(f);
}

void qmp_inject_nmi(Error **errp)
{
    nmi_monitor_handle(monitor_get_cpu_index(monitor_cur()), errp);
}

