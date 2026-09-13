/*
 * QEMU Geforce NV2A implementation
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2018-2025 Matt Borgerson
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

#include "hw/xbox/nv2a/nv2a_int.h"
#include "hw/xbox/game-compat.h"
#include "hw/core/cpu.h"
#include "target/i386/cpu.h"
#include "qemu/main-loop.h"
#include "ui/xemu-settings.h"

#ifdef __ANDROID__
#include <android/log.h>
#endif

void nv2a_update_irq(NV2AState *d)
{
    /* PFIFO */
    if (d->pfifo.pending_interrupts & d->pfifo.enabled_interrupts) {
        d->pmc.pending_interrupts |= NV_PMC_INTR_0_PFIFO;
    } else {
        d->pmc.pending_interrupts &= ~NV_PMC_INTR_0_PFIFO;
    }

    /* PCRTC */
    if (d->pcrtc.pending_interrupts & d->pcrtc.enabled_interrupts) {
        d->pmc.pending_interrupts |= NV_PMC_INTR_0_PCRTC;
    } else {
        d->pmc.pending_interrupts &= ~NV_PMC_INTR_0_PCRTC;
    }

    /* PGRAPH */
    if (d->pgraph.pending_interrupts & d->pgraph.enabled_interrupts) {
        d->pmc.pending_interrupts |= NV_PMC_INTR_0_PGRAPH;
    } else {
        d->pmc.pending_interrupts &= ~NV_PMC_INTR_0_PGRAPH;
    }

    if (d->pmc.pending_interrupts && d->pmc.enabled_interrupts) {
        trace_nv2a_irq(d->pmc.pending_interrupts);
        pci_irq_assert(PCI_DEVICE(d));
    } else {
        pci_irq_deassert(PCI_DEVICE(d));
    }
}

uint8_t *xemu_get_xbox_ram_ptr(void)
{
    return g_nv2a ? g_nv2a->vram_ptr : NULL;
}

DMAObject nv_dma_load(NV2AState *d, hwaddr dma_obj_address)
{
    assert(dma_obj_address < memory_region_size(&d->ramin));

    uint32_t *dma_obj = (uint32_t *)(d->ramin_ptr + dma_obj_address);
    uint32_t flags = ldl_le_p(dma_obj);
    uint32_t limit = ldl_le_p(dma_obj + 1);
    uint32_t frame = ldl_le_p(dma_obj + 2);

    return (DMAObject){
        .dma_class  = GET_MASK(flags, NV_DMA_CLASS),
        .dma_target = GET_MASK(flags, NV_DMA_TARGET),
        .address    = (frame & NV_DMA_ADDRESS) | GET_MASK(flags, NV_DMA_ADJUST),
        .limit      = limit,
    };
}

void *nv_dma_map(NV2AState *d, hwaddr dma_obj_address, hwaddr *len)
{
    DMAObject dma = nv_dma_load(d, dma_obj_address);

    /* TODO: Handle targets and classes properly */
    trace_nv2a_dma_map(dma_obj_address, dma.dma_class, dma.dma_target,
                       dma.address, dma.limit);
    dma.address &= 0x07FFFFFF;

    assert(dma.address < memory_region_size(d->vram));
    // assert(dma.address + dma.limit < memory_region_size(d->vram));
    *len = dma.limit;
    return d->vram_ptr + dma.address;
}

hwaddr nv_clip_gpu_tile_blit(NV2AState *d, hwaddr blit_base_address, hwaddr len)
{
    const uint32_t *regs = d->pfb.regs;
    hwaddr blit_end = blit_base_address + len;
    for (int i = 0; i < NV_NUM_GPU_TILES; ++i) {
        uint32_t base_and_flags = regs[NV_PFB_TILE_BASE_ADDRESS_AND_FLAGS(i)];
        if (!(base_and_flags & NV_PFB_TILE_FLAGS_VALID)) {
            continue;
        }

        uint32_t limit = regs[NV_PFB_TILE_LIMIT(i)];

        if (blit_base_address < limit && blit_end > limit) {
            // TODO: Determine HW behavior if tiles are consecutive.
            return limit + 1 - blit_base_address;
        }
    }

    return len;
}

const NV2ABlockInfo blocktable[NV_NUM_BLOCKS] = {
    #define ENTRY(NAME, LNAME, OFFSET, SIZE) [NV_##NAME] = {            \
        .name   = #NAME,                                                \
        .offset = OFFSET,                                               \
        .size   = SIZE,                                                 \
        .ops    = { .read = LNAME ## _read, .write = LNAME ## _write }, \
    }
    ENTRY(PMC,      pmc,      0x000000, 0x001000),
    ENTRY(PBUS,     pbus,     0x001000, 0x001000),
    ENTRY(PFIFO,    pfifo,    0x002000, 0x002000),
    ENTRY(PRMA,     prma,     0x007000, 0x001000),
    ENTRY(PVIDEO,   pvideo,   0x008000, 0x001000),
    ENTRY(PTIMER,   ptimer,   0x009000, 0x001000),
    ENTRY(PCOUNTER, pcounter, 0x00a000, 0x001000),
    ENTRY(PVPE,     pvpe,     0x00b000, 0x001000),
    ENTRY(PTV,      ptv,      0x00d000, 0x001000),
    ENTRY(PRMFB,    prmfb,    0x0a0000, 0x020000),
    ENTRY(PRMVIO,   prmvio,   0x0c0000, 0x001000),
    ENTRY(PFB,      pfb,      0x100000, 0x001000),
    ENTRY(PSTRAPS,  pstraps,  0x101000, 0x001000),
    ENTRY(PGRAPH,   pgraph,   0x400000, 0x002000),
    ENTRY(PCRTC,    pcrtc,    0x600000, 0x001000),
    ENTRY(PRMCIO,   prmcio,   0x601000, 0x001000),
    ENTRY(PRAMDAC,  pramdac,  0x680000, 0x001000),
    ENTRY(PRMDIO,   prmdio,   0x681000, 0x001000),
    // ENTRY(PRAMIN,   pramin,   0x700000, 0x100000),
    ENTRY(USER,     user,     0x800000, 0x800000),
};
#undef ENTRY

static int nv2a_get_bpp(VGACommonState *s)
{
    NV2AState *d = container_of(s, NV2AState, vga);

    int depth = s->cr[0x28] & 3;

    int bpp;
    switch (depth) {
    case 0:
        /* FIXME: This case is sometimes hit during early Xbox startup.
         *        Presumably a race-condition where VGA isn't initialized, yet.
         *        `bpp = 0` mimics old code that did `bpp = depth * 8;`.
         *        This works around the issue of this mode being unhandled.
         *        However, QEMU VGA uses a 4bpp mode if `bpp = 0`.
         *        We don't know if Xbox hardware would do the same. */
        bpp = 0;
        break;
    case 2:
        bpp = d->pramdac.general_control &
              NV_PRAMDAC_GENERAL_CONTROL_ALT_MODE_SEL ? 16 : 15;
        break;
    case 3:
        bpp = 32;
        break;
    default:
        /* This is only a fallback path */
        bpp = depth * 8;
        fprintf(stderr, "Unknown VGA depth: %d\n", depth);
        assert(false);
        break;
    }

    return bpp;
}

static void nv2a_get_params(VGACommonState *s, VGADisplayParams *params)
{
    NV2AState *d = container_of(s, NV2AState, vga);
    params->line_offset = (s->cr[0x13] | ((s->cr[0x19] & 0xe0) << 3) |
                           ((s->cr[0x25] & 0x20) << 6))
                          << 3;
    params->start_addr = d->pcrtc.start / 4;
    params->line_compare = s->cr[VGA_CRTC_LINE_COMPARE] |
                           ((s->cr[VGA_CRTC_OVERFLOW] & 0x10) << 4) |
                           ((s->cr[VGA_CRTC_MAX_SCAN] & 0x40) << 3);
}

const uint8_t *nv2a_get_dac_palette(void)
{
    return g_nv2a->puserdac.palette;
}

int nv2a_get_screen_off(void)
{
    return g_nv2a->vga.sr[VGA_SEQ_CLOCK_MODE] & VGA_SR01_SCREEN_OFF;
}

static int64_t nv2a_calc_vblank_period_ns(NV2AState *d)
{
    /*
     * Diagnostic override. A title that presents on every second VBLANK and
     * one that asks for every VBLANK but misses the deadline both settle at
     * half the refresh rate, and no amount of watching them apart tells them
     * apart while the emulator itself cannot make the deadline. Halving the
     * emulated refresh does: the first title halves again, the second one
     * suddenly makes its deadline and holds the new rate.
     */
    static int64_t override_ns = -1;
    if (override_ns == -1) {
        const char *hz = getenv("HAKUX_VBLANK_HZ");
        override_ns = 0;
        if (hz && hz[0]) {
            int v = atoi(hz);
            if (v >= 10 && v <= 240) {
                override_ns = NANOSECONDS_PER_SECOND / v;
            }
        }
    }
    if (override_ns > 0) {
        return override_ns;
    }

    /*
     * Which mode this is, from the two registers that describe the output
     * raster rather than from the one that happens to be written last.
     *
     * fp_vdisplay_end is the last ACTIVE LINE, not a line count: measured
     * vd=479 with res=640x480 over a 240 s soak (Galleon, Thor, dispatch
     * 1789275041-vblank-timing-4013526), on all 129 windows. So a mode's
     * line count is vd + 1, and PAL's 576 lines put 575 here.
     *
     * The NV2A interlaces only for 1080i. SD output is scanned out
     * progressively and the external encoder does the interlacing, which is
     * why 480i and 480p are one mode as far as this register file is
     * concerned and why the measured title reports il=ff. Both display back
     * ends read this same bit for this same purpose -- vk/display.c and
     * gl/display.c, "used only in 1080i", doubling the viewport height -- so
     * when it is set, the raster described here is one FIELD and the frame is
     * twice as tall.
     *
     * The 50 Hz branch must therefore be BOUNDED. PAL is 576 lines and never
     * more, so anything taller is an HD mode running at the NTSC field rate.
     * The open `vdisplay > 480` this replaces sent 720p (719) and 1080i to
     * 50 Hz -- a 19.9% period error on a path both renderers handle -- while
     * its own comment claimed those modes for the 59.94 branch. Scaling for
     * interlace first makes the bound right whether 1080i puts 539 (per
     * field) or 1079 (per frame) in the register, which is not something any
     * title on hand can be made to report.
     *
     * Both branches are still constants. Deriving the period from the CRTC
     * raster and the VPLL was tried and failed by -26.3% (P7 in
     * docs/investigations/guest-visible-vblank.md); until something
     * authoritative about the video standard is found, the guard is what
     * there is, and it can at least be right about which mode is which.
     */
    uint32_t vdisplay = d->pramdac.fp_vdisplay_end;

    if (d->vga.cr[NV_PRMCIO_INTERLACE_MODE] !=
        NV_PRMCIO_INTERLACE_MODE_DISABLED) {
        /* Per-field raster: the frame is two of these. */
        vdisplay = vdisplay * 2 + 1;
    }

    if (vdisplay > 480 && vdisplay <= 576) {
        /* PAL (576i/576p): 50 Hz, exactly. */
        return NANOSECONDS_PER_SECOND / 50;
    }

    /* NTSC and HD (480i/480p/720p/1080i): 60000/1001 fields a second. */
    return 16683750;
}

