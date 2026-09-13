/*
 * QEMU MCPX Audio Processing Unit implementation
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2018-2019 Jannik Vogel
 * Copyright (c) 2019-2025 Matt Borgerson
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#include "apu_int.h"

MCPXAPUState *g_state; // Used via debug handlers

static void update_irq(MCPXAPUState *d)
{
    if (d->regs[NV_PAPU_FECTL] & NV_PAPU_FECTL_FEMETHMODE_TRAPPED) {
        qatomic_or(&d->regs[NV_PAPU_ISTS], NV_PAPU_ISTS_FETINTSTS);
    }
    if ((d->regs[NV_PAPU_IEN] & NV_PAPU_ISTS_GINTSTS) &&
        ((d->regs[NV_PAPU_ISTS] & ~NV_PAPU_ISTS_GINTSTS) &
         d->regs[NV_PAPU_IEN])) {
        qatomic_or(&d->regs[NV_PAPU_ISTS], NV_PAPU_ISTS_GINTSTS);
        // fprintf(stderr, "mcpx irq raise ien=%08x ists=%08x\n",
        //         d->regs[NV_PAPU_IEN], d->regs[NV_PAPU_ISTS]);
        pci_irq_assert(PCI_DEVICE(d));
    } else {
        qatomic_and(&d->regs[NV_PAPU_ISTS], ~NV_PAPU_ISTS_GINTSTS);
        // fprintf(stderr, "mcpx irq lower ien=%08x ists=%08x\n",
        //         d->regs[NV_PAPU_IEN], d->regs[NV_PAPU_ISTS]);
        pci_irq_deassert(PCI_DEVICE(d));
    }
}

static uint64_t mcpx_apu_read(void *opaque, hwaddr addr, unsigned int size)
{
    MCPXAPUState *d = opaque;

    uint64_t r = 0;
    switch (addr) {
    case NV_PAPU_XGSCNT:
        r = qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL) / 100; //???
        break;
    default:
        if (addr < 0x20000) {
            r = qatomic_read(&d->regs[addr]);
        }
        break;
    }

    trace_mcpx_apu_reg_read(addr, size, r);
    return r;
}

static void mcpx_apu_write(void *opaque, hwaddr addr, uint64_t val,
                           unsigned int size)
{
    MCPXAPUState *d = opaque;

    trace_mcpx_apu_reg_write(addr, size, val);

    switch (addr) {
    case NV_PAPU_ISTS:
        /* the bits of the interrupts to clear are written */
        qatomic_and(&d->regs[NV_PAPU_ISTS], ~val);
        update_irq(d);
        qemu_cond_broadcast(&d->cond);
        break;
    case NV_PAPU_FECTL:
    case NV_PAPU_SECTL:
        qatomic_set(&d->regs[addr], val);
        qemu_cond_broadcast(&d->cond);
        break;
    case NV_PAPU_FEMEMDATA:
        /* 'magic write'
         * This value is expected to be written to FEMEMADDR on completion of
         * something to do with notifies. Just do it now :/ */
        stl_le_phys(&address_space_memory, d->regs[NV_PAPU_FEMEMADDR], val);
        // fprintf(stderr, "MAGIC WRITE\n");
        qatomic_set(&d->regs[addr], val);
        break;
    default:
        if (addr < 0x20000) {
            qatomic_set(&d->regs[addr], val);
        }
        break;
    }
}

static const MemoryRegionOps mcpx_apu_mmio_ops = {
    .read = mcpx_apu_read,
    .write = mcpx_apu_write,
};

static int monitor_num_used_bytes(MCPXAPUState *d)
{
    int queued_bytes;
    qemu_spin_lock(&d->monitor.fifo_lock);
    queued_bytes = (int)fifo8_num_used(&d->monitor.fifo);
    qemu_spin_unlock(&d->monitor.fifo_lock);
    return queued_bytes;
}

static void throttle(MCPXAPUState *d)
{
    if (d->ep_frame_div % 8) {
        return;
    }

    if (d->monitor.fifo_capacity_bytes <= 0) {
        return;
    }

    int64_t start_us = qemu_clock_get_us(QEMU_CLOCK_REALTIME);
    int queued_bytes = monitor_num_used_bytes(d);

    while (!qatomic_read(&d->exiting) &&
           queued_bytes >= d->monitor.queued_bytes_high) {
        qemu_cond_timedwait(&d->cond, &d->lock, EP_FRAME_US / 1000);
        if (qatomic_read(&d->exiting)) {
            break;
        }
        queued_bytes = monitor_num_used_bytes(d);
    }

#ifdef __ANDROID__
    /* Android scheduler granularity is often too coarse for the extra
     * low-watermark pacing below and can make speech sound dragged out.
     * Keep FIFO backpressure, but let the output callback set the pace.
     */
    d->next_frame_time_us = 0;
    d->sleep_acc_us += qemu_clock_get_us(QEMU_CLOCK_REALTIME) - start_us;
    return;
#endif

    if (queued_bytes > d->monitor.queued_bytes_low) {
        int64_t now_us = qemu_clock_get_us(QEMU_CLOCK_REALTIME);
        if (d->next_frame_time_us == 0 ||
            now_us - d->next_frame_time_us > EP_FRAME_US) {
            d->next_frame_time_us = now_us;
        }
        while (!qatomic_read(&d->exiting)) {
            now_us = qemu_clock_get_us(QEMU_CLOCK_REALTIME);
            int64_t remaining_ms = (d->next_frame_time_us - now_us) / 1000;
            if (remaining_ms > 0) {
                int sleep_ms = remaining_ms > INT_MAX ? INT_MAX : (int)remaining_ms;
                qemu_cond_timedwait(&d->cond, &d->lock, sleep_ms);
            } else {
                break;
            }
        }
        d->next_frame_time_us += EP_FRAME_US;

        /* Nudge frame timing based on queue level to avoid drifting
         * toward one of the watermarks.
         */
        int mid = (d->monitor.queued_bytes_low + d->monitor.queued_bytes_high) / 2;
        d->next_frame_time_us += (queued_bytes > mid) - (queued_bytes < mid);
    } else {
        d->next_frame_time_us = start_us;
    }

    d->sleep_acc_us += qemu_clock_get_us(QEMU_CLOCK_REALTIME) - start_us;
}

