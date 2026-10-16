/*
 * Run a title's own GP and EP DSP programs, restored from a save state,
 * on mixbin input of our choosing -- the use_dsp = true path, offline.
 *
 *   dsp_harness DIR --in SRC.s16le --frames N [--route BIN:CH:GAIN_DB ...]
 *               [--out OUTPREFIX] [--no-ep]
 *
 * DIR holds what hxs_dsp_export.py writes (gp_core.bin, ep_core.bin,
 * gp_regs.bin, ep_regs.bin, apu_regs.bin, ram.bin). SRC is stereo s16le at
 * 48 kHz; each --route adds channel CH (0 = L, 1 = R) of SRC, times
 * 10^(GAIN_DB/20), into mixbin BIN, the way voice_process() in vp.c fills
 * mixbins (headroom and volume are the caller's to fold into GAIN_DB). Each
 * 32-sample frame is written to GP X:0x1400 + 32 * bin with float_to_24b,
 * the GP is run to idle (gp_ep.c mcpx_apu_dsp_frame with realtime = true),
 * and every eighth frame the EP is too.
 *
 * Writes OUTPREFIX.gp.s16le (X:0x1400 and X:0x1420 >> 8 after each GP
 * frame: the MON_GP tap), OUTPREFIX.ep0.s16le (what the EP writes to its
 * output FIFO 0: the MON_EP tap, i.e. the AC97 stream), and OUTPREFIX.fifo
 * .log (one line per FIFO DMA: unit, dir, index, bytes). Builds against the
 * emulator's own hw/xbox/mcpx/apu/dsp/{dsp,dsp_cpu,dsp_dma}.c with the
 * stand-in headers in dspstub/.
 */
#include "qemu/osdep.h"
#include "dsp.h"
#include "dsp_cpu.h"
#include "dsp_dma.h"
#include "dsp_state.h"

#define PAGE 4096
#define FRAME 32
#define NBINS 32

/* apu_regs.h */
#define GPSADDR 0x2040
#define GPFADDR 0x2044
#define EPSADDR 0x2048
#define EPFADDR 0x204C
#define GPSMAXSGE 0x20D4
#define GPFMAXSGE 0x20D8
#define EPSMAXSGE 0x20DC
#define EPFMAXSGE 0x20E0
#define GPOFBASE0 0x3024
#define GPIFBASE0 0x3064
#define EPOFBASE0 0x4024
#define EPIFBASE0 0x4064
#define RST 0xFFFC

static uint32_t *apu_regs, *gp_regs, *ep_regs;
static uint8_t *ram;
static size_t ram_size;
static FILE *fifo_log, *ep0_out;
static int frame_no;

static void *slurp(const char *dir, const char *name, size_t *len)
{
    char path[4096];
    snprintf(path, sizeof(path), "%s%s%s", dir, *dir ? "/" : "", name);
    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        exit(1);
    }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    void *p = malloc(n);
    if (fread(p, 1, n, f) != (size_t)n) {
        perror(path);
        exit(1);
    }
    fclose(f);
    if (len) {
        *len = n;
    }
    return p;
}

static void sg_rw(uint32_t sge_base, unsigned max_sge, uint8_t *ptr,
                  uint32_t addr, size_t len, bool dir)
{
    unsigned entry = addr / PAGE;
    unsigned off = addr % PAGE;
    size_t chunk = PAGE - off;
    while (len > 0) {
        if (entry > max_sge) {
            fprintf(stderr, "sge entry %u > max %u\n", entry, max_sge);
            exit(2);
        }
        uint32_t prd = ldl_le_p(&ram[sge_base + entry * 8]);
        size_t paddr = (size_t)prd + off;
        if (chunk > len) {
            chunk = len;
        }
        if (paddr + chunk >= ram_size) {
            fprintf(stderr, "sge paddr %zx out of RAM\n", paddr);
            exit(2);
        }
        if (dir) {
            memcpy(&ram[paddr], ptr, chunk);
        } else {
            memcpy(ptr, &ram[paddr], chunk);
        }
        ptr += chunk;
        len -= chunk;
        entry++;
        chunk = PAGE;
        off = 0;
    }
}

static uint32_t circ_rw(uint32_t sge, unsigned max, uint8_t *ptr,
                        uint32_t base, uint32_t end, uint32_t cur,
                        size_t len, bool dir)
{
    while (len > 0) {
        size_t n = end - cur;
        if (n > len) {
            n = len;
        }
        sg_rw(sge, max, ptr, cur, n, dir);
        ptr += n;
        len -= n;
        cur += n;
        if (cur >= end) {
            cur = base;
        }
    }
    return cur;
}