/*
 * Guest-visible VBLANK timing instrument.
 *
 * A golden framebuffer comparison is blind to timing. A title that steps its
 * simulation off VBLANK, double-buffers against it, or measures elapsed time
 * by counting its interrupts draws the same pixels whether our period is
 * right or a fifth out, so the corpus cannot see any of it. The only way to
 * know is to measure what the guest actually sees, which is the moment
 * NV_PCRTC_INTR_0_VBLANK is asserted -- not the moment the timer callback was
 * scheduled, and not `pacing.vblank_fired`, which in simple-VBLANK mode
 * counts only one of the two sources live in that mode.
 *
 * Three things are recorded at each assertion:
 *
 *  - the interval since the previous one, into a histogram, so the
 *    distribution gets reported rather than an exponential mean. For jitter
 *    the distribution is the whole question: a correct mean with a 10 ms tail
 *    is a different defect from a wrong mean.
 *  - which of the three assertion sites produced it, because in simple mode
 *    the period timer and the host display refresh are both live and their
 *    sum is what paces the guest.
 *  - whether the guest had not yet acknowledged the previous one. PCRTC
 *    coalesces: the bit is already set, the OR is a no-op, and the guest's
 *    ISR sees one interrupt where hardware delivered two. A title counting
 *    VBLANKs to measure time loses that tick outright.
 *
 * Cost is one clock read and one array increment per assertion at 60-180 Hz,
 * plus a log line every two seconds. A line per VBLANK was the obvious
 * alternative and was rejected: at 60 Hz it perturbs what it measures.
 *
 * All three call sites hold the BQL -- the timer callback runs from the main
 * loop, and the gfx_update path in ui/xemu.c takes it explicitly -- so the
 * accumulator needs no locking of its own.
 */
#ifdef __ANDROID__

#define VBH_BUCKET_NS   50000    /* 50 us */
#define VBH_BUCKETS     1024     /* 0 .. 51.2 ms, then one overflow bin */
#define VBH_WINDOW_NS   2000000000LL

/* VBH_SRC_GFX was the host-refresh source in simple-VBLANK mode, removed in
 * nv2a_vga_gfx_update below. The slot is kept so the `src(tmr= smp= gfx=)`
 * field of the `vbl` line keeps its shape -- vblank_report.py and
 * vblank_ab.py parse it with an exact regex, and a narrowed line stops
 * matching rather than failing. It now reads zero on every window, and
 * `smp>0 gfx=0` is how a log says the second source is gone. */
enum { VBH_SRC_TIMER = 0, VBH_SRC_SIMPLE, VBH_SRC_GFX, VBH_SRC__COUNT };

static struct {
    int64_t  last_ns;
    int64_t  window_start_ns;
    uint32_t bucket[VBH_BUCKETS + 1];
    uint32_t n;
    uint32_t src[VBH_SRC__COUNT];
    uint32_t coalesced;
    uint32_t deferred;
    /* NV_PCRTC_RASTER reads the guest made during the period that just
     * ended. On silicon that register is the scanline the beam is on, so it
     * advances at the horizontal rate -- 15.734 kHz for 480i, some 262 counts
     * across a field -- and a title can poll it to find where in the frame it
     * is, or to wait for a particular line. Ours advances by one PER READ
     * (pcrtc.c: `r = d->pcrtc.raster++`) and is reset to 0 at VBLANK, so the
     * value a title gets back is a function of how often it has asked, not of
     * how much of the frame has elapsed. Whether that matters depends on
     * whether anything reads it, which nothing has ever counted. */
    uint32_t raster_reads;
    uint32_t raster_reads_max;
    int64_t  min_ns;
    int64_t  max_ns;
    uint64_t sum_ns;

    /*
     * PHASE, which is a different property from rate and was the thing left
     * open on #65.
     *
     * The rate question is "how far apart are consecutive assertions", and
     * the histogram above answers it. The phase question is "did this
     * assertion land where the grid said it would", and the grid is a value
     * this file holds: d->vblank_next_target_ns is the slot this VBLANK was
     * scheduled into, and it is still un-advanced at the moment of the
     * assertion. So `now - target` IS the phase error, in nanoseconds, per
     * assertion, and it needs nothing from pgraph.c -- which is what #65
     * recorded as the blocker for measuring it.
     *
     * Split on deferral, because the two are different mechanisms wearing
     * one number:
     *
     *   - a NON-deferred assertion's lateness is the QEMU timer's own
     *     latency, i.e. how late the main loop got to us;
     *   - a DEFERRED one's is that plus however long the deferral held it,
     *     which is bounded by poll_interval * defer_cap -- half a period in
     *     normal mode, a whole one in unlock mode.
     *
     * `late_neg` is the impossible row, and it is here to be zero. A QEMU
     * timer fires at or after its deadline and never before, and every path
     * that rearms this timer early (the deferral retry, and FLIP_STALL's
     * timer_mod(now)) can only fire a VBLANK that is ALREADY past its slot.
     * So a negative lateness would mean the grid was moved out from under an
     * armed timer by a writer this file does not know about, which is a
     * different defect from any of the four and would invalidate the split
     * above rather than just adding to it.
     */
    uint32_t late_bucket[VBH_BUCKETS + 1];
    uint32_t late_n;
    uint32_t late_neg;
    uint64_t late_sum;
    int64_t  late_max;
    uint32_t late_nodef_n;
    uint64_t late_nodef_sum;
    int64_t  late_nodef_max;
    uint32_t late_def_n;
    uint64_t late_def_sum;
    int64_t  late_def_max;

    /* Assertions made while unlock mode was active. #65 had to read this off
     * the `gfps` line, which is emitted on a different cadence by a different
     * writer, so a window could not be attributed with certainty. It belongs
     * on the line whose numbers it explains. */
    uint32_t unlocked_n;

    /*
     * Assertions on which the grid's `<= now` clamp fired, counted at the
     * clamp itself rather than inferred from the lateness figures.
     *
     * This is the one event that turns a late VBLANK into permanent drift,
     * and it is worth its own counter because the clamp does not discard the
     * EXCESS over a period -- it discards the WHOLE lateness. `target +=
     * period` puts the next slot at `t + period`; the clamp replaces that
     * with `now + period` = `t + late + period`, so the grid moves forward by
     * `late`, not by `late - period`. Mean drift per assertion is therefore
     * `E[late * 1(late > period)]`, which is why a 10.8 ms mean deferral hold
     * on a 16.68 ms period can cost 1.7 ms per assertion on the eleven
     * deferrals in a window of 109: 11 * 16,810,019 / 109 = 1,696,382 ns
     * against a measured 1,695,881.
     *
     * Counted so a change to the deferral cap can be judged on whether the
     * clamp still fires, which is the mechanism, rather than on a drift
     * figure, which is the mechanism mixed with the host's stall tail.
     */
    uint32_t clamped;

    /*
     * COALESCING, attributed rather than counted.
     *
     * `coalesced` alone cannot say whether the guest lost anything. Three
     * things separate a lost interrupt from a number:
     *
     *   - coal_enabled: the VBLANK bit was UNMASKED in INTR_EN_0, so the
     *     guest had asked to be interrupted and an assertion folded into the
     *     pending one is a tick it will never see. A coalesce while the bit
     *     is masked is not observable as a lost interrupt at all -- the guest
     *     is not taking them -- so if the count is dominated by masked
     *     periods then 1.56% is a measurement of the wrong population.
     *   - coal_short: the interval that PRECEDED the coalesce was shorter
     *     than the period. That is the signature of our own machinery
     *     causing it: the grid's correction after a deferral, or a second
     *     source, delivers two assertions closer together than hardware
     *     would and the ISR has less time to acknowledge.
     *   - coal_gap_sum: the mean of those preceding intervals, so "shorter"
     *     has a magnitude.
     *
     * Coalescing itself is faithful in KIND -- PCRTC_INTR_0 is a sticky
     * latch on silicon too, and a hardware ISR that misses its window loses
     * the same tick. What is ours is the RATE, and these three fields are
     * what make that separable.
     */
    uint32_t coal_enabled;
    uint32_t coal_short;
    uint64_t coal_gap_sum;
} s_vbh;

/* Interval at or below which the given share of the window's samples fell,
 * reported as the containing bucket's upper edge -- so an upper bound good
 * to 50 us, which is 0.3% of a refresh period. */
static int64_t vbh_pct_of(const uint32_t *bucket, uint32_t n, uint32_t pct)
{
    uint32_t want = (n * pct + 99) / 100;
    uint32_t acc = 0;

    if (want == 0) {
        want = 1;
    }
    for (int i = 0; i <= VBH_BUCKETS; i++) {
        acc += bucket[i];
        if (acc >= want) {
            return (int64_t)(i + 1) * VBH_BUCKET_NS;
        }
    }
    return (int64_t)(VBH_BUCKETS + 1) * VBH_BUCKET_NS;
}