/*
 * Audio capture harness -- see docs/investigations/audio-harness.md.
 *
 * Audio on this project has no golden reference, so the only falsifiable
 * claim available about a gain change is a measured level. This writes the
 * final APU output to a file so levels can be measured rather than judged by
 * ear.
 *
 * The tap is the one funnel both output paths converge on:
 * d->monitor.frame_buf, immediately before it is pushed to the FIFO that
 * feeds SDL (and AAudio on Android). Everything downstream of that is
 * platform plumbing that we do not want folded into the measurement.
 *
 * Format, read out of the source rather than assumed:
 *   - int16_t frame_buf[256][2]           (apu_int.h:104) -- signed 16-bit,
 *     two channels, channel is the minor index, so the file is interleaved
 *     L,R,L,R. Host endian, to match AUDIO_S16SYS below.
 *   - 48000 Hz, 2 channels, AUDIO_S16SYS  (apu.c:342-344)
 *   - one complete buffer per 8 VP frames (vp.c:1885, dsp/gp_ep.c:465)
 *     = 256 stereo frames = 1024 bytes = 5.333 ms (EP_FRAME_US, apu_regs.h:363)
 *
 * The 1-in-8 cadence is buffer geometry, not a sampling choice. Each VP frame
 * fills a 32-sample slice at (ep_frame_div % 8) * 32, so the buffer is
 * complete only on the 8th. Writing it every frame would emit the same block
 * eight times, seven of them partly stale, and the file's sample rate -- not
 * its content -- would then be wrong by 8x.
 *
 * This runs on the audio thread, which is why:
 *   - the environment is read once, in apu_capture_init(), never per frame;
 *   - the handle is opened once and held, not reopened per block;
 *   - an I/O failure latches the capture off, and never asserts: a debug tap
 *     must not be able to kill a run;
 *   - the byte cap is enforced, so a flag left set cannot fill the device.
 */

