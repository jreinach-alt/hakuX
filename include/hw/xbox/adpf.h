/*
 * #544 ADPF performance-hint sessions for the emulator's hot threads.
 *
 * Android only; every entry point is a no-op elsewhere, and on Android
 * unless HAKUX_ADPF is set (see hw/xbox/adpf.c).
 */
#ifndef HW_XBOX_ADPF_H
#define HW_XBOX_ADPF_H

#include "qemu/thread.h"

typedef enum HakuxAdpfRole {
    HAKUX_ADPF_VCPU,        /* the TCG vCPU thread: session 0 */
    HAKUX_ADPF_PFIFO,       /* pusher, puller, pgraph methods: session 1 */
    HAKUX_ADPF_RENDER,      /* the Vulkan render thread: session 1 */
    HAKUX_ADPF_NROLES
} HakuxAdpfRole;

/* The calling thread has started in this role. */
void hakux_adpf_thread_start(HakuxAdpfRole role);

/* Another, already running, thread has this role. */
void hakux_adpf_thread_add(HakuxAdpfRole role, QemuThread *thread);

/*
 * Session 1 (PFIFO plus render) has all the threads it will get: with no
 * setThreads below API 34, its session is created only after this.
 */
void hakux_adpf_gpu_threads_done(void);

/* One guest flip (FLIP_STALL), from the PFIFO thread. */
void hakux_adpf_flip(int64_t vblank_period_ns);

#endif