static int64_t vbh_percentile(uint32_t pct)
{
    return vbh_pct_of(s_vbh.bucket, s_vbh.n, pct);
}

static void vbh_dump_and_reset(NV2AState *d, int64_t now)
{
    int64_t period  = nv2a_calc_vblank_period_ns(d);
    int64_t span_ns = now - s_vbh.window_start_ns;
    /* What we intended is `period`. This is what was delivered, and the gap
     * between them is the rate at which the guest's VBLANK clock loses or
     * gains time against the wall. */
    int64_t mean_ns = s_vbh.n ? (int64_t)(s_vbh.sum_ns / s_vbh.n) : 0;
    /* Delivered rate over the window in millihertz, counting every assertion
     * from every source -- which is the figure a title pacing off VBLANK is
     * actually subject to. */
    int64_t mhz = span_ns > 0
                      ? (int64_t)s_vbh.n * 1000000000LL * 1000LL / span_ns
                      : 0;
    int w = 0, h = 0;

    if (d->vga.get_resolution) {
        d->vga.get_resolution(&d->vga, &w, &h);
    }

    /*
     * What the programmed mode says the period ought to be, alongside what we
     * chose. nv2a_calc_vblank_period_ns does not derive anything: it branches
     * on one flat-panel register and returns a constant. The NV2A's own
     * answer is vtotal * htotal / pixel clock, and every ingredient of that
     * is programmed by the guest and sitting in registers we already model --
     * the CRTC totals in the VGA register file, the pixel clock in
     * VPLL_COEFF, which pramdac.c stores and nothing has ever decoded.
     *
     * This is deliberately the naive VGA reading: htotal in 8-dot characters,
     * vtotal from the standard overflow bits, no NV2A extension bits applied,
     * because their positions are a guess and a guess would be
     * indistinguishable from a measurement. The raw CRTC bytes go out beside
     * it so the extension bits can be read out of a real title rather than
     * assumed. If
     * this naive figure lands near the constant we return, the derivation is
     * the fix; if it lands nowhere near, the Xbox does not program the NV2A
     * CRTC with the encoder's timing and a mode table is the only option.
     */
    uint32_t vco   = d->pramdac.video_clock_coeff;
    uint32_t vm    = vco & NV_PRAMDAC_VPLL_COEFF_MDIV;
    uint32_t vn    = (vco & NV_PRAMDAC_VPLL_COEFF_NDIV) >> 8;
    uint32_t vp    = (vco & NV_PRAMDAC_VPLL_COEFF_PDIV) >> 16;
    int64_t  pixclk = vm ? (int64_t)NV2A_CRYSTAL_FREQ * vn / (1 << vp) / vm : 0;
    int64_t  htotal = ((int64_t)d->vga.cr[VGA_CRTC_H_TOTAL] + 5) * 8;
    int64_t  vtotal = (d->vga.cr[VGA_CRTC_V_TOTAL] |
                       ((d->vga.cr[VGA_CRTC_OVERFLOW] & 0x01) << 8) |
                       ((d->vga.cr[VGA_CRTC_OVERFLOW] & 0x20) << 4)) + 2;
    int64_t derived = pixclk > 0
                          ? vtotal * htotal * NANOSECONDS_PER_SECOND / pixclk
                          : 0;

    __android_log_print(
        ANDROID_LOG_INFO, "hakuX-perf",
        "vblmode want=%lld derived=%lld (vtotal=%lld htotal=%lld pixclk=%lld "
        "vpll=%08x m=%u n=%u p=%u) cr00=%02x cr06=%02x cr07=%02x cr25=%02x "
        "cr2d=%02x msr=%02x vd=%u il=%02x res=%dx%d",
        (long long)period, (long long)derived,
        (long long)vtotal, (long long)htotal, (long long)pixclk,
        vco, vm, vn, vp,
        d->vga.cr[VGA_CRTC_H_TOTAL], d->vga.cr[VGA_CRTC_V_TOTAL],
        d->vga.cr[VGA_CRTC_OVERFLOW], d->vga.cr[0x25], d->vga.cr[0x2d],
        d->vga.msr, d->pramdac.fp_vdisplay_end,
        d->vga.cr[NV_PRMCIO_INTERLACE_MODE], w, h);

    /*
     * The other candidate raster, and the reason the first one could not have
     * worked.
     *
     * P7 derived the period from the VGA CRTC and the VPLL and missed by
     * -26.3%. That failure is sharper than it looks. With vtotal=525 fixed
     * and the VPLL decoded at 31,089,742 Hz, a 59.94 Hz frame needs a
     * horizontal total of 987.96 pixels -- and the VGA register can only
     * count whole 8-dot characters, so 123.5 of them is not a value it can
     * hold, whatever extension bits we have not decoded. No character width
     * (8, 9, 4) and no PDIV shift fixes that: halving or doubling the clock
     * keeps the fractional part. Nor can the clock be repaired instead: at
     * the CRTC's 728 pixels the period wants a 22,909,091 Hz pixel clock,
     * which is this VCO over 10.86 -- not a power of two, so not a PDIV
     * misread, and it would need a 12.28 MHz crystal, which is not one of
     * the parts. The two register groups cannot be reconciled by any decode;
     * they describe different rasters.
     *
     * The PRAMDAC flat-panel timing generator is the other one, and it counts
     * in PIXELS rather than characters, so it can hold 988 where the CRTC
     * cannot. This tree already believes the guest programs that block: the
     * VBLANK period has always been chosen off FP_VDISPLAY_END, which reads
     * 479 in a 640x480 title. FP_VTOTAL (0x804) and FP_HTOTAL (0x824) are the
     * two registers of it that were never modelled -- the writes fell through
     * pramdac.c's switch -- so they are stored now and printed here beside
     * everything else the block holds.
     *
     * If this derivation lands on the period and the CRTC one does not, the
     * FP raster is what reaches the encoder and the constants can go. If the
     * totals read 0, the guest never programs them, the flat-panel block is a
     * partial write, and the period has to come from outside the NV2A
     * entirely -- the AV pack or the kernel's video region. Either answer
     * ends the question; a zero is a result and not a broken run.
     */
    int64_t fp_vt = (int64_t)d->pramdac.fp_vtotal + 1;
    int64_t fp_ht = (int64_t)d->pramdac.fp_htotal + 1;
    int64_t derived_fp = (pixclk > 0 && d->pramdac.fp_vtotal &&
                          d->pramdac.fp_htotal)
                             ? fp_vt * fp_ht * NANOSECONDS_PER_SECOND / pixclk
                             : 0;

    __android_log_print(
        ANDROID_LOG_INFO, "hakuX-perf",
        "vblfp want=%lld derived_fp=%lld (fp_vtotal=%u fp_htotal=%u "
        "lines=%lld px=%lld) vde=%u hde=%u vcrtc=%u hcrtc=%u vsync=%u "
        "vvalid=%u hvalid=%u genctl=%08x sr01=%02x",
        (long long)period, (long long)derived_fp,
        d->pramdac.fp_vtotal, d->pramdac.fp_htotal,
        (long long)fp_vt, (long long)fp_ht,
        d->pramdac.fp_vdisplay_end, d->pramdac.fp_hdisplay_end,
        d->pramdac.fp_vcrtc, d->pramdac.fp_hcrtc,
        d->pramdac.fp_vsync_end, d->pramdac.fp_vvalid_end,
        d->pramdac.fp_hvalid_end, d->pramdac.general_control,
        d->vga.sr[VGA_SEQ_CLOCK_MODE]);

    /*
     * The PLL decode, checked against two clocks whose right answer is known
     * from outside this tree.
     *
     * Everything derived above hangs on one formula -- crystal * N / M / 2^P
     * with a 16.6667 MHz crystal -- applied to VPLL. If that formula or that
     * crystal is wrong, the pixel clock is wrong by a fixed factor and every
     * raster judged against it is wrong by the same factor, which is exactly
     * the shape of what the FP raster showed: 525 lines x 776 px needs
     * 24.42 MHz and we decode 31.09, a factor of 1.273.
     *
     * NVPLL and MPLL are the same formula on the same crystal, and the parts
     * they clock have documented speeds: the NV2A core runs at 233 MHz and
     * the memory at 200 MHz. So they are a calibration, not a diagnostic. If
     * they decode to those, the formula is sound and the pixel clock is what
     * the guest asked for, which puts the mismatch in the raster or in the
     * premise. If they come out 1.27x high -- 297 MHz and 255 MHz -- the
     * crystal is wrong by the very factor that would make the flat-panel
     * raster derive the period exactly, and the derivation is back.
     *
     * Nothing here can choose between those: the guest programs both
     * coefficients and this only reads them back.
     */
    uint32_t nco = d->pramdac.core_clock_coeff;
    uint32_t mco = d->pramdac.memory_clock_coeff;
    uint32_t nm  = nco & NV_PRAMDAC_NVPLL_COEFF_MDIV;
    uint32_t nn  = (nco & NV_PRAMDAC_NVPLL_COEFF_NDIV) >> 8;
    uint32_t np  = (nco & NV_PRAMDAC_NVPLL_COEFF_PDIV) >> 16;
    uint32_t mm  = mco & NV_PRAMDAC_MPLL_COEFF_MDIV;
    uint32_t mn  = (mco & NV_PRAMDAC_MPLL_COEFF_NDIV) >> 8;
    uint32_t mp  = (mco & NV_PRAMDAC_MPLL_COEFF_PDIV) >> 16;
    int64_t  nvclk = nm ? (int64_t)NV2A_CRYSTAL_FREQ * nn / (1 << np) / nm : 0;
    int64_t  mclk  = mm ? (int64_t)NV2A_CRYSTAL_FREQ * mn / (1 << mp) / mm : 0;

    __android_log_print(
        ANDROID_LOG_INFO, "hakuX-perf",
        "vblpll xtal=%d nvpll=%08x(m=%u n=%u p=%u) core=%lld stored=%lld "
        "mpll=%08x(m=%u n=%u p=%u) mem=%lld vpll=%08x pix=%lld",
        NV2A_CRYSTAL_FREQ, nco, nm, nn, np, (long long)nvclk,
        (long long)d->pramdac.core_clock_freq,
        mco, mm, mn, mp, (long long)mclk, vco, (long long)pixclk);

    /*
     * Phase, and the coalescing attribution. On its own line rather than
     * appended to `vbl`, because vblank_report.py and vblank_ab.py both parse
     * `vbl` with one exact regex and a widened line would simply stop
     * matching -- which reads as a soak that emitted nothing.
     */
    int64_t late_mean = s_vbh.late_n
                            ? (int64_t)(s_vbh.late_sum / s_vbh.late_n) : 0;
    int64_t late_nodef_mean = s_vbh.late_nodef_n
        ? (int64_t)(s_vbh.late_nodef_sum / s_vbh.late_nodef_n) : 0;
    int64_t late_def_mean = s_vbh.late_def_n
        ? (int64_t)(s_vbh.late_def_sum / s_vbh.late_def_n) : 0;
    int64_t coal_gap_mean = s_vbh.coalesced
        ? (int64_t)(s_vbh.coal_gap_sum / s_vbh.coalesced) : 0;

    __android_log_print(
        ANDROID_LOG_INFO, "hakuX-perf",
        "vblphase n=%u period=%lld mean=%lld p50=%lld p90=%lld p99=%lld "
        "max=%lld neg=%u nodef(n=%u mean=%lld max=%lld) "
        "def(n=%u mean=%lld max=%lld) unl=%u "
        "coal=%u coal_en=%u coal_short=%u coal_gap=%lld en=%u clamp=%u",
        s_vbh.late_n, (long long)period, (long long)late_mean,
        (long long)vbh_pct_of(s_vbh.late_bucket, s_vbh.late_n, 50),
        (long long)vbh_pct_of(s_vbh.late_bucket, s_vbh.late_n, 90),
        (long long)vbh_pct_of(s_vbh.late_bucket, s_vbh.late_n, 99),
        (long long)s_vbh.late_max, s_vbh.late_neg,
        s_vbh.late_nodef_n, (long long)late_nodef_mean,
        (long long)s_vbh.late_nodef_max,
        s_vbh.late_def_n, (long long)late_def_mean,
        (long long)s_vbh.late_def_max,
        s_vbh.unlocked_n,
        s_vbh.coalesced, s_vbh.coal_enabled, s_vbh.coal_short,
        (long long)coal_gap_mean,
        (unsigned)((d->pcrtc.enabled_interrupts &
                    NV_PCRTC_INTR_EN_0_VBLANK) ? 1 : 0),
        s_vbh.clamped);

    __android_log_print(
        ANDROID_LOG_INFO, "hakuX-perf",
        "vbl n=%u win=%lldms want=%lld got=%lld drift=%+lld rate=%lld.%03lldHz "
        "p1=%lld p50=%lld p90=%lld p99=%lld min=%lld max=%lld "
        "src(tmr=%u smp=%u gfx=%u) coal=%u def=%u rast=%u/%u",
        s_vbh.n, (long long)(span_ns / 1000000),
        (long long)period, (long long)mean_ns,
        (long long)(mean_ns - period),
        (long long)(mhz / 1000), (long long)(mhz % 1000),
        (long long)vbh_percentile(1), (long long)vbh_percentile(50),
        (long long)vbh_percentile(90), (long long)vbh_percentile(99),
        (long long)(s_vbh.n ? s_vbh.min_ns : 0), (long long)s_vbh.max_ns,
        s_vbh.src[VBH_SRC_TIMER], s_vbh.src[VBH_SRC_SIMPLE],
        s_vbh.src[VBH_SRC_GFX], s_vbh.coalesced, s_vbh.deferred,
        s_vbh.raster_reads, s_vbh.raster_reads_max);

    memset(s_vbh.bucket, 0, sizeof(s_vbh.bucket));
    memset(s_vbh.late_bucket, 0, sizeof(s_vbh.late_bucket));
    memset(s_vbh.src, 0, sizeof(s_vbh.src));
    s_vbh.n = 0;
    s_vbh.late_n = 0;
    s_vbh.late_neg = 0;
    s_vbh.late_sum = 0;
    s_vbh.late_max = 0;
    s_vbh.late_nodef_n = 0;
    s_vbh.late_nodef_sum = 0;
    s_vbh.late_nodef_max = 0;
    s_vbh.late_def_n = 0;
    s_vbh.late_def_sum = 0;
    s_vbh.late_def_max = 0;
    s_vbh.unlocked_n = 0;
    s_vbh.clamped = 0;
    s_vbh.coal_enabled = 0;
    s_vbh.coal_short = 0;
    s_vbh.coal_gap_sum = 0;
    s_vbh.coalesced = 0;
    s_vbh.deferred = 0;
    s_vbh.raster_reads = 0;
    s_vbh.raster_reads_max = 0;
    s_vbh.min_ns = 0;
    s_vbh.max_ns = 0;
    s_vbh.sum_ns = 0;
    s_vbh.window_start_ns = now;
}