static void gp_scratch(void *o, uint8_t *ptr, uint32_t addr, size_t len,
                       bool dir)
{
    sg_rw(apu_regs[GPSADDR], apu_regs[GPSMAXSGE], ptr, addr, len, dir);
}

static void ep_scratch(void *o, uint8_t *ptr, uint32_t addr, size_t len,
                       bool dir)
{
    sg_rw(apu_regs[EPSADDR], apu_regs[EPSMAXSGE], ptr, addr, len, dir);
}

static void fifo(const char *unit, uint32_t fbase, uint32_t sge,
                 unsigned max, uint8_t *ptr, unsigned index, size_t len,
                 bool dir)
{
    uint32_t r = (dir ? fbase : fbase + 0x40) + 0x10 * index;
    uint32_t base = apu_regs[r] & 0xFFFFFF;
    uint32_t end = apu_regs[r + 4] & 0xFFFFFF;
    uint32_t cur = apu_regs[r + 8] & 0xFFFFFF;
    fprintf(fifo_log, "%d %s %s %u %zu base %x end %x cur %x\n", frame_no,
            unit, dir ? "out" : "in", index, len, base, end, cur);
    if (end <= base) {
        return;
    }
    if (cur >= end) {
        cur = cur % (end - base);
    }
    if (cur < base) {
        cur = base;
    }
    cur = circ_rw(sge, max, ptr, base, end, cur, len, dir);
    apu_regs[r + 8] = (apu_regs[r + 8] & ~0xFFFFFFu) | cur;
}

static void gp_fifo(void *o, uint8_t *ptr, unsigned index, size_t len,
                    bool dir)
{
    fifo("gp", GPOFBASE0, apu_regs[GPFADDR], apu_regs[GPFMAXSGE], ptr, index,
         len, dir);
}

static void ep_fifo(void *o, uint8_t *ptr, unsigned index, size_t len,
                    bool dir)
{
    if (dir && index == 0) {
        fwrite(ptr, 1, len, ep0_out);
    }
    fifo("ep", EPOFBASE0, apu_regs[EPFADDR], apu_regs[EPFMAXSGE], ptr, index,
         len, dir);
}

static DSPState *restore(const char *dir, const char *name,
                         dsp_scratch_rw_func s, dsp_fifo_rw_func f, bool gp)
{
    size_t n;
    uint32_t *w = slurp(dir, name, &n);
    if (n != 11533 * 4) {
        fprintf(stderr, "%s: %zu bytes, want %d\n", name, n, 11533 * 4);
        exit(1);
    }
    DSPState *d = dsp_init(NULL, s, f);
    dsp_core_t *c = &d->core;
    uint32_t *p = w;
    c->pc = *p++;
    memcpy(c->registers, p, sizeof(c->registers)); p += 64;
    memcpy(c->stack, p, sizeof(c->stack)); p += 32;
    memcpy(c->xram, p, sizeof(c->xram)); p += 4096;
    memcpy(c->yram, p, sizeof(c->yram)); p += 2048;
    memcpy(c->pram, p, sizeof(c->pram)); p += 4096;
    memcpy(c->mixbuffer, p, sizeof(c->mixbuffer)); p += 1024;
    memcpy(c->periph, p, sizeof(c->periph)); p += 128;
    c->loop_rep = *p++;
    c->pc_on_rep = *p++;
    c->instr_cycle = *p++;
    c->interrupt_state = *p++;
    c->interrupt_instr_fetch = *p++;
    c->interrupt_save_pc = *p++;
    c->interrupt_counter = *p++;
    c->interrupt_ipl_to_raise = *p++;
    c->interrupt_pipeline_count = *p++;
    for (int i = 0; i < 12; i++) {
        c->interrupt_ipl[i] = (int16_t)*p++;
    }
    for (int i = 0; i < 12; i++) {
        c->interrupt_is_pending[i] = *p++;
    }
    c->num_inst = *p++;
    c->cur_inst_len = *p++;
    c->cur_inst = *p++;
    d->dma.configuration = *p++;
    d->dma.control = *p++;
    d->dma.start_block = *p++;
    d->dma.next_block = *p++;
    d->dma.error = *p++;
    d->dma.eol = *p++;
    d->save_cycles = (int32_t)*p++;
    d->interrupts = *p++;
    memset(c->pram_opcache, 0, sizeof(c->pram_opcache));
    d->is_gp = gp;
    c->is_gp = gp;
    free(w);
    return d;
}

static uint32_t to24(float v)
{
    double s = v * (8.0 * 0x100000);
    int i;
    if (s >= 1.0 * 0x7fffff) {
        i = 0x7fffff;
    } else if (s <= -8.0 * 0x100000) {
        i = -1 - 0x7fffff;
    } else {
        i = (int)lrint(s);
    }
    return (uint32_t)i & 0xffffff;
}