#ifdef __ANDROID__
#include <android/log.h>
#define APU_CAP_LOG(fmt, ...)                                                 \
    __android_log_print(ANDROID_LOG_INFO, "hakuX-audiocap", fmt, ##__VA_ARGS__)
#else
#define APU_CAP_LOG(fmt, ...)                                                 \
    fprintf(stderr, "mcpx apu: audio capture: " fmt "\n", ##__VA_ARGS__)
#endif

/* ~1.3 s of audio, so the write() rate stays near 4/s instead of 187/s.
 * /sdcard is FUSE-backed on Android and a stall there lands on the audio
 * thread; see the "what it cannot measure" section of the write-up.
 */
#define APU_CAPTURE_BUF_BYTES (256 * 1024)
#define APU_CAPTURE_DEFAULT_MB 64

static struct {
    FILE *fp;
    char *buf;
    uint64_t bytes_written;
    uint64_t byte_limit;
    uint64_t blocks;
} apu_capture;

static void apu_capture_close(const char *why)
{
    if (!apu_capture.fp) {
        return;
    }

    FILE *fp = apu_capture.fp;
    apu_capture.fp = NULL; /* latch off before the slow part */

    fclose(fp);
    g_free(apu_capture.buf);
    apu_capture.buf = NULL;

    APU_CAP_LOG("stopped (%s) after %" PRIu64 " blocks, %" PRIu64 " bytes, "
                "%.3f s of audio",
                why, apu_capture.blocks, apu_capture.bytes_written,
                (double)apu_capture.blocks * 256.0 / 48000.0);
}

static void apu_capture_write(const void *buf, size_t len)
{
    if (apu_capture.bytes_written + len > apu_capture.byte_limit) {
        apu_capture_close("byte cap reached");
        return;
    }

    if (fwrite(buf, len, 1, apu_capture.fp) != 1) {
        /* Deliberately not an assert. Losing the capture is a debug
         * inconvenience; killing the guest's audio thread is a bug.
         */
        APU_CAP_LOG("write failed: %s", strerror(errno));
        apu_capture_close("write error");
        return;
    }

    apu_capture.bytes_written += len;
    apu_capture.blocks++;
}

/*
 * Output starvation accounting -- see docs/investigations/audio-baseline.md.
 *
 * monitor_sink_cb zero-fills whatever the FIFO could not supply and says
 * nothing about it. A chronic partial fill is therefore completely invisible:
 * it reduces loudness at the speaker by its duty cycle, and it does so
 * DOWNSTREAM of the PCM tap, so every level in a capture stays exactly as it
 * was. That combination -- audible, and unmeasurable by the instrument we
 * built to measure audio -- is why this counter exists.
 *
 * It is not covered by g_dbg.utilization, which measures how long the APU
 * thread SLEEPS. A thread can sleep plenty and still miss deadlines in bursts,
 * so a utilization below 1 does not rule starvation out.
 *
 * Threading. These are incremented on the SDL/AAudio callback thread and read
 * on the APU thread, so they are relaxed atomics and never touched under a
 * lock: the callback is a realtime-ish context and must not wait on anything.
 * Nothing here is derived from a pair of counters read at the same instant, so
 * a torn read between two of them costs at worst one slightly wrong log line.
 * They are deliberately NOT written straight into g_dbg, which the APU thread
 * copies wholesale in mcpx_debug_end_frame(); publishing from the reader side
 * keeps that copy single-threaded.
 *
 * File-static rather than a member of MCPXAPUState, following apu_capture
 * above: there is one APU, the counters are diagnostics, and putting them in
 * the device state would drag in a vmstate decision for something that must
 * not survive a savestate anyway.
 */
static struct {
    uint64_t callbacks;      /* every call into monitor_sink_cb */
    uint64_t short_calls;    /* ... that could not be filled from the FIFO */
    uint64_t empty_calls;    /* ... that got NOTHING: a full period of silence */
    uint64_t bytes_asked;
    uint64_t bytes_short;    /* bytes the sink emitted as zero-fill */
    uint64_t max_short;      /* worst single shortfall, in bytes */
} apu_starve;

static void apu_starve_account(int free_b, int copied)
{
    qatomic_set(&apu_starve.callbacks, apu_starve.callbacks + 1);
    qatomic_set(&apu_starve.bytes_asked, apu_starve.bytes_asked + free_b);

    if (copied >= free_b) {
        return;
    }
    uint64_t missing = (uint64_t)(free_b - copied);
    qatomic_set(&apu_starve.short_calls, apu_starve.short_calls + 1);
    qatomic_set(&apu_starve.bytes_short, apu_starve.bytes_short + missing);
    if (copied == 0) {
        qatomic_set(&apu_starve.empty_calls, apu_starve.empty_calls + 1);
    }
    if (missing > apu_starve.max_short) {
        qatomic_set(&apu_starve.max_short, missing);
    }
}

/*
 * Called from the APU thread's existing once-a-second accounting block, not
 * from the callback: logging from a realtime audio callback is how a level
 * measurement turns into a pacing measurement.
 *
 * Reports every 5 s, but only when the interval actually starved -- with two
 * exceptions, both of which exist because "no lines" and "instrument never
 * ran" look identical in a log, and this campaign has already lost two arms
 * and a day to exactly that ambiguity:
 *
 *   - the first report always fires, so a clean run still proves the counter
 *     is alive and says what the device geometry is;
 *   - a heartbeat fires every 30 s regardless, so a long clean run keeps
 *     saying so.
 *
 * Every figure on the line is the DELTA since the last LINE, not a running
 * total and not "since the last time this was called": a cumulative report
 * would make one early burst read as permanent starvation for the rest of the
 * run, and an interval measured from the last call would not match the window
 * the line claims to describe. The one exception is labelled worst-ever.
 *
 * The line records whether the PCM capture was armed, because the capture
 * writes to FUSE-backed storage from the audio thread and can itself cause
 * the starvation being counted. A starvation figure measured with the capture
 * on describes the capture run, not a normal one, and the reader must be able
 * to tell which they are holding.
 */
static void apu_starve_report(MCPXAPUState *d, int64_t now_ms)
{
    static int64_t last_ms;
    static uint64_t last_calls, last_short, last_empty, last_asked, last_bshort;
    static unsigned reports;

    if (last_ms == 0) {
        last_ms = now_ms;
        return;
    }
    if (now_ms - last_ms < 5000) {
        return;
    }

    uint64_t calls = qatomic_read(&apu_starve.callbacks);
    uint64_t shorts = qatomic_read(&apu_starve.short_calls);
    uint64_t empties = qatomic_read(&apu_starve.empty_calls);
    uint64_t asked = qatomic_read(&apu_starve.bytes_asked);
    uint64_t bshort = qatomic_read(&apu_starve.bytes_short);

    uint64_t d_calls = calls - last_calls;
    uint64_t d_short = shorts - last_short;
    uint64_t d_empty = empties - last_empty;
    uint64_t d_asked = asked - last_asked;
    uint64_t d_bshort = bshort - last_bshort;

    bool heartbeat = (reports == 0) || (now_ms - last_ms >= 30000);
    if (d_short || heartbeat) {
        /* The percentage is the one number that matters: it is the fraction of
         * output time replaced by silence, i.e. the loudness the speaker loses
         * that no capture can show.
         */
        APU_CAP_LOG("starve: %llu/%llu callbacks short (%llu empty), "
                    "%llu/%llu bytes zero-filled = %.4f%% of output, "
                    "worst-ever %llu B; device buf %d B, fifo %d B, capture %s",
                    (unsigned long long)d_short, (unsigned long long)d_calls,
                    (unsigned long long)d_empty,
                    (unsigned long long)d_bshort, (unsigned long long)d_asked,
                    d_asked ? 100.0 * (double)d_bshort / (double)d_asked : 0.0,
                    (unsigned long long)qatomic_read(&apu_starve.max_short),
                    d->monitor.device_buffer_bytes,
                    d->monitor.fifo_capacity_bytes,
                    apu_capture.fp ? "ARMED" : "off");
        reports++;
        last_ms = now_ms;
        last_calls = calls;
        last_short = shorts;
        last_empty = empties;
        last_asked = asked;
        last_bshort = bshort;
    }
}

/* ------------------------------------------------------------------------
 * Output level meter: audio_measure.py's statistics, computed in the emulator
 * and reported through logcat.
 *
 * WHY THIS EXISTS. The level of the audio output could be measured in exactly
 * one way -- arm a PCM capture, hold a title, pull 18-24 MB off the device and
 * run docs/testing/audio_measure.py over it. That route has now failed three
 * times for three different reasons, and every failure was silent:
 *
 *   - a marker file left armed from an earlier experiment made eight unrelated
 *     soaks write to the SD card for four minutes each;
 *   - the same marker going missing made a soak that DID ask for a capture pull
 *     a stale 24 MB file from four hours earlier, which measured beautifully
 *     and was caught only because 126.976 s of audio cannot come out of a 95 s
 *     app lifetime;
 *   - and on 2026-09-12 the request-side arming was dropped by a stale
 *     dispatcher snapshot, so the field was accepted, recorded, and ignored.
 *
 * A number that costs a 24 MB pull, a FUSE-backed write on the audio thread and
 * three separate pieces of host tooling is a number nobody takes. This computes
 * the same statistics from the same samples, at the same tap point, and prints
 * them -- so a level costs a soak and a grep, and a second title costs nothing
 * but device time.
 *
 * It is deliberately NOT a replacement for the capture. A capture can be
 * re-analysed with a question nobody had thought of yet; this can only answer
 * the questions compiled into it. It is the cheap instrument, not the
 * authoritative one, and where both exist they must agree -- which is exactly
 * the calibration this is first used for.
 *
 * CONVENTIONS, copied from audio_measure.py so the two are comparable:
 *   - full scale is 32768, so a peak of 32767 reads -0.0003 dBFS;
 *   - RMS dBFS is against a full-scale SQUARE wave, so a full-scale sine is
 *     -3.01 dBFS;
 *   - RMS is AC, i.e. DC removed, because a DC offset inflates raw RMS without
 *     being audible;
 *   - windows are 2400 frames = 50.0 ms, and a window whose AC variance is
 *     exactly zero is excluded from the percentiles rather than counted as
 *     -inf. That is what percentiles() in audio_measure.py does, and matching
 *     it matters: the published Galleon baseline counted 1,677 of 1,857
 *     windows, and a meter that counted all 1,857 would report a different p5;
 *   - "clipped" is |s| >= 32767, not 32768, because the float-to-short
 *     conversion scales by 32767 and negative saturation arrives as -32767;
 *   - "wrap suspects" counts adjacent samples differing by more than full
 *     scale, the signature of the int16_t mix accumulator wrapping (#73).
 *
 * Percentiles come from a 0.1 dB histogram rather than a sorted list, because
 * a sorted list would mean storing every window of an unbounded run on the
 * audio thread. 0.1 dB is two orders below the tolerance any of these
 * measurements are judged at, and the bin CENTRE is reported so the error is
 * symmetric.
 *
 * Runs on the APU thread only, at the same point the capture writes, so no
 * atomics: se_frame is the only writer and the only reader.
 * ------------------------------------------------------------------------ */

#ifdef __ANDROID__
#define APU_LVL_LOG(fmt, ...)                                                 \
    __android_log_print(ANDROID_LOG_INFO, "hakuX-audio", fmt, ##__VA_ARGS__)
#else
#define APU_LVL_LOG(fmt, ...)                                                 \
    fprintf(stderr, "mcpx apu: level: " fmt "\n", ##__VA_ARGS__)
#endif

#define APU_LVL_FULL_SCALE 32768.0
#define APU_LVL_WINDOW_FRAMES 2400 /* 50.0 ms at 48 kHz */
#define APU_LVL_BINS 1440          /* 0.1 dB steps */
#define APU_LVL_BIN_DB 0.1
#define APU_LVL_DB_FLOOR (-144.0)
#define APU_LVL_REPORT_MS 5000

static struct {
    /* whole run, per channel */
    int64_t sum[2];
    uint64_t sumsq[2];
    int32_t peak[2];
    uint64_t clipped[2];
    uint64_t zeros[2];
    uint64_t wraps[2];
    int32_t max_jump[2];
    int32_t last[2];
    bool have_last;
    uint64_t frames;

    /* window in progress */
    int64_t wsum[2];
    uint64_t wsumsq[2];
    uint32_t wn;

    /* closed windows */
    uint64_t bins[2][APU_LVL_BINS];
    uint64_t counted[2];
    uint64_t silent[2];

    int64_t last_ms;
    int reports;
} apu_level;

static double apu_level_db(double amplitude)
{
    if (amplitude <= 0.0) {
        return APU_LVL_DB_FLOOR;
    }
    return 20.0 * log10(amplitude / APU_LVL_FULL_SCALE);
}

static void apu_level_close_window(void)
{
    for (int c = 0; c < 2; c++) {
        double n = (double)apu_level.wn;
        double mean = (double)apu_level.wsum[c] / n;
        double var = (double)apu_level.wsumsq[c] / n - mean * mean;
        if (!(var > 0.0)) {
            /* Exactly-constant window. audio_measure.py drops these from the
             * percentiles rather than binning them at -inf; count them so the
             * denominator can be checked against the file's window count. */
            apu_level.silent[c]++;
            continue;
        }
        double d = apu_level_db(sqrt(var));
        int bin = (int)((d - APU_LVL_DB_FLOOR) / APU_LVL_BIN_DB);
        if (bin < 0) {
            bin = 0;
        }
        if (bin >= APU_LVL_BINS) {
            bin = APU_LVL_BINS - 1;
        }
        apu_level.bins[c][bin]++;
        apu_level.counted[c]++;
    }
    apu_level.wsum[0] = apu_level.wsum[1] = 0;
    apu_level.wsumsq[0] = apu_level.wsumsq[1] = 0;
    apu_level.wn = 0;
}

/* Nearest-rank, no interpolation, so the answer is an observed window --
 * matching percentiles() in audio_measure.py. */
static double apu_level_pct(int c, int p)
{
    uint64_t n = apu_level.counted[c];
    if (!n) {
        return APU_LVL_DB_FLOOR;
    }
    uint64_t target = (uint64_t)(((double)p / 100.0) * (double)(n - 1) + 0.5);
    uint64_t cum = 0;
    for (int b = 0; b < APU_LVL_BINS; b++) {
        cum += apu_level.bins[c][b];
        if (cum > target) {
            return APU_LVL_DB_FLOOR + (b + 0.5) * APU_LVL_BIN_DB;
        }
    }
    return APU_LVL_DB_FLOOR + (APU_LVL_BINS - 0.5) * APU_LVL_BIN_DB;
}

static void apu_level_observe(const int16_t buf[][2], int frames)
{
    for (int i = 0; i < frames; i++) {
        for (int c = 0; c < 2; c++) {
            int32_t v = buf[i][c];
            apu_level.sum[c] += v;
            apu_level.sumsq[c] += (uint64_t)((int64_t)v * v);
            apu_level.wsum[c] += v;
            apu_level.wsumsq[c] += (uint64_t)((int64_t)v * v);
            int32_t a = v < 0 ? -v : v;
            if (a > apu_level.peak[c]) {
                apu_level.peak[c] = a;
            }
            if (a >= 32767) {
                apu_level.clipped[c]++;
            }
            if (v == 0) {
                apu_level.zeros[c]++;
            }
            if (apu_level.have_last) {
                int32_t jump = v - apu_level.last[c];
                if (jump < 0) {
                    jump = -jump;
                }
                if (jump > apu_level.max_jump[c]) {
                    apu_level.max_jump[c] = jump;
                }
                if (jump > 32768) {
                    apu_level.wraps[c]++;
                }
            }
            apu_level.last[c] = v;
        }
        apu_level.have_last = true;
        apu_level.frames++;
        apu_level.wn++;
        if (apu_level.wn == APU_LVL_WINDOW_FRAMES) {
            apu_level_close_window();
        }
    }
}

static void apu_level_report(int64_t now_ms)
{
    if (!apu_level.last_ms) {
        apu_level.last_ms = now_ms;
        return;
    }
    if (now_ms - apu_level.last_ms < APU_LVL_REPORT_MS) {
        return;
    }
    apu_level.last_ms = now_ms;
    if (!apu_level.frames) {
        return;
    }
    apu_level.reports++;

    for (int c = 0; c < 2; c++) {
        double n = (double)apu_level.frames;
        double mean = (double)apu_level.sum[c] / n;
        double var = (double)apu_level.sumsq[c] / n - mean * mean;
        if (var < 0.0) {
            var = 0.0;
        }
        /* One line per channel rather than one wide line for both: the two
         * channels are compared against each other constantly (a lost channel
         * or a stuck one is the failure this would catch first), and a reader
         * doing that by eye down a column beats one doing it across a line. */
        APU_LVL_LOG(
            "level %c: %.3f s  peak %d (%.2f dBFS)  acrms %.2f dBFS  "
            "dc %.3f %%FS  p5/25/50/75/95 %.2f/%.2f/%.2f/%.2f/%.2f  "
            "windows %llu counted %llu flat  clipped %llu  zeros %llu  "
            "wrap %llu  maxjump %d",
            c ? 'R' : 'L', n / 48000.0,
            apu_level.peak[c], apu_level_db((double)apu_level.peak[c]),
            apu_level_db(sqrt(var)),
            100.0 * mean / APU_LVL_FULL_SCALE,
            apu_level_pct(c, 5), apu_level_pct(c, 25), apu_level_pct(c, 50),
            apu_level_pct(c, 75), apu_level_pct(c, 95),
            (unsigned long long)apu_level.counted[c],
            (unsigned long long)apu_level.silent[c],
            (unsigned long long)apu_level.clipped[c],
            (unsigned long long)apu_level.zeros[c],
            (unsigned long long)apu_level.wraps[c],
            apu_level.max_jump[c]);
    }
}

static void se_frame(MCPXAPUState *d)
{
    mcpx_apu_update_dsp_preference(d);
    mcpx_debug_begin_frame();
    g_dbg.gp_realtime = d->gp.realtime;
    g_dbg.ep_realtime = d->ep.realtime;

    /* A rudimentary calculation to determine approximately how taxed the APU
     * thread is, by measuring how much time we spend waiting for FIFO to drain
     * versus working on building frames.
     * =1: thread is not sleeping and likely falling behind realtime
     * <1: thread is able to complete work on time
     */
    int64_t now = qemu_clock_get_ms(QEMU_CLOCK_REALTIME);
    if (now - d->frame_count_time_ms >= 1000) {
        g_dbg.frames_processed = d->frame_count;
        float t = 1.0f - ((double)d->sleep_acc_us /
                          (double)((now - d->frame_count_time_ms) * 1000));
        g_dbg.utilization = t;

        d->frame_count_time_ms = now;
        d->frame_count = 0;
        d->sleep_acc_us = 0;
    }
    /* Outside the once-a-second block deliberately: that block resets the
     * utilization window, and starvation keeps its own 5 s cadence. `now` is
     * reused rather than re-read, so this costs a call and a comparison on a
     * 5.333 ms frame.
     */
    apu_starve_report(d, now);
    apu_level_report(now);
    d->frame_count++;

    /* Buffer for all mixbins for this frame */
    float mixbins[NUM_MIXBINS][NUM_SAMPLES_PER_FRAME] = { 0 };

    mcpx_apu_vp_frame(d, mixbins);
    mcpx_apu_dsp_frame(d, mixbins);

    if ((d->ep_frame_div + 1) % 8 == 0) {
        if (0 <= g_config.audio.volume_limit && g_config.audio.volume_limit < 1) {
            float f = pow(g_config.audio.volume_limit, M_E);
            for (int i = 0; i < 256; i++) {
                d->monitor.frame_buf[i][0] *= f;
                d->monitor.frame_buf[i][1] *= f;
            }
        }

        /* Capture after the limiter, so the file holds what is actually sent
         * to the device. A limiter below unity scales both sides of an A/B
         * equally and so cancels in a dB difference; its value is recorded in
         * the sidecar either way. One pointer test when capture is off.
         */
        if (apu_capture.fp) {
            apu_capture_write(d->monitor.frame_buf,
                              sizeof(d->monitor.frame_buf));
        }

        /* Same samples, same point, same conventions as the capture -- so the
         * two can be checked against each other whenever both are available.
         * See the level meter's comment for why a second instrument here is
         * worth having. */
        apu_level_observe(d->monitor.frame_buf, 256);

        qemu_spin_lock(&d->monitor.fifo_lock);
        int num_bytes_free = (int)fifo8_num_free(&d->monitor.fifo);
        assert(num_bytes_free >= sizeof(d->monitor.frame_buf));
        fifo8_push_all(&d->monitor.fifo, (uint8_t *)d->monitor.frame_buf,
                       sizeof(d->monitor.frame_buf));
        qemu_spin_unlock(&d->monitor.fifo_lock);
        memset(d->monitor.frame_buf, 0, sizeof(d->monitor.frame_buf));
    }

    d->ep_frame_div++;

    mcpx_debug_end_frame();
}

/* Note: only supports millisecond resolution on Windows */
static void sleep_ns(int64_t ns)
{
#ifndef _WIN32
        struct timespec sleep_delay, rem_delay;
        sleep_delay.tv_sec = ns / 1000000000LL;
        sleep_delay.tv_nsec = ns % 1000000000LL;
        nanosleep(&sleep_delay, &rem_delay);
#else
        Sleep(ns / SCALE_MS);
#endif
}

static int getenv_int_clamped(const char *name, int min_value, int max_value,
                              int fallback)
{
    const char *value = getenv(name);
    if (!value || value[0] == '\0') {
        return fallback;
    }

    char *end = NULL;
    long parsed = strtol(value, &end, 10);
    if (end == value || *end != '\0') {
        return fallback;
    }

    if (parsed < min_value) {
        return min_value;
    }
    if (parsed > max_value) {
        return max_value;
    }
    return (int)parsed;
}


static void monitor_sink_cb(void *opaque, uint8_t *stream, int free_b)
{
    MCPXAPUState *s = MCPX_APU_DEVICE(opaque);

    if (!runstate_is_running()) {
        memset(stream, 0, free_b);
        return;
    }

    int avail = 0;
    int wait_attempts = 10;
    for (int i = 0; i < wait_attempts; i++) {
        qemu_spin_lock(&s->monitor.fifo_lock);
        avail = fifo8_num_used(&s->monitor.fifo);
        qemu_spin_unlock(&s->monitor.fifo_lock);
        if (avail >= free_b) {
            break;
        }
        sleep_ns(500000);
        qemu_cond_broadcast(&s->cond);
        if (!runstate_is_running()) {
            memset(stream, 0, free_b);
            return;
        }
    }

    int copied = 0;
    int to_copy = MIN(free_b, avail);
    while (copied < to_copy) {
        uint32_t chunk_len = 0;
        qemu_spin_lock(&s->monitor.fifo_lock);
        chunk_len = fifo8_pop_buf(&s->monitor.fifo, stream + copied,
                                  to_copy - copied);
        qemu_spin_unlock(&s->monitor.fifo_lock);
        if (!chunk_len) {
            break;
        }
        copied += chunk_len;
    }

    if (copied < free_b) {
        memset(stream + copied, 0, free_b - copied);
    }

    /* Counted here and not on the two early returns above: those zero-fill
     * because the machine is paused or exiting, which is silence on purpose.
     * Folding them in would make every pause look like a starvation burst.
     */
    apu_starve_account(free_b, copied);

    qemu_cond_broadcast(&s->cond);
}

/* Default capture name. The format is in the filename on purpose: a headerless
 * PCM file whose rate and layout are folklore is not a measurement.
 */
#define APU_CAPTURE_BASENAME "apu_monitor.s16le48k2ch.pcm"

/* Presence of this file arms the capture; see apu_capture_armed(). */
#define APU_CAPTURE_MARKER "audio_capture.on"

#ifdef __ANDROID__
/* The app's external files dir: writable without root, reachable by adb pull,
 * and the same place the pgraph harness already writes. The guest's cwd is not
 * writable, which is why the dead tap's relative "ep.pcm" could never have
 * worked here.
 */
#define APU_CAPTURE_DIR "/sdcard/Android/data/com.jreinach.hakux.debug/files/"
#else
#define APU_CAPTURE_DIR ""
#endif

/* Write a sidecar describing the capture, so the measurement script never has
 * to guess the format, and the run's audio config is on the record next to the
 * samples it produced.
 */
static void apu_capture_write_sidecar(const char *pcm_path, size_t block_bytes)
{
    char *json_path = g_strdup_printf("%s.json", pcm_path);
    FILE *fp = fopen(json_path, "wb");

    if (fp) {
        fprintf(fp,
                "{\n"
                "  \"pcm_file\": \"%s\",\n"
                "  \"sample_rate\": 48000,\n"
                "  \"channels\": 2,\n"
                "  \"sample_format\": \"s16\",\n"
                "  \"interleaved\": true,\n"
                "  \"host_endian\": \"%s\",\n"
                "  \"bytes_per_block\": %zu,\n"
                "  \"frames_per_block\": 256,\n"
                "  \"block_ms\": 5.333,\n"
                "  \"tap\": \"monitor.frame_buf before fifo8_push_all\",\n"
                "  \"byte_limit\": %" PRIu64 ",\n"
                "  \"audio_volume_limit\": %f,\n"
                "  \"audio_use_dsp\": %s\n"
                "}\n",
                pcm_path,
#if HOST_BIG_ENDIAN
                "big",
#else
                "little",
#endif
                block_bytes, apu_capture.byte_limit,
                (double)g_config.audio.volume_limit,
                g_config.audio.use_dsp ? "true" : "false");
        fclose(fp);
    } else {
        APU_CAP_LOG("could not write sidecar %s: %s", json_path,
                    strerror(errno));
    }

    g_free(json_path);
}

/* Read the marker file that arms the capture on a device.
 *
 * The environment alone is not enough here. On Android the env is populated
 * from Kotlin via SDLActivity.nativeSetenv, gated on a SharedPreference set
 * through the settings UI -- that is how XEMU_TEXTURE_DUMP is wired
 * (android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt:100-112).
 * So an env-only switch cannot be thrown over adb: it needs a UI toggle and a
 * Java change. A marker file can:
 *
 *     adb shell touch <dir>/audio_capture.on
 *
 * Returns true if the capture should run. If the marker's first line parses as
 * an integer it overrides the size cap in MB, so a run can be bounded from adb
 * without rebuilding.
 */
static bool apu_capture_armed(const char *marker_path, int *cap_mb)
{
    if (getenv_int_clamped("XEMU_AUDIO_CAPTURE", 0, 1, 0) == 1) {
        return true;
    }

    FILE *fp = fopen(marker_path, "rb");
    if (!fp) {
        return false;
    }

    char line[32] = { 0 };
    if (fgets(line, sizeof(line), fp)) {
        char *end = NULL;
        long parsed = strtol(line, &end, 10);
        if (end != line && parsed >= 1 && parsed <= 4096) {
            *cap_mb = (int)parsed;
        }
    }
    fclose(fp);

    return true;
}

static void apu_capture_init(MCPXAPUState *d)
{
    const char *marker = getenv("XEMU_AUDIO_CAPTURE_MARKER");
    char *owned_marker = NULL;
    if (!marker || !marker[0]) {
        owned_marker = g_strdup_printf("%s%s", APU_CAPTURE_DIR,
                                       APU_CAPTURE_MARKER);
        marker = owned_marker;
    }

    int cap_mb = getenv_int_clamped("XEMU_AUDIO_CAPTURE_MAX_MB", 1, 4096,
                                    APU_CAPTURE_DEFAULT_MB);

    bool armed = apu_capture_armed(marker, &cap_mb);
    g_free(owned_marker);
    if (!armed) {
        return;
    }

    const char *path = getenv("XEMU_AUDIO_CAPTURE_PATH");
    char *owned = NULL;
    if (!path || !path[0]) {
        owned = g_strdup_printf("%s%s", APU_CAPTURE_DIR, APU_CAPTURE_BASENAME);
        path = owned;
    }

    /* "wb", not the dead tap's "a+": one capture is one run. Appending would
     * silently splice several runs into a file whose timeline is a lie.
     */
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        APU_CAP_LOG("could not open %s: %s -- capture disabled", path,
                    strerror(errno));
        g_free(owned);
        return;
    }

    apu_capture.buf = g_malloc(APU_CAPTURE_BUF_BYTES);
    setvbuf(fp, apu_capture.buf, _IOFBF, APU_CAPTURE_BUF_BYTES);

    apu_capture.bytes_written = 0;
    apu_capture.blocks = 0;
    apu_capture.byte_limit = (uint64_t)cap_mb * 1024 * 1024;
    apu_capture.fp = fp;

    apu_capture_write_sidecar(path, sizeof(d->monitor.frame_buf));

    APU_CAP_LOG("capturing s16/48000/2ch to %s (cap %d MB, %.0f s max)", path,
                cap_mb, (double)apu_capture.byte_limit / (48000.0 * 2.0 * 2.0));

    g_free(owned);
}

static void monitor_init(MCPXAPUState *d)
{
    qemu_spin_init(&d->monitor.fifo_lock);
    d->monitor.queued_bytes_low = 0;
    d->monitor.queued_bytes_high = 0;

    int fifo_frames = 3;
    int audio_samples = 512;
#ifdef __ANDROID__
    fifo_frames = 48;
    audio_samples = 2048;
    fifo_frames = getenv_int_clamped("XEMU_ANDROID_AUDIO_FIFO_FRAMES", 3, 128,
                                     fifo_frames);
    audio_samples = getenv_int_clamped("XEMU_ANDROID_AUDIO_SAMPLES", 256, 4096,
                                       audio_samples);
#endif
    int fifo_capacity_bytes = fifo_frames * sizeof(d->monitor.frame_buf);
    fifo8_create(&d->monitor.fifo, fifo_capacity_bytes);

    struct SDL_AudioSpec sdl_audio_spec = {
        .freq = 48000,
        .format = AUDIO_S16SYS,
        .channels = 2,
        .samples = audio_samples,
        .callback = monitor_sink_cb,
        .userdata = d,
    };

    if (SDL_Init(SDL_INIT_AUDIO) < 0)  {
        fprintf(stderr, "Failed to initialize SDL audio subsystem: %s\n",
                SDL_GetError());
        exit(1);
    }

    SDL_AudioDeviceID sdl_audio_dev;
    SDL_AudioSpec obtained_audio_spec;
    sdl_audio_dev = SDL_OpenAudioDevice(NULL, 0, &sdl_audio_spec,
                                        &obtained_audio_spec,
                                        SDL_AUDIO_ALLOW_FORMAT_CHANGE);
    if (sdl_audio_dev == 0) {
        fprintf(stderr, "SDL_OpenAudioDevice failed: %s\n",
                SDL_GetError());
        assert(!"SDL_OpenAudioDevice failed");
        exit(1);
    }

    int fifo_frame_bytes = sizeof(d->monitor.frame_buf);
    int drain_bytes = obtained_audio_spec.samples * 2 * sizeof(int16_t);
    if (drain_bytes <= 0) {
        drain_bytes = audio_samples * 2 * sizeof(int16_t);
    }
    drain_bytes = MAX(drain_bytes, fifo_frame_bytes);
    d->monitor.fifo_capacity_bytes = fifo_capacity_bytes;
    int max_high = MAX(d->monitor.fifo_capacity_bytes - fifo_frame_bytes,
                       fifo_frame_bytes);
    d->monitor.device_buffer_bytes = drain_bytes;
    d->monitor.queued_bytes_high = MIN(3 * drain_bytes, max_high);
    d->monitor.queued_bytes_low = MIN(drain_bytes, d->monitor.queued_bytes_high);

    SDL_PauseAudioDevice(sdl_audio_dev, 0);

    apu_capture_init(d);
}

static void mcpx_apu_realize(PCIDevice *dev, Error **errp)
{
    MCPXAPUState *d = MCPX_APU_DEVICE(dev);

    dev->config[PCI_INTERRUPT_PIN] = 0x01;

    memory_region_init_io(&d->mmio, OBJECT(dev), &mcpx_apu_mmio_ops, d,
                          "mcpx-apu-mmio", 0x80000);

    memory_region_init_io(&d->vp.mmio, OBJECT(dev), &vp_ops, d,
                          "mcpx-apu-vp", 0x10000);
    memory_region_add_subregion(&d->mmio, 0x20000, &d->vp.mmio);

    memory_region_init_io(&d->gp.mmio, OBJECT(dev), &gp_ops, d,
                          "mcpx-apu-gp", 0x10000);
    memory_region_add_subregion(&d->mmio, 0x30000, &d->gp.mmio);

    memory_region_init_io(&d->ep.mmio, OBJECT(dev), &ep_ops, d,
                          "mcpx-apu-ep", 0x10000);
    memory_region_add_subregion(&d->mmio, 0x50000, &d->ep.mmio);

    pci_register_bar(dev, 0, PCI_BASE_ADDRESS_SPACE_MEMORY, &d->mmio);
}

static void mcpx_apu_exitfn(PCIDevice *dev)
{
    MCPXAPUState *d = MCPX_APU_DEVICE(dev);
    d->exiting = true;
    qemu_cond_broadcast(&d->cond);
    qemu_thread_join(&d->apu_thread);
    mcpx_apu_vp_finalize(d);
}

static void mcpx_apu_reset(MCPXAPUState *d)
{
    qemu_mutex_lock(&d->lock); // FIXME: Can fail if thread is pegged, add flag
    memset(d->regs, 0, sizeof(d->regs));

    mcpx_apu_vp_reset(d);

    // FIXME: Reset DSP state
    memset(d->gp.dsp->core.pram_opcache, 0,
           sizeof(d->gp.dsp->core.pram_opcache));
    memset(d->ep.dsp->core.pram_opcache, 0,
           sizeof(d->ep.dsp->core.pram_opcache));
    d->set_irq = false;
    d->next_frame_time_us = 0;
    qemu_cond_signal(&d->cond);
    qemu_mutex_unlock(&d->lock);
}

// Note: This is handled as a VM state change and not as a `pre_save` callback
// because we want to halt the FIFO before any VM state is saved/restored to
// avoid corruption.
static void mcpx_apu_vm_state_change(void *opaque, bool running, RunState state)
{
    MCPXAPUState *d = opaque;

    if (state == RUN_STATE_SAVE_VM) {
        qemu_mutex_lock(&d->lock);
    }
}

static int mcpx_apu_post_save(void *opaque)
{
    MCPXAPUState *d = opaque;
    qemu_cond_signal(&d->cond);
    qemu_mutex_unlock(&d->lock);
    return 0;
}

static int mcpx_apu_pre_load(void *opaque)
{
    MCPXAPUState *d = opaque;
    mcpx_apu_reset(d);
    qemu_mutex_lock(&d->lock);
    return 0;
}

static int mcpx_apu_post_load(void *opaque, int version_id)
{
    MCPXAPUState *d = opaque;
    qemu_cond_signal(&d->cond);
    qemu_mutex_unlock(&d->lock);
    return 0;
}

static void mcpx_apu_reset_hold(Object *obj, ResetType type)
{
    MCPXAPUState *d = MCPX_APU_DEVICE(obj);
    mcpx_apu_reset(d);
}

const VMStateDescription vmstate_vp_dsp_dma_state = {
    .name = "mcpx-apu/dsp-state/dma",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields      = (VMStateField[]) {
        VMSTATE_UINT32(configuration, DSPDMAState),
        VMSTATE_UINT32(control, DSPDMAState),
        VMSTATE_UINT32(start_block, DSPDMAState),
        VMSTATE_UINT32(next_block, DSPDMAState),
        VMSTATE_BOOL(error, DSPDMAState),
        VMSTATE_BOOL(eol, DSPDMAState),
        VMSTATE_END_OF_LIST()
    }
};

const VMStateDescription vmstate_vp_dsp_core_state = {
    .name = "mcpx-apu/dsp-state/core",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields      = (VMStateField[]) {
        // FIXME: Remove unnecessary fields
        VMSTATE_UINT16(instr_cycle, dsp_core_t),
        VMSTATE_UINT32(pc, dsp_core_t),
        VMSTATE_UINT32_ARRAY(registers, dsp_core_t, DSP_REG_MAX),
        VMSTATE_UINT32_2DARRAY(stack, dsp_core_t, 2, 16),
        VMSTATE_UINT32_ARRAY(xram, dsp_core_t, DSP_XRAM_SIZE),
        VMSTATE_UINT32_ARRAY(yram, dsp_core_t, DSP_YRAM_SIZE),
        VMSTATE_UINT32_ARRAY(pram, dsp_core_t, DSP_PRAM_SIZE),
        VMSTATE_UINT32_ARRAY(mixbuffer, dsp_core_t, DSP_MIXBUFFER_SIZE),
        VMSTATE_UINT32_ARRAY(periph, dsp_core_t, DSP_PERIPH_SIZE),
        VMSTATE_UINT32(loop_rep, dsp_core_t),
        VMSTATE_UINT32(pc_on_rep, dsp_core_t),
        VMSTATE_UINT16(interrupt_state, dsp_core_t),
        VMSTATE_UINT16(interrupt_instr_fetch, dsp_core_t),
        VMSTATE_UINT16(interrupt_save_pc, dsp_core_t),
        VMSTATE_UINT16(interrupt_counter, dsp_core_t),
        VMSTATE_UINT16(interrupt_ipl_to_raise, dsp_core_t),
        VMSTATE_UINT16(interrupt_pipeline_count, dsp_core_t),
        VMSTATE_INT16_ARRAY(interrupt_ipl, dsp_core_t, 12),
        VMSTATE_UINT16_ARRAY(interrupt_is_pending, dsp_core_t, 12),
        VMSTATE_UINT32(num_inst, dsp_core_t),
        VMSTATE_UINT32(cur_inst_len, dsp_core_t),
        VMSTATE_UINT32(cur_inst, dsp_core_t),
        VMSTATE_UNUSED(1),
        VMSTATE_UINT32(disasm_memory_ptr, dsp_core_t),
        VMSTATE_BOOL(exception_debugging, dsp_core_t),
        VMSTATE_UINT32(disasm_prev_inst_pc, dsp_core_t),
        VMSTATE_BOOL(disasm_is_looping, dsp_core_t),
        VMSTATE_UINT32(disasm_cur_inst, dsp_core_t),
        VMSTATE_UINT16(disasm_cur_inst_len, dsp_core_t),
        VMSTATE_UINT32_ARRAY(disasm_registers_save, dsp_core_t, 64),
// #ifdef DSP_DISASM_REG_PC
//         VMSTATE_UINT32(pc_save, dsp_core_t),
// #endif
        VMSTATE_END_OF_LIST()
    }
};

const VMStateDescription vmstate_vp_dsp_state = {
    .name = "mcpx-apu/dsp-state",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (VMStateField[]) {
        VMSTATE_STRUCT(core, DSPState, 1, vmstate_vp_dsp_core_state, dsp_core_t),
        VMSTATE_STRUCT(dma, DSPState, 1, vmstate_vp_dsp_dma_state, DSPDMAState),
        VMSTATE_INT32(save_cycles, DSPState),
        VMSTATE_UINT32(interrupts, DSPState),
        VMSTATE_END_OF_LIST()
    }
};


const VMStateDescription vmstate_vp_ssl_data = {
    .name = "mcpx_apu_voice_data",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (VMStateField[]) {
        VMSTATE_UINT32_ARRAY(base, MCPXAPUVPSSLData, MCPX_HW_SSLS_PER_VOICE),
        VMSTATE_UINT8_ARRAY(count, MCPXAPUVPSSLData, MCPX_HW_SSLS_PER_VOICE),
        VMSTATE_INT32(ssl_index, MCPXAPUVPSSLData),
        VMSTATE_INT32(ssl_seg, MCPXAPUVPSSLData),
        VMSTATE_END_OF_LIST()
    }
};

static const VMStateDescription vmstate_mcpx_apu = {
    .name = "mcpx-apu",
    .version_id = 1,
    .minimum_version_id = 1,
    .post_save = mcpx_apu_post_save,
    .pre_load = mcpx_apu_pre_load,
    .post_load = mcpx_apu_post_load,
    .fields = (VMStateField[]) {
        VMSTATE_PCI_DEVICE(parent_obj, MCPXAPUState),
        VMSTATE_STRUCT_POINTER(gp.dsp, MCPXAPUState, vmstate_vp_dsp_state,
                               DSPState),
        VMSTATE_UINT32_ARRAY(gp.regs, MCPXAPUState, 0x10000),
        VMSTATE_STRUCT_POINTER(ep.dsp, MCPXAPUState, vmstate_vp_dsp_state,
                               DSPState),
        VMSTATE_UINT32_ARRAY(ep.regs, MCPXAPUState, 0x10000),
        VMSTATE_UINT32_ARRAY(regs, MCPXAPUState, 0x20000),
        VMSTATE_UINT32(vp.inbuf_sge_handle, MCPXAPUState),
        VMSTATE_UINT32(vp.outbuf_sge_handle, MCPXAPUState),
        VMSTATE_STRUCT_ARRAY(vp.ssl, MCPXAPUState, MCPX_HW_MAX_VOICES, 1,
                             vmstate_vp_ssl_data, MCPXAPUVPSSLData),
        VMSTATE_INT32(vp.ssl_base_page, MCPXAPUState),
        VMSTATE_UINT8_ARRAY(vp.hrtf_submix, MCPXAPUState, 4),
        VMSTATE_UINT8(vp.hrtf_headroom, MCPXAPUState),
        VMSTATE_UINT8_ARRAY(vp.submix_headroom, MCPXAPUState, NUM_MIXBINS),
        VMSTATE_UINT64_ARRAY(vp.voice_locked, MCPXAPUState, 4),
        VMSTATE_END_OF_LIST()
    },
};

static void mcpx_apu_class_init(ObjectClass *klass, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(klass);
    ResettableClass *rc = RESETTABLE_CLASS(klass);
    PCIDeviceClass *k = PCI_DEVICE_CLASS(klass);

    k->vendor_id = PCI_VENDOR_ID_NVIDIA;
    k->device_id = PCI_DEVICE_ID_NVIDIA_MCPX_APU;
    k->revision = 177;
    k->class_id = PCI_CLASS_MULTIMEDIA_AUDIO;
    k->realize = mcpx_apu_realize;
    k->exit = mcpx_apu_exitfn;

    rc->phases.hold = mcpx_apu_reset_hold;

    dc->desc = "MCPX Audio Processing Unit";
    dc->vmsd = &vmstate_mcpx_apu;
}

static const TypeInfo mcpx_apu_info = {
    .name = "mcpx-apu",
    .parent = TYPE_PCI_DEVICE,
    .instance_size = sizeof(MCPXAPUState),
    .class_init = mcpx_apu_class_init,
    .interfaces =
        (InterfaceInfo[]){
            { INTERFACE_CONVENTIONAL_PCI_DEVICE },
            {},
        },
};

static void mcpx_apu_register(void)
{
    type_register_static(&mcpx_apu_info);
}
type_init(mcpx_apu_register);

static void *mcpx_apu_frame_thread(void *arg)
{
    MCPXAPUState *d = MCPX_APU_DEVICE(arg);
    qemu_mutex_lock(&d->lock);
    while (!qatomic_read(&d->exiting)) {
        int xcntmode = GET_MASK(qatomic_read(&d->regs[NV_PAPU_SECTL]),
                                NV_PAPU_SECTL_XCNTMODE);
        uint32_t fectl = qatomic_read(&d->regs[NV_PAPU_FECTL]);
        if (xcntmode == NV_PAPU_SECTL_XCNTMODE_OFF ||
            (fectl & NV_PAPU_FECTL_FEMETHMODE_TRAPPED) ||
            (fectl & NV_PAPU_FECTL_FEMETHMODE_HALTED)) {
            d->set_irq = true;
        }

        if (d->set_irq) {
            qemu_mutex_unlock(&d->lock);
            bql_lock();
            update_irq(d);
            bql_unlock();
            qemu_mutex_lock(&d->lock);
            d->set_irq = false;
        }

        xcntmode = GET_MASK(qatomic_read(&d->regs[NV_PAPU_SECTL]),
                            NV_PAPU_SECTL_XCNTMODE);
        fectl = qatomic_read(&d->regs[NV_PAPU_FECTL]);
        if (xcntmode == NV_PAPU_SECTL_XCNTMODE_OFF ||
            (fectl & NV_PAPU_FECTL_FEMETHMODE_TRAPPED) ||
            (fectl & NV_PAPU_FECTL_FEMETHMODE_HALTED)) {
            qemu_cond_wait(&d->cond, &d->lock);
            continue;
        }
        throttle(d);
        se_frame((void *)d);
    }
    qemu_mutex_unlock(&d->lock);
    return NULL;
}

void mcpx_apu_init(PCIBus *bus, int devfn, MemoryRegion *ram)
{
    PCIDevice *dev = pci_create_simple(bus, devfn, "mcpx-apu");
    MCPXAPUState *d = MCPX_APU_DEVICE(dev);

    g_state = d;

    d->ram = ram;
    d->ram_ptr = memory_region_get_ram_ptr(d->ram);

    mcpx_apu_dsp_init(d);

    d->set_irq = false;
    d->exiting = false;

    qemu_mutex_init(&d->lock);
    qemu_cond_init(&d->cond);
    qemu_add_vm_change_state_handler(mcpx_apu_vm_state_change, d);

    mcpx_apu_vp_init(d);
    monitor_init(d);
    qemu_thread_create(&d->apu_thread, "mcpx.apu_thread", mcpx_apu_frame_thread,
                       d, QEMU_THREAD_JOINABLE);
}