/*
 * Call immediately BEFORE the pending-interrupt OR, so the coalescing check
 * still sees the state the guest left behind.
 *
 * `grid_target_ns` is the slot this assertion was SCHEDULED into, i.e.
 * d->vblank_next_target_ns before the caller advances it, or 0 for a source
 * that is not on the grid at all. The distinction is the point: an assertion
 * with no grid target has no phase to be wrong about, and in simple-VBLANK
 * mode the host-refresh source is exactly that -- which is half of why two
 * sources for one event cannot be summarised by one number.
 */
static void nv2a_vblank_record(NV2AState *d, int src, bool was_deferred,
                               int64_t grid_target_ns)
{
    int64_t now = qemu_clock_get_ns(QEMU_CLOCK_REALTIME);

    if (d->pcrtc.pending_interrupts & NV_PCRTC_INTR_0_VBLANK) {
        s_vbh.coalesced++;
        if (d->pcrtc.enabled_interrupts & NV_PCRTC_INTR_EN_0_VBLANK) {
            s_vbh.coal_enabled++;
        }
        /* The interval this coalesce arrived at the end of. A coalesce after
         * a SHORT interval is one our own machinery caused; after a full
         * period it is the guest's ISR being slow, which hardware has too. */
        if (s_vbh.last_ns) {
            int64_t gap = now - s_vbh.last_ns;
            s_vbh.coal_gap_sum += (uint64_t)(gap > 0 ? gap : 0);
            if (gap < nv2a_calc_vblank_period_ns(d)) {
                s_vbh.coal_short++;
            }
        }
    }
    if (was_deferred) {
        s_vbh.deferred++;
    }
    if (d->unlock_mode_active) {
        s_vbh.unlocked_n++;
    }
    if (grid_target_ns) {
        int64_t late = now - grid_target_ns;

        if (late < 0) {
            /* The impossible row. See the struct comment: this is here to be
             * zero, and a non-zero count means a writer this file does not
             * account for moved the grid under an armed timer. */
            s_vbh.late_neg++;
            late = 0;
        }
        int idx = (int)(late / VBH_BUCKET_NS);
        if (idx > VBH_BUCKETS) {
            idx = VBH_BUCKETS;
        }
        s_vbh.late_bucket[idx]++;
        s_vbh.late_n++;
        s_vbh.late_sum += (uint64_t)late;
        if (late > s_vbh.late_max) {
            s_vbh.late_max = late;
        }
        if (was_deferred) {
            s_vbh.late_def_n++;
            s_vbh.late_def_sum += (uint64_t)late;
            if (late > s_vbh.late_def_max) {
                s_vbh.late_def_max = late;
            }
        } else {
            s_vbh.late_nodef_n++;
            s_vbh.late_nodef_sum += (uint64_t)late;
            if (late > s_vbh.late_nodef_max) {
                s_vbh.late_nodef_max = late;
            }
        }
    }
    s_vbh.src[src]++;
    /* Read before the caller zeroes it, so this is the count for the period
     * that just ended rather than the one starting. */
    s_vbh.raster_reads += d->pcrtc.raster;
    if (d->pcrtc.raster > s_vbh.raster_reads_max) {
        s_vbh.raster_reads_max = d->pcrtc.raster;
    }

    if (s_vbh.last_ns) {
        int64_t delta = now - s_vbh.last_ns;
        int idx = (int)(delta / VBH_BUCKET_NS);

        if (idx < 0) {
            idx = 0;
        } else if (idx > VBH_BUCKETS) {
            idx = VBH_BUCKETS;
        }
        s_vbh.bucket[idx]++;
        s_vbh.sum_ns += (uint64_t)delta;
        if (!s_vbh.n || delta < s_vbh.min_ns) {
            s_vbh.min_ns = delta;
        }
        if (delta > s_vbh.max_ns) {
            s_vbh.max_ns = delta;
        }
        s_vbh.n++;
    }
    s_vbh.last_ns = now;

    if (!s_vbh.window_start_ns) {
        s_vbh.window_start_ns = now;
    } else if (now - s_vbh.window_start_ns >= VBH_WINDOW_NS && s_vbh.n >= 8) {
        vbh_dump_and_reset(d, now);
    }
}

static void nv2a_vblank_note_clamp(void)
{
    s_vbh.clamped++;
}

#else
#define nv2a_vblank_record(d, src, was_deferred, grid) ((void)0)
#define nv2a_vblank_note_clamp() ((void)0)
#endif

static int64_t s_last_vblank_fire_ns;

/*
 * The `J` figure in the pacing line, updated from wherever a VBLANK was
 * actually asserted.
 *
 * This used to live inline in the adaptive callback only, so in simple-VBLANK
 * mode `s_last_vblank_fire_ns` was never written and the EWMA never updated:
 * `J` read its initial 0.0 and the "0.0 ms jitter" row for `simple_vblank` in
 * docs/investigations/frame-pacing-and-parallelism.md was that artefact rather
 * than a clean VBLANK. A number that is zero because nothing wrote it is worse
 * than an absent one -- it reads as the best result in the table.
 *
 * `J` remains a poor summary of jitter and the histogram above is the reason:
 * an exponential mean of |delta - period| cannot tell a 0.25 ms symmetric
 * jitter from a mode accurate to 0.1% with a 28 ms tail. What it can now do is
 * mean the same thing in both modes.
 */