static uint64_t run_to_idle(DSPState *d, uint64_t cap)
{
    dsp_start_frame(d);
    d->core.is_idle = false;
    d->core.cycle_count = 0;
    uint64_t total = 0;
    do {
        dsp_run(d, 1000);
        total += 1000;
    } while (!d->core.is_idle && total < cap);
    return d->core.cycle_count;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: see the header comment\n");
        return 1;
    }
    const char *dir = argv[1];
    const char *in = NULL, *out = "harness";
    int frames = 256;
    bool run_ep = true;
    int nroute = 0;
    int r_bin[64], r_ch[64];
    float r_gain[64];
    for (int i = 2; i < argc; i++) {
        if (!strcmp(argv[i], "--in")) {
            in = argv[++i];
        } else if (!strcmp(argv[i], "--frames")) {
            frames = atoi(argv[++i]);
        } else if (!strcmp(argv[i], "--out")) {
            out = argv[++i];
        } else if (!strcmp(argv[i], "--no-ep")) {
            run_ep = false;
        } else if (!strcmp(argv[i], "--route")) {
            double g;
            if (sscanf(argv[++i], "%d:%d:%lf", &r_bin[nroute], &r_ch[nroute],
                       &g) != 3) {
                fprintf(stderr, "bad --route %s\n", argv[i]);
                return 1;
            }
            r_gain[nroute++] = pow(10.0, g / 20.0);
        }
    }
    apu_regs = slurp(dir, "apu_regs.bin", NULL);
    gp_regs = slurp(dir, "gp_regs.bin", NULL);
    ep_regs = slurp(dir, "ep_regs.bin", NULL);
    ram = slurp(dir, "ram.bin", &ram_size);
    DSPState *gp = restore(dir, "gp_core.bin", gp_scratch, gp_fifo, true);
    DSPState *ep = restore(dir, "ep_core.bin", ep_scratch, ep_fifo, false);
    bool gp_on = (gp_regs[RST] & 3) == 3;
    bool ep_on = (ep_regs[RST] & 3) == 3 && run_ep;

    size_t src_len = 0;
    int16_t *src = in ? slurp("", in, &src_len) : NULL;
    size_t src_frames = src_len / 4;

    char path[4096];
    snprintf(path, sizeof(path), "%s.fifo.log", out);
    fifo_log = fopen(path, "w");
    snprintf(path, sizeof(path), "%s.ep0.s16le", out);
    ep0_out = fopen(path, "wb");
    snprintf(path, sizeof(path), "%s.gp.s16le", out);
    FILE *gp_out = fopen(path, "wb");

    static float mix[NBINS][FRAME];
    uint64_t gp_cyc_max = 0, ep_cyc_max = 0, gp_unfinished = 0;
    for (frame_no = 0; frame_no < frames; frame_no++) {
        memset(mix, 0, sizeof(mix));
        for (int i = 0; i < FRAME; i++) {
            size_t s = (size_t)frame_no * FRAME + i;
            if (s >= src_frames) {
                break;
            }
            for (int r = 0; r < nroute; r++) {
                mix[r_bin[r]][i] += r_gain[r] * src[2 * s + r_ch[r]] / 32768.0f;
            }
        }
        for (int b = 0; b < NBINS; b++) {
            for (int i = 0; i < FRAME; i++) {
                dsp_write_memory(gp, 'X', 0x1400 + b * FRAME + i,
                                 to24(mix[b][i]));
            }
        }
        if (gp_on) {
            uint64_t c = run_to_idle(gp, 50000000);
            if (!gp->core.is_idle) {
                gp_unfinished++;
            }
            gp_cyc_max = c > gp_cyc_max ? c : gp_cyc_max;
            int16_t o[FRAME][2];
            for (int i = 0; i < FRAME; i++) {
                o[i][0] = dsp_read_memory(gp, 'X', 0x1400 + i) >> 8;
                o[i][1] = dsp_read_memory(gp, 'X', 0x1420 + i) >> 8;
            }
            fwrite(o, sizeof(o), 1, gp_out);
        }
        if (ep_on && frame_no % 8 == 0) {
            uint64_t c = run_to_idle(ep, 50000000);
            ep_cyc_max = c > ep_cyc_max ? c : ep_cyc_max;
        }
    }
    fclose(gp_out);
    fclose(ep0_out);
    fclose(fifo_log);
    printf("frames %d gp %s ep %s; gp max %llu instr/frame (%llu frames "
           "never idle), ep max %llu\n", frames, gp_on ? "on" : "off",
           ep_on ? "on" : "off", (unsigned long long)gp_cyc_max,
           (unsigned long long)gp_unfinished,
           (unsigned long long)ep_cyc_max);
    return 0;
}