static void nv2a_vblank_note_fire(int64_t period, int64_t now)
{
    if (s_last_vblank_fire_ns) {
        float delta_ms = (float)(now - s_last_vblank_fire_ns) / 1e6f;
        float expected_ms = (float)period / 1e6f;
        float jitter = delta_ms - expected_ms;

        if (jitter < 0) {
            jitter = -jitter;
        }
        g_nv2a_stats.pacing.vblank_jitter_ms =
            g_nv2a_stats.pacing.vblank_jitter_ms * 0.9f + jitter * 0.1f;
    }
    s_last_vblank_fire_ns = now;
}

#ifdef __ANDROID__
/* Simple VBLANK mode: matches x1_box behavior.  Just fires the PCRTC
 * interrupt at a fixed interval — no adaptive deferral, no flip assists,
 * no NOP recovery.  For debugging game-specific timing issues. */
static bool g_simple_vblank_mode = false;

void nv2a_set_simple_vblank(bool enable)
{
    g_simple_vblank_mode = enable;
}

bool nv2a_get_simple_vblank(void)
{
    return g_simple_vblank_mode;
}

static void nv2a_simple_vblank_cb(NV2AState *d)
{
    int64_t period = nv2a_calc_vblank_period_ns(d);
    int64_t now = qemu_clock_get_ns(QEMU_CLOCK_REALTIME);

    /* Count here too. The adaptive path owns the stats and this one did not
     * touch them, so every pacing figure derived from the VBLANK count read
     * zero in simple mode -- exactly the mode you switch to when you want
     * pacing numbers with the deferral heuristics out of the way. */
    g_nv2a_stats.pacing.vblank_fired++;
    nv2a_vblank_note_fire(period, now);
    nv2a_vblank_record(d, VBH_SRC_SIMPLE, false, d->vblank_next_target_ns);

    /* Pure x1_box behavior: fire PCRTC interrupt, update IRQ.
     * No adaptive deferral, no flip auto-completion, no NOP assist.
     * The guest kernel handles everything itself.
     *
     * This is the ONLY source of a VBLANK in this mode, and it was not. See
     * nv2a_vga_gfx_update below for what else used to assert one and why that
     * made this mode useless as the baseline it exists to be.
     */
    d->pcrtc.pending_interrupts |= NV_PCRTC_INTR_0_VBLANK;
    d->pcrtc.raster = 0;
    nv2a_update_irq(d);

    d->vblank_next_target_ns += period;
    if (d->vblank_next_target_ns <= now) {
        d->vblank_next_target_ns = now + period;
        nv2a_vblank_note_clamp();
    }
    timer_mod(d->vblank_timer, d->vblank_next_target_ns);
}
#endif


static void nv2a_vblank_timer_cb(void *opaque)
{
    NV2AState *d = opaque;

#ifdef __ANDROID__
    if (g_simple_vblank_mode) {
        nv2a_simple_vblank_cb(d);
        return;
    }
#endif

    int64_t period = nv2a_calc_vblank_period_ns(d);
    int64_t now = qemu_clock_get_ns(QEMU_CLOCK_REALTIME);

    /*
     * Adaptive VBLANK: defer this VBLANK when the game is actively
     * rendering and barely missed the deadline.
     *
     * In normal mode, the deferral window covers ~1.25 VBLANK periods
     * after the last FLIP call, targeting games that take slightly
     * longer than one period to render.
     *
     * "Unlock framerate" mode widens the window and cap, but only
     * engages when the game's frame time is near one VBLANK period
     * (i.e. targeting ~60fps). 30fps games (frame time ~2 periods)
     * always use normal deferral so their intermediate VBLANKs are
     * preserved for frame-count-based timing.
     *
     * The !waiting_for_flip check ensures we never defer a VBLANK
     * that the game is actively waiting for. When the game calls
     * FLIP_STALL, it fires the deferred VBLANK immediately via
     * timer_mod, so actual deferral latency is minimal.
     */
    /*
     * Use the smoothed frame time to determine unlock mode with
     * hysteresis to prevent thrashing at the boundary.
     *
     * Enter unlock mode when frame time < 1.5 periods (~60fps zone).
     * Exit only when frame time > 2.5 periods (well into 30fps).
     *
     * Without hysteresis, a game dipping from 60fps to ~40fps would
     * cross the threshold, lose the generous deferral window, fall to
     * 30fps, and get permanently trapped because the 30fps frame time
     * keeps the threshold exceeded.
     */
    int64_t effective_frame_ns = d->avg_frame_ns ? d->avg_frame_ns
                                                 : d->last_frame_ns;
    /*
     * Diagnostic override. Unlock mode is entered only by a title whose frame
     * time is already under 1.5 periods, which is the state it exists to
     * produce: a title sitting at two periods can never reach the entry
     * condition, so it stays locked however much headroom appears. Forcing it
     * on says whether that bootstrap is what holds a given title at half
     * rate, or whether the title asked for half rate itself.
     */
    static int force_unlock = -1;
    if (force_unlock == -1) {
        const char *e = getenv("HAKUX_FORCE_UNLOCK");
        force_unlock = (e && e[0] && e[0] != '0') ? 1 : 0;
    }

    if (force_unlock) {
        d->unlock_mode_active = true;
    } else if (g_config.perf.unlock_framerate && effective_frame_ns > 0) {
        int64_t enter_thresh = period + period / 2;
        int64_t exit_thresh  = period * 2 + period / 2;
        if (!d->unlock_mode_active && effective_frame_ns < enter_thresh) {
            d->unlock_mode_active = true;
        } else if (d->unlock_mode_active && effective_frame_ns > exit_thresh) {
            d->unlock_mode_active = false;
        }
    } else {
        d->unlock_mode_active = false;
    }
    bool unlocked = d->unlock_mode_active;
    int64_t time_in_frame = d->last_flip_ns ? (now - d->last_flip_ns) : 0;
    int64_t defer_window;
    if (unlocked) {
        defer_window = period * 3;
    } else {
        /*
         * Graduated deferral: scale the window to the actual frame time
         * with 20% headroom so the game can finish, but cap below
         * 2 periods so genuine 30fps games' intermediate VBLANKs fire.
         */
        int64_t adaptive = effective_frame_ns + effective_frame_ns / 5;
        int64_t floor    = period + period / 4;
        int64_t cap      = period * 2 - period / 4;
        defer_window = MIN(MAX(adaptive, floor), cap);
    }
    /*
     * The deferral hold, in poll intervals, and the one place where it has to
     * answer to the grid rather than to the frame rate.
     *
     * `max_defer = poll_interval * defer_cap` below. In normal mode that is
     * `(period/8) * 4 = period/2`, and a deferral alone can never push an
     * assertion past its next grid slot -- which is exactly why the locked
     * regime delivers 59.941 Hz at +0.005 s/min of drift. In unlock mode it
     * was `(period/16) * 16 = period` to the nanosecond, and that is the one
     * value the grid cannot absorb: the assertion lands at
     * `slot + L + max_defer + L'` for a timer round trip L + L' > 0, the
     * `<= now` clamp fires, and the grid is re-based on `now + period`
     * instead of `slot + period` -- discarding the WHOLE lateness, not the
     * excess over a period. Measured on #65's arm B (DOA3, thor): 843,164 ns
     * of permanent drift per assertion in fully-unlocked windows, 3.03 s of
     * guest-visible time lost per minute of play, on a mode that is on by
     * default for every title above about 40 fps.
     *
     * The grid's own arithmetic picks the value, and it is not a tuning
     * parameter. The next slot is one period away; the cap is quantised in
     * poll intervals; a period is sixteen of them. So the largest cap that
     * leaves the grid ANY room is fifteen, and the room it leaves is one poll
     * interval = 1,042,734 ns, which is what the timer round trip has to fit
     * inside. That round trip is measurable directly as
     * `def(mean=) - max_defer` and reads 126,275 / 126,526 / 132,679 /
     * 178,460 ns across the four cap-bound windows of that soak -- 5.8x to
     * 8.3x inside the margin. Cost: the hold loses 6.25% of its length.
     *
     * Where this value is wrong: a host whose timer round trip exceeds
     * 1,042,734 ns. The nova's non-deferred lateness is 3.4x the thor's
     * (360,179 against 104,923 ns), which puts its round trip near 720,000 ns
     * and the margin at only 1.4x. If the clamp still fires there, the
     * reasoning is unchanged and the value is fourteen; nothing above needs
     * revisiting. That is the failure world, stated before the arm ran.
     *
     * Deliberately NOT changed: `poll_interval`, so the retry granularity is
     * the same and this is one constant; and the normal-mode pair, which the
     * arithmetic already exonerates.
     */
    int defer_cap = unlocked ? 15 : 4;
    int64_t poll_interval = unlocked ? period / 16 : period / 8;
    bool in_deferral_window = effective_frame_ns > 0 &&
                              time_in_frame < defer_window;

    /*
     * The graduated deferral cap (period * 2 - period / 4 = ~29ms) already
     * prevents genuine 30fps games from getting deferral. No additional
     * android_allow_defer guard is needed — it was causing games to get
     * trapped at 30fps by killing deferral in the recovery zone (30-36fps)
     * where the game could speed back up if given modest deferral headroom.
     */
    if (in_deferral_window &&
        d->flip_active &&
        !qatomic_read(&d->pgraph.waiting_for_flip) &&
        !d->vblank_deferred) {
        int64_t max_defer = poll_interval * defer_cap;
        int64_t remaining = defer_window - time_in_frame;
        int64_t fire_at = now + MIN(max_defer, remaining);

        d->vblank_defer_count = 1;
        qatomic_set(&d->vblank_deferred, true);
        timer_mod(d->vblank_timer, fire_at);
        return;
    }

    bool was_deferred = d->vblank_defer_count > 0;
    d->vblank_defer_count = 0;
    qatomic_set(&d->vblank_deferred, false);

    /* Track VBLANK firing stats */
    g_nv2a_stats.pacing.vblank_fired++;
    g_nv2a_stats.pacing.unlock_mode_active = unlocked;
    if (was_deferred) {
        g_nv2a_stats.pacing.defers_total++;
        if (d->vblank_defer_request_ns) {
            float delivery_ms = (float)(now - d->vblank_defer_request_ns) / 1e6f;
            g_nv2a_stats.pacing.vblank_delivery_ms =
                g_nv2a_stats.pacing.vblank_delivery_ms * 0.8f + delivery_ms * 0.2f;
            d->vblank_defer_request_ns = 0;
        }
    }
    nv2a_vblank_note_fire(period, now);

    nv2a_vblank_record(d, VBH_SRC_TIMER, was_deferred,
                       d->vblank_next_target_ns);
    d->pcrtc.pending_interrupts |= NV_PCRTC_INTR_0_VBLANK;
    d->pcrtc.raster = 0;


    nv2a_update_irq(d);

    /*
     * Advance the VBLANK target.
     *
     * The grid is fixed: advance by exactly one period from where the last
     * one was SCHEDULED, not from where it fired. That is what keeps the
     * guest's VBLANK clock keeping time. A callback that runs late leaves the
     * next target closer than a period away, and the short interval that
     * follows is the grid correcting itself -- 7.1 ms intervals against a
     * 16.68 ms period show up in a real soak and are this working, not a
     * fault. The clamp below is the only escape, for a callback more than a
     * whole period late, where there is nothing left to correct into.
     *
     * A deferred VBLANK used to be excluded from this and restarted the grid
     * from `now`, so every deferral shifted the phase forward permanently and
     * nothing ever gave it back. The comment that stood here defended it: the
     * fixed grid leaves a deferred frame less than a period to finish in, and
     * "caus[es] a cascade where every subsequent frame also misses -- locking
     * the game to 30fps". That is a real cost and it is a frame-rate cost.
     * What it bought was paid for in the guest's timebase, and nobody had
     * priced that side until it was measured:
     *
     *   Galleon, 240 s, Thor, 19f52510d9 -- 14,653 VBLANK assertions
     *     windows with no deferral   16,712,711 ns mean, 59.844 Hz
     *     windows with 1-20 defers   17,198,838 ns mean, 58.186 Hz
     *     windows with >20 defers    19,159,610 ns mean, 52.285 Hz
     *     whole soak                 17,747,165 ns mean, 56.587 Hz
     *
     * So the period itself is right to 0.17% and its p99 to 1%, and the
     * deferral machinery takes the delivered rate 5.6% below the rate we
     * intend -- 3.8 seconds lost per minute of play for anything that counts
     * VBLANKs to measure time, and 8.9 s/min in heavy scenes.
     *
     * `unlocked` used to reset the grid too, and that half was left alone
     * deliberately -- Galleon never enters unlock mode (`Ul:N` on all 129
     * windows of both arms) so neither arm could measure it, and moving two
     * things at once would have made the half that was measurable unreadable.
     * It is fixed here, on the same reasoning and one measurement further on.
     *
     * The condition was `was_deferred || unlocked`, and the second half was
     * never about deferral: while unlock mode is active EVERY VBLANK reset the
     * target to `now + period`, deferred or not. A QEMU timer fires at or
     * after its deadline and never before, so that added the callback's own
     * lateness to the period on every single VBLANK and compounded it instead
     * of letting a fixed grid absorb it. A mean lateness of 0.3 ms is a
     * permanent 16.98 ms period -- 58.9 Hz, 1.8% slow -- for as long as the
     * mode is held, and `unlock_framerate` defaults to TRUE.
     *
     * Which inverts the intuition: the titles whose pacing looks healthiest
     * are the ones running with no phase grid, because the mode is entered
     * whenever smoothed frame time is under 1.5 periods. The measurement that
     * makes this arm possible is Dead or Alive 3, which reports `Ul:Y` on 15
     * of 47 windows and a `gfps` ceiling of 59 -- the fast title #65 said this
     * half needed and did not have.
     *
     * The grid is now the sole authority on when a VBLANK happens. The
     * deferral retry and FLIP_STALL's `timer_mod(now)` still move the TIMER,
     * which is how a single VBLANK's phase is distorted, but neither writes
     * the target, so what they shift the grid gives back on the next one.
     * `vblphase` above measures exactly that residue.
     */
    d->vblank_next_target_ns += period;
    if (d->vblank_next_target_ns <= now) {
        d->vblank_next_target_ns = now + period;
        nv2a_vblank_note_clamp();
    }
    timer_mod(d->vblank_timer, d->vblank_next_target_ns);

    /* Wake the PFIFO thread when a diag capture is pending or active
     * so the capture progresses even if the game is idle. */
    if (nv2a_dbg_diag_frame_pending() || nv2a_dbg_diag_frame_active()) {
        pfifo_kick(d);
    }
}

void nv2a_vblank_recalc(NV2AState *d)
{
    if (d->vblank_timer) {
        int64_t period = nv2a_calc_vblank_period_ns(d);
        d->vblank_next_target_ns = qemu_clock_get_ns(QEMU_CLOCK_REALTIME) + period;
        timer_mod(d->vblank_timer, d->vblank_next_target_ns);
    }
}

static void nv2a_vga_gfx_update(void *opaque)
{
    VGACommonState *vga = opaque;
    vga->hw_ops->gfx_update(vga);

    /*
     * This also asserted NV_PCRTC_INTR_0_VBLANK whenever
     * g_simple_vblank_mode was set, so that mode had TWO sources for one
     * event: the period timer at 59.94 Hz and this one at the host panel's
     * refresh, for 150-180 assertions a second on a 90-120 Hz handheld. Both
     * landed in 4b70acfb85, whose message calls the mode "60Hz" and describes
     * this half as a `graphic_hw_update` CALL -- so the second interrupt
     * source is incidental, and its own comment conceded that it "makes games
     * run too fast".
     *
     * The host panel is not on any grid this file can see and is not a fixed
     * multiple of the period, so a title stepping off VBLANK was stepping off
     * the sum of a 59.94 Hz clock and the viewer's display. It also made the
     * mode useless as the instrument it exists to be; see
     * docs/investigations/guest-visible-vblank.md.
     *
     * The `graphic_hw_update` call in ui/xemu.c that drives this function
     * every host refresh in simple mode stays: it is what keeps the display
     * updating, and it is the half of that commit the message describes. Only
     * the interrupt is gone.
     */
}

static void nv2a_init_memory(NV2AState *d, MemoryRegion *ram)
{
    /* xbox is UMA - vram *is* ram */
    d->vram = ram;

     /* PCI exposed vram */
    memory_region_init_alias(&d->vram_pci, OBJECT(d), "nv2a-vram-pci", d->vram,
                             0, memory_region_size(d->vram));
    pci_register_bar(PCI_DEVICE(d), 1, PCI_BASE_ADDRESS_MEM_PREFETCH, &d->vram_pci);


    /* RAMIN - should be in vram somewhere, but not quite sure where atm */
    memory_region_init_ram(&d->ramin, OBJECT(d), "nv2a-ramin", 0x100000, &error_fatal);
    /* memory_region_init_alias(&d->ramin, "nv2a-ramin", &d->vram,
                         memory_region_size(d->vram) - 0x100000,
                         0x100000); */

    memory_region_add_subregion(&d->mmio, 0x700000, &d->ramin);


    d->vram_ptr = memory_region_get_ram_ptr(d->vram);
    d->ramin_ptr = memory_region_get_ram_ptr(&d->ramin);

    memory_region_set_log(d->vram, true, DIRTY_MEMORY_NV2A);
    memory_region_set_log(d->vram, true, DIRTY_MEMORY_NV2A_TEX);
    memory_region_set_dirty(d->vram, 0, memory_region_size(d->vram));

    pgraph_init(d);

    /* fire up pfifo */
    qemu_thread_create(&d->pfifo.thread, "nv2a.pfifo_thread",
                       pfifo_thread, d, QEMU_THREAD_JOINABLE);
}

static void nv2a_init_vga(NV2AState *d)
{
    VGACommonState *vga = &d->vga;
    vga->vram_size_mb = memory_region_size(d->vram) / MiB;

    vga_common_init(vga, OBJECT(d), &error_fatal);
    vga->get_bpp = nv2a_get_bpp;
    vga->get_params = nv2a_get_params;
    // vga->overlay_draw_line = nv2a_overlay_draw_line;

    d->hw_ops = *vga->hw_ops;
    d->hw_ops.gfx_update = nv2a_vga_gfx_update;
    vga->con = graphic_console_init(DEVICE(d), 0, &d->hw_ops, vga);

    /* hacky. swap out vga's vram */
    memory_region_destroy(&vga->vram);
    // memory_region_unref(&vga->vram); // FIXME: Is ths right?
    memory_region_init_alias(&vga->vram, OBJECT(d), "vga.vram",
                             d->vram, 0, memory_region_size(d->vram));
    vga->vram_ptr = memory_region_get_ram_ptr(&vga->vram);
    vga_dirty_log_start(vga);

    d->vblank_timer = timer_new_ns(QEMU_CLOCK_REALTIME,
                                   nv2a_vblank_timer_cb, d);
    d->vblank_next_target_ns = qemu_clock_get_ns(QEMU_CLOCK_REALTIME) +
                               NANOSECONDS_PER_SECOND / 60;
    d->flip_active = false;
    d->vblank_defer_count = 0;
    d->last_flip_ns = 0;
    d->last_frame_ns = 0;
    d->avg_frame_ns = 0;
    d->unlock_mode_active = false;
    timer_mod(d->vblank_timer, d->vblank_next_target_ns);
}

static void nv2a_lock_fifo(NV2AState *d)
{
    qemu_mutex_lock(&d->pfifo.lock);
    d->pfifo.fifo_kick = true;
    qemu_cond_broadcast(&d->pfifo.fifo_cond);
    bql_unlock();
    qemu_cond_wait(&d->pfifo.fifo_idle_cond, &d->pfifo.lock);
    bql_lock();
    qemu_mutex_lock(&d->pgraph.lock);
}

static void nv2a_unlock_fifo(NV2AState *d)
{
    pfifo_kick(d);
    qemu_mutex_unlock(&d->pgraph.lock);
    qemu_mutex_unlock(&d->pfifo.lock);
}

static void nv2a_reset(NV2AState *d)
{
    nv2a_lock_fifo(d);
    bool halted = qatomic_read(&d->pfifo.halt);
    if (!halted) {
        qatomic_set(&d->pfifo.halt, true);
    }
    qemu_event_reset(&d->pgraph.flush_complete);
    qatomic_set(&d->pgraph.flush_pending, true);
    nv2a_unlock_fifo(d);
    bql_unlock();
    qemu_event_wait(&d->pgraph.flush_complete);
    bql_lock();
    nv2a_lock_fifo(d);
    if (!halted) {
        qatomic_set(&d->pfifo.halt, false);
    }

    memset(d->pfifo.regs, 0, sizeof(d->pfifo.regs));
    memset(d->pgraph.regs_, 0, sizeof(d->pgraph.regs_));
    memset(d->pvideo.regs, 0, sizeof(d->pvideo.regs));

    d->pcrtc.start = 0;
    d->pramdac.core_clock_coeff = 0x00011C01; /* 189MHz...? */
    d->pramdac.core_clock_freq = 233333324;
    d->pramdac.memory_clock_coeff = 0;
    d->pramdac.video_clock_coeff = 0x0003C20D; /* 25182Khz...? */

    d->pfifo.regs[NV_PFIFO_CACHE1_STATUS] |= NV_PFIFO_CACHE1_STATUS_LOW_MARK;

    vga_common_reset(&d->vga);
    /* seems to start in color mode */
    d->vga.msr = VGA_MIS_COLOR;

    d->pgraph.waiting_for_nop = false;
    d->pgraph.waiting_for_flip = false;
    d->flip_active = false;
    d->vblank_defer_count = 0;
    d->last_flip_ns = 0;
    d->last_frame_ns = 0;
    d->avg_frame_ns = 0;
    d->unlock_mode_active = false;
    d->vblank_deferred = false;
    d->pgraph.waiting_for_context_switch = false;

    d->pmc.pending_interrupts = 0;
    d->pfifo.pending_interrupts = 0;
    d->ptimer.pending_interrupts = 0;
    d->pcrtc.pending_interrupts = 0;

    for (int i = 0; i < 256; i++) {
        d->puserdac.palette[i*3]   = i;
        d->puserdac.palette[i*3+1] = i;
        d->puserdac.palette[i*3+2] = i;
    }

    nv2a_unlock_fifo(d);
}

static void nv2a_realize(PCIDevice *dev, Error **errp)
{
    NV2AState *d = NV2A_DEVICE(dev);

    /* setting subsystem ids again, see comment in nv2a_class_init() */
    pci_set_word(dev->config + PCI_SUBSYSTEM_VENDOR_ID, 0);
    pci_set_word(dev->config + PCI_SUBSYSTEM_ID, 0);
    dev->config[PCI_INTERRUPT_PIN] = 0x01;

    /* mmio */
    memory_region_init(&d->mmio, OBJECT(dev), "nv2a-mmio", 0x1000000);
    pci_register_bar(PCI_DEVICE(d), 0, PCI_BASE_ADDRESS_SPACE_MEMORY, &d->mmio);

    for (int i=0; i < ARRAY_SIZE(blocktable); i++) {
        if (!blocktable[i].name) continue;
        memory_region_init_io(&d->block_mmio[i], OBJECT(dev),
                              &blocktable[i].ops, d,
                              blocktable[i].name, blocktable[i].size);
        memory_region_add_subregion(&d->mmio, blocktable[i].offset,
                                    &d->block_mmio[i]);
    }

    qemu_mutex_init(&d->pfifo.lock);
    qemu_cond_init(&d->pfifo.fifo_cond);
    qemu_cond_init(&d->pfifo.fifo_idle_cond);
    qemu_cond_init(&d->pfifo.fifo_drained_cond);
}

static void nv2a_exitfn(PCIDevice *dev)
{
    NV2AState *d;
    d = NV2A_DEVICE(dev);

    d->exiting = true;

    qemu_cond_broadcast(&d->pfifo.fifo_cond);
    qemu_thread_join(&d->pfifo.thread);

    pgraph_destroy(&d->pgraph);
}

static void nv2a_reset_hold(Object *obj, ResetType type)
{
    NV2AState *s = NV2A_DEVICE(obj);
    nv2a_reset(s);
}

// Note: This is handled as a VM state change and not as a `pre_save` callback
// because we want to halt the FIFO before any VM state is saved/restored to
// avoid corruption.
static void nv2a_vm_state_change(void *opaque, bool running, RunState state)
{
    NV2AState *d = opaque;
    if (state == RUN_STATE_SAVE_VM) {
        nv2a_lock_fifo(d);
        qatomic_set(&d->pfifo.halt, true);
        pgraph_pre_savevm_trigger(d);
        nv2a_unlock_fifo(d);
        bql_unlock();
        pgraph_pre_savevm_wait(d);
        bql_lock();
        nv2a_lock_fifo(d);
    } else if (state == RUN_STATE_RESTORE_VM) {
        nv2a_lock_fifo(d);
        qatomic_set(&d->pfifo.halt, true);
        nv2a_unlock_fifo(d);
    } else if (state == RUN_STATE_RUNNING) {
        nv2a_lock_fifo(d);
        qatomic_set(&d->pfifo.halt, false);
        nv2a_unlock_fifo(d);
    } else if (state == RUN_STATE_SHUTDOWN) {
        nv2a_lock_fifo(d);
        pgraph_pre_shutdown_trigger(d);
        nv2a_unlock_fifo(d);
        bql_unlock();
        pgraph_pre_shutdown_wait(d);
        bql_lock();
    }
}

static int nv2a_post_save(void *opaque)
{
    NV2AState *d = opaque;
    nv2a_unlock_fifo(d);
    return 0;
}

static int nv2a_pre_load(void *opaque)
{
    NV2AState *d = opaque;
    nv2a_lock_fifo(d);
    return 0;
}

static int nv2a_post_load(void *opaque, int version_id)
{
    NV2AState *d = opaque;
    qatomic_set(&d->pgraph.flush_pending, true);
    nv2a_unlock_fifo(d);
    return 0;
}

const VMStateDescription vmstate_nv2a_pgraph_vertex_attributes = {
    .name = "nv2a/pgraph/vertex-attr",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (VMStateField[]) {
        // FIXME
        VMSTATE_END_OF_LIST()
    }
};

static const VMStateDescription vmstate_nv2a = {
    .name = "nv2a",
    .version_id = 3,
    .minimum_version_id = 1,
    .post_save = nv2a_post_save,
    .post_load = nv2a_post_load,
    .pre_load = nv2a_pre_load,
    .fields = (VMStateField[]) {
        // FIXME: Split this up into subsections
        VMSTATE_PCI_DEVICE(parent_obj, NV2AState),
        VMSTATE_STRUCT(vga, NV2AState, 0, vmstate_vga_common, VGACommonState),
        VMSTATE_UINT32(pgraph.pending_interrupts, NV2AState),
        VMSTATE_UINT32(pgraph.enabled_interrupts, NV2AState),
        VMSTATE_UINT64(pgraph.context_surfaces_2d.object_instance, NV2AState),
        VMSTATE_UINT64(pgraph.context_surfaces_2d.dma_image_source, NV2AState),
        VMSTATE_UINT64(pgraph.context_surfaces_2d.dma_image_dest, NV2AState),
        VMSTATE_UINT32(pgraph.context_surfaces_2d.color_format, NV2AState),
        VMSTATE_UINT32(pgraph.context_surfaces_2d.source_pitch, NV2AState),
        VMSTATE_UINT32(pgraph.context_surfaces_2d.dest_pitch, NV2AState),
        VMSTATE_UINT64(pgraph.context_surfaces_2d.source_offset, NV2AState),
        VMSTATE_UINT64(pgraph.context_surfaces_2d.dest_offset, NV2AState),
        VMSTATE_UINT64(pgraph.image_blit.object_instance, NV2AState),
        VMSTATE_UINT64(pgraph.image_blit.context_surfaces, NV2AState),
        VMSTATE_UINT32(pgraph.image_blit.operation, NV2AState),
        VMSTATE_UINT32(pgraph.image_blit.in_x, NV2AState),
        VMSTATE_UINT32(pgraph.image_blit.in_y, NV2AState),
        VMSTATE_UINT32(pgraph.image_blit.out_x, NV2AState),
        VMSTATE_UINT32(pgraph.image_blit.out_y, NV2AState),
        VMSTATE_UINT32(pgraph.image_blit.width, NV2AState),
        VMSTATE_UINT32(pgraph.image_blit.height, NV2AState),
        VMSTATE_UINT64(pgraph.kelvin.object_instance, NV2AState),
        VMSTATE_UINT64(pgraph.dma_color, NV2AState),
        VMSTATE_UINT64(pgraph.dma_zeta, NV2AState),
        VMSTATE_BOOL(pgraph.surface_color.draw_dirty, NV2AState),
        VMSTATE_BOOL(pgraph.surface_zeta.draw_dirty, NV2AState),
        VMSTATE_BOOL(pgraph.surface_color.buffer_dirty, NV2AState),
        VMSTATE_BOOL(pgraph.surface_zeta.buffer_dirty, NV2AState),
        VMSTATE_BOOL(pgraph.surface_color.write_enabled_cache, NV2AState),
        VMSTATE_BOOL(pgraph.surface_zeta.write_enabled_cache, NV2AState),
        VMSTATE_UINT32(pgraph.surface_color.pitch, NV2AState),
        VMSTATE_UINT32(pgraph.surface_zeta.pitch, NV2AState),
        VMSTATE_UINT64(pgraph.surface_color.offset, NV2AState),
        VMSTATE_UINT64(pgraph.surface_zeta.offset, NV2AState),
        VMSTATE_UINT32(pgraph.surface_type, NV2AState),
        VMSTATE_UINT32(pgraph.surface_shape.z_format, NV2AState),
        VMSTATE_UINT32(pgraph.surface_shape.color_format, NV2AState),
        VMSTATE_UINT32(pgraph.surface_shape.zeta_format, NV2AState),
        VMSTATE_UINT32(pgraph.surface_shape.log_width, NV2AState),
        VMSTATE_UINT32(pgraph.surface_shape.log_height, NV2AState),
        VMSTATE_UINT32(pgraph.surface_shape.clip_x, NV2AState),
        VMSTATE_UINT32_V(pgraph.surface_shape.clip_y, NV2AState, 2),
        VMSTATE_UINT32(pgraph.surface_shape.clip_width, NV2AState),
        VMSTATE_UINT32(pgraph.surface_shape.clip_height, NV2AState),
        VMSTATE_UINT32(pgraph.surface_shape.anti_aliasing, NV2AState),
        VMSTATE_UINT32(pgraph.last_surface_shape.z_format, NV2AState),
        VMSTATE_UINT32(pgraph.last_surface_shape.color_format, NV2AState),
        VMSTATE_UINT32(pgraph.last_surface_shape.zeta_format, NV2AState),
        VMSTATE_UINT32(pgraph.last_surface_shape.log_width, NV2AState),
        VMSTATE_UINT32(pgraph.last_surface_shape.log_height, NV2AState),
        VMSTATE_UINT32(pgraph.last_surface_shape.clip_x, NV2AState),
        VMSTATE_UINT32_V(pgraph.last_surface_shape.clip_y, NV2AState, 2),
        VMSTATE_UINT32(pgraph.last_surface_shape.clip_width, NV2AState),
        VMSTATE_UINT32(pgraph.last_surface_shape.clip_height, NV2AState),
        VMSTATE_UINT32(pgraph.last_surface_shape.anti_aliasing, NV2AState),
        VMSTATE_UINT64(pgraph.dma_a, NV2AState),
        VMSTATE_UINT64(pgraph.dma_b, NV2AState),
        VMSTATE_UINT64(pgraph.dma_state, NV2AState),
        VMSTATE_UINT64(pgraph.dma_notifies, NV2AState),
        VMSTATE_UINT64(pgraph.dma_semaphore, NV2AState),
        VMSTATE_UINT64(pgraph.dma_report, NV2AState),
        VMSTATE_UINT64(pgraph.report_offset, NV2AState),
        VMSTATE_UINT64(pgraph.dma_vertex_a, NV2AState),
        VMSTATE_UINT64(pgraph.dma_vertex_b, NV2AState),
        VMSTATE_UINT32(pgraph.primitive_mode, NV2AState),
        VMSTATE_UINT32_ARRAY(pgraph.vertex_state_shader_v0, NV2AState, 4),
        VMSTATE_UINT32_2DARRAY(pgraph.program_data, NV2AState, NV2A_MAX_TRANSFORM_PROGRAM_LENGTH, VSH_TOKEN_SIZE),
        VMSTATE_UINT32_2DARRAY(pgraph.vsh_constants, NV2AState, NV2A_VERTEXSHADER_CONSTANTS, 4),
        VMSTATE_BOOL_ARRAY(pgraph.vsh_constants_dirty, NV2AState, NV2A_VERTEXSHADER_CONSTANTS),
        VMSTATE_UINT32_2DARRAY(pgraph.ltctxa, NV2AState, NV2A_LTCTXA_COUNT, 4),
        VMSTATE_BOOL_ARRAY(pgraph.ltctxa_dirty, NV2AState, NV2A_LTCTXA_COUNT),
        VMSTATE_UINT32_2DARRAY(pgraph.ltctxb, NV2AState, NV2A_LTCTXB_COUNT, 4),
        VMSTATE_BOOL_ARRAY(pgraph.ltctxb_dirty, NV2AState, NV2A_LTCTXB_COUNT),
        VMSTATE_UINT32_2DARRAY(pgraph.ltc1, NV2AState, NV2A_LTC1_COUNT, 4),
        VMSTATE_BOOL_ARRAY(pgraph.ltc1_dirty, NV2AState, NV2A_LTC1_COUNT),
        VMSTATE_STRUCT_ARRAY(pgraph.vertex_attributes, NV2AState, NV2A_VERTEXSHADER_ATTRIBUTES, 1, vmstate_nv2a_pgraph_vertex_attributes, VertexAttribute),
        VMSTATE_UINT32(pgraph.inline_array_length, NV2AState),
        VMSTATE_UINT32_SUB_ARRAY(pgraph.inline_array, NV2AState, 0, NV2A_MAX_BATCH_LENGTH_V2),
        VMSTATE_UINT32_SUB_ARRAY_V(pgraph.inline_array, NV2AState, NV2A_MAX_BATCH_LENGTH_V2, NV2A_MAX_BATCH_LENGTH - NV2A_MAX_BATCH_LENGTH_V2, 3),
        VMSTATE_UINT32(pgraph.inline_elements_length, NV2AState), // fixme
        VMSTATE_UINT32_SUB_ARRAY(pgraph.inline_elements, NV2AState, 0, NV2A_MAX_BATCH_LENGTH_V2),
        VMSTATE_UINT32_SUB_ARRAY_V(pgraph.inline_elements, NV2AState, NV2A_MAX_BATCH_LENGTH_V2, NV2A_MAX_BATCH_LENGTH - NV2A_MAX_BATCH_LENGTH_V2, 3),
        VMSTATE_UINT32(pgraph.inline_buffer_length, NV2AState), // fixme
        VMSTATE_UINT32(pgraph.draw_arrays_length, NV2AState),
        VMSTATE_UINT32(pgraph.draw_arrays_max_count, NV2AState),
        VMSTATE_INT32_ARRAY(pgraph.draw_arrays_start, NV2AState, 1250),
        VMSTATE_INT32_ARRAY(pgraph.draw_arrays_count, NV2AState, 1250),
        VMSTATE_UINT32_ARRAY(pgraph.regs_, NV2AState, 0x2000),
        VMSTATE_UINT32(pmc.pending_interrupts, NV2AState),
        VMSTATE_UINT32(pmc.enabled_interrupts, NV2AState),
        VMSTATE_UINT32(pfifo.pending_interrupts, NV2AState),
        VMSTATE_UINT32(pfifo.enabled_interrupts, NV2AState),
        VMSTATE_UINT32_ARRAY(pfifo.regs, NV2AState, 0x2000),
        VMSTATE_UINT32_ARRAY(pvideo.regs, NV2AState, 0x1000),
        VMSTATE_UINT32(ptimer.pending_interrupts, NV2AState),
        VMSTATE_UINT32(ptimer.enabled_interrupts, NV2AState),
        VMSTATE_UINT32(ptimer.numerator, NV2AState),
        VMSTATE_UINT32(ptimer.denominator, NV2AState),
        VMSTATE_UINT32(ptimer.alarm_time, NV2AState),
        VMSTATE_UINT32_ARRAY(pfb.regs, NV2AState, 0x1000),
        VMSTATE_UINT32(pcrtc.pending_interrupts, NV2AState),
        VMSTATE_UINT32(pcrtc.enabled_interrupts, NV2AState),
        VMSTATE_UINT64(pcrtc.start, NV2AState),
        VMSTATE_UINT32(pramdac.core_clock_coeff, NV2AState),
        VMSTATE_UINT64(pramdac.core_clock_freq, NV2AState),
        VMSTATE_UINT32(pramdac.memory_clock_coeff, NV2AState),
        VMSTATE_UINT32(pramdac.video_clock_coeff, NV2AState),
        VMSTATE_UINT16(puserdac.write_mode_address, NV2AState),
        VMSTATE_UINT8_ARRAY(puserdac.palette, NV2AState, 256*3),
        VMSTATE_BOOL(pgraph.waiting_for_flip, NV2AState),
        VMSTATE_BOOL(pgraph.waiting_for_nop, NV2AState),
        VMSTATE_UNUSED(1),
        VMSTATE_BOOL(pgraph.waiting_for_context_switch, NV2AState),
        VMSTATE_END_OF_LIST()
    },
};

static void nv2a_class_init(ObjectClass *klass, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(klass);
    ResettableClass *rc = RESETTABLE_CLASS(klass);
    PCIDeviceClass *k = PCI_DEVICE_CLASS(klass);

    k->vendor_id = PCI_VENDOR_ID_NVIDIA;
    k->device_id = PCI_DEVICE_ID_NVIDIA_GEFORCE_NV2A;
    k->revision  = 0xA1;
    k->class_id  = PCI_CLASS_DISPLAY_VGA;
    /* When both subsystem ids are set to 0, QEMU sets them to its own
     * default values. However we set them anyway in case upstream decides
     * to change this behavior. */
    k->subsystem_vendor_id = 0;
    k->subsystem_id = 0;
    k->realize   = nv2a_realize;
    k->exit      = nv2a_exitfn;

    rc->phases.hold = nv2a_reset_hold;

    dc->desc = "GeForce NV2A Integrated Graphics";
    dc->vmsd = &vmstate_nv2a;
}

static const TypeInfo nv2a_info = {
    .name          = "nv2a",
    .parent        = TYPE_PCI_DEVICE,
    .instance_size = sizeof(NV2AState),
    .class_init    = nv2a_class_init,
    .interfaces          = (InterfaceInfo[]) {
        { INTERFACE_CONVENTIONAL_PCI_DEVICE },
        { },
    },
};

static void nv2a_register(void)
{
    type_register_static(&nv2a_info);
}
type_init(nv2a_register);

void nv2a_init(PCIBus *bus, int devfn, MemoryRegion *ram)
{
    PCIDevice *dev = pci_create_simple(bus, devfn, "nv2a");
    NV2AState *d = NV2A_DEVICE(dev);
    nv2a_init_memory(d, ram);
    nv2a_init_vga(d);
    qemu_add_vm_change_state_handler(nv2a_vm_state_change, d);
}
