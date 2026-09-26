/* Included at the end of the generated carved.c, so the field list under test
 * and the checks below are one translation unit and the descriptions can stay
 * `static` exactly as they are in aci.c. */

#include "members.c.inc"

/* ---- a QEMUFile that is a byte buffer, and the four VMStateInfos the ACI
 * field list actually names. Defining them here rather than linking QEMU's is
 * deliberate in one useful way: if aci.c grows a field of a type this harness
 * does not implement, the link fails loudly instead of the field going
 * untested. */

struct QEMUFile {
    uint8_t buf[8192];
    size_t len;
    size_t pos;
};

static int f_put(QEMUFile *f, const void *p, size_t n)
{
    assert(f->len + n <= sizeof(f->buf));
    memcpy(f->buf + f->len, p, n);
    f->len += n;
    return 0;
}

static int f_get(QEMUFile *f, void *p, size_t n)
{
    assert(f->pos + n <= f->len);
    memcpy(p, f->buf + f->pos, n);
    f->pos += n;
    return 0;
}

/* Big-endian, as QEMU's stream is, and keyed on the size the FIELD declares.
 * A field whose declared size disagrees with the member's is already a compile
 * error via type_check(); this makes a disagreement between the field's size
 * and its info visible at run time too. */
static int int_put(QEMUFile *f, void *pv, size_t size,
                   const VMStateField *field, JSONWriter *vmdesc)
{
    uint8_t b[8];
    uint64_t v = 0;

    (void)field; (void)vmdesc;
    assert(size >= 1 && size <= 8);
    switch (size) {
    case 1: v = *(uint8_t *)pv; break;
    case 2: v = *(uint16_t *)pv; break;
    case 4: v = *(uint32_t *)pv; break;
    case 8: v = *(uint64_t *)pv; break;
    default: assert(0);
    }
    for (size_t i = 0; i < size; i++) {
        b[i] = (uint8_t)(v >> (8 * (size - 1 - i)));
    }
    return f_put(f, b, size);
}

static int int_get(QEMUFile *f, void *pv, size_t size,
                   const VMStateField *field)
{
    uint8_t b[8];
    uint64_t v = 0;

    (void)field;
    assert(size >= 1 && size <= 8);
    if (f_get(f, b, size) < 0) {
        return -1;
    }
    for (size_t i = 0; i < size; i++) {
        v = (v << 8) | b[i];
    }
    switch (size) {
    case 1: *(uint8_t *)pv = (uint8_t)v; break;
    case 2: *(uint16_t *)pv = (uint16_t)v; break;
    case 4: *(uint32_t *)pv = (uint32_t)v; break;
    case 8: *(uint64_t *)pv = v; break;
    default: assert(0);
    }
    return 0;
}

static int buf_put(QEMUFile *f, void *pv, size_t size,
                   const VMStateField *field, JSONWriter *vmdesc)
{
    (void)field; (void)vmdesc;
    return f_put(f, pv, size);
}

static int buf_get(QEMUFile *f, void *pv, size_t size,
                   const VMStateField *field)
{
    (void)field;
    return f_get(f, pv, size);
}

const VMStateInfo vmstate_info_uint8  = { "uint8",  int_get, int_put };
const VMStateInfo vmstate_info_uint16 = { "uint16", int_get, int_put };
const VMStateInfo vmstate_info_uint32 = { "uint32", int_get, int_put };
const VMStateInfo vmstate_info_buffer = { "buffer", buf_get, buf_put };

/* ---- the stub for the real re-derivation, which also lets the harness check
 * the one thing that is actually wrong in ac97.c's device-level post_load:
 * which pointer the hook is handed. */

static AC97LinkState *post_load_arg;
static int post_load_calls;

void ac97_link_post_load(AC97LinkState *s)
{
    post_load_arg = s;
    post_load_calls++;
}

/* ---- the walker ---- */

enum { OP_SAVE, OP_LOAD, OP_MAP };

typedef struct {
    int op;
    QEMUFile *f;
    uint8_t *cover;     /* OP_MAP: one byte per byte of the walked struct */
    size_t cover_len;
} WalkCtx;

static void walk(const VMStateDescription *vmsd, uint8_t *opaque, size_t rel,
                 WalkCtx *c)
{
    const VMStateField *field = vmsd->fields;
    unsigned handled = VMS_SINGLE | VMS_ARRAY | VMS_STRUCT | VMS_BUFFER;

    for (; field->name; field++) {
        size_t n = (field->flags & VMS_ARRAY) ? (size_t)field->num : 1;

        /* Anything cleverer than a fixed scalar, fixed array, fixed buffer or
         * nested struct is refused rather than silently skipped -- a skipped
         * field would read as covered. */
        assert((field->flags & ~handled) == 0);
        assert(field->field_exists == NULL);

        for (size_t i = 0; i < n; i++) {
            size_t step = (size_t)field->size * i;
            uint8_t *addr = opaque + field->offset + step;
            size_t r = rel + field->offset + step;

            if (field->flags & VMS_STRUCT) {
                walk(field->vmsd, addr, r, c);
                continue;
            }
            switch (c->op) {
            case OP_SAVE:
                assert(field->info->put(c->f, addr, field->size, field,
                                        NULL) == 0);
                break;
            case OP_LOAD:
                assert(field->info->get(c->f, addr, field->size,
                                        field) == 0);
                break;
            case OP_MAP:
                for (size_t b = 0; b < field->size; b++) {
                    if (r + b < c->cover_len) {
                        c->cover[r + b] = 1;
                    }
                }
                break;
            }
        }
    }
    if (c->op == OP_LOAD && vmsd->post_load) {
        assert(vmsd->post_load(opaque, vmsd->version_id) == 0);
    }
}

/* ---- classification of every AC97LinkState member ----
 *
 * GUEST      guest-visible register state; a save/load round trip must
 *            reproduce it byte for byte, so the field list must cover it
 * DERIVED    recomputed on load from GUEST state by ac97_link_post_load
 * TRANSIENT  generator/scratch position, reset on load
 * HOST       a host-side pointer installed by realize; migrating it would be
 *            a bug, not a fix
 *
 * DERIVED, TRANSIENT and HOST must NOT appear in the field list. GUEST must.
 * A member with no row here fails the run: that is the drift gate. */

enum { CLS_GUEST, CLS_DERIVED, CLS_TRANSIENT, CLS_HOST };

static const struct {
    const char *name;
    int cls;
    const char *why;
} link_class[] = {
    { "pci_dev",    CLS_HOST,      "set by mcpx_aci_realize via ac97_common_init" },
    { "as",         CLS_HOST,      "the device's address space, from realize" },
    { "audio_be",   CLS_HOST,      "host audio backend handle, from realize" },
    { "glob_cnt",   CLS_GUEST,     "AC'97 global control, guest-written" },
    { "glob_sta",   CLS_GUEST,     "AC'97 global status, guest-visible" },
    { "cas",        CLS_GUEST,     "codec access semaphore, guest-visible" },
    { "last_samp",  CLS_TRANSIENT, "last sample for the zero-fill generator" },
    { "bm_regs",    CLS_GUEST,     "eight bus-master engines and their BD cache" },
    { "mixer_data", CLS_GUEST,     "the 256-byte AC'97 mixer register page" },
    { "voice_pi",   CLS_DERIVED,   "reopened by reset_voices from the rate regs" },
    { "voice_po",   CLS_DERIVED,   "reopened by reset_voices from the rate regs" },
    { "voice_mc",   CLS_DERIVED,   "reopened by reset_voices from the rate regs" },
    { "invalid_freq", CLS_DERIVED, "set by open_voice from the rate regs" },
    { "silence",    CLS_TRANSIENT, "zero-fill scratch; reset_bm_regs clears it" },
    { "bup_flag",   CLS_TRANSIENT, "zero-fill latch, reset on load" },
};

static const char *cls_name(int c)
{
    switch (c) {
    case CLS_GUEST: return "GUEST";
    case CLS_DERIVED: return "DERIVED";
    case CLS_TRANSIENT: return "TRANSIENT";
    default: return "HOST";
    }
}

static int classify(const char *name, const char **why)
{
    for (size_t i = 0; i < ARRAY_SIZE_LOCAL(link_class); i++) {
        if (!strcmp(link_class[i].name, name)) {
            *why = link_class[i].why;
            return link_class[i].cls;
        }
    }
    return -1;
}

static int failures;

static void fail(const char *fmt, ...)
{
    va_list ap;
    fputs("  FAIL  ", stdout);
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    fputc('\n', stdout);
    failures++;
}

static bool is_zero(const uint8_t *p, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        if (p[i]) {
            return false;
        }
    }
    return true;
}

static void fill_pattern(uint8_t *p, size_t n, uint32_t seed)
{
    for (size_t i = 0; i < n; i++) {
        seed = seed * 1103515245u + 12345u;
        p[i] = (uint8_t)(seed >> 16);
    }
}

/* One arm: fill, save through `vmsd`, wipe to a fresh device, load back, and
 * report per-member whether the bytes returned. */
static void round_trip(const char *label, const VMStateDescription *vmsd,
                       bool expect_ac97)
{
    MCPXACIState *st = calloc(1, sizeof(*st));
    MCPXACIState *ref = calloc(1, sizeof(*ref));
    QEMUFile f = { 0 };
    WalkCtx c;
    size_t guest_bytes = 0, guest_ok = 0;

    printf("\n== arm: %s ==\n", label);

    /* A guest that has been running: EVERY byte of the codec and of PCI
     * config space holds something that is not a reset value -- the pointer
     * members included, deliberately, so that a field list which wrongly
     * migrated one would show up as a non-zero value after a load onto a
     * fresh device. Nothing here is ever dereferenced. */
    fill_pattern((uint8_t *)&st->ac97, sizeof(st->ac97), 0x5eed1234);
    fill_pattern(st->dev.config, sizeof(st->dev.config), 0xc0ffee11);
    memcpy(ref, st, sizeof(*st));

    c = (WalkCtx){ .op = OP_SAVE, .f = &f };
    walk(vmsd, (uint8_t *)st, 0, &c);
    printf("  stream: %zu bytes\n", f.len);

    /* Fresh device: what a load actually lands on. */
    memset(st, 0, sizeof(*st));
    post_load_arg = NULL;
    post_load_calls = 0;

    f.pos = 0;
    c = (WalkCtx){ .op = OP_LOAD, .f = &f };
    walk(vmsd, (uint8_t *)st, 0, &c);
    assert(f.pos == f.len);

    for (size_t i = 0; i < ARRAY_SIZE_LOCAL(link_members); i++) {
        const HarnessMember *m = &link_members[i];
        const char *why = NULL;
        int cls = classify(m->name, &why);
        const uint8_t *got = (const uint8_t *)&st->ac97 + m->offset;
        const uint8_t *want = (const uint8_t *)&ref->ac97 + m->offset;
        bool same = memcmp(got, want, m->size) == 0;

        if (cls < 0) {
            fail("AC97LinkState.%s has no classification in body.c.inc -- "
                 "a member was added to ac97_int.h and nobody decided "
                 "whether it is guest state", m->name);
            continue;
        }
        if (cls == CLS_GUEST) {
            guest_bytes += m->size;
            if (same) {
                guest_ok += m->size;
                printf("  ok    %-12s %3zu B  GUEST      reproduced\n",
                       m->name, m->size);
            } else if (expect_ac97) {
                fail("%-12s %3zu B  GUEST      NOT reproduced", m->name,
                     m->size);
            } else {
                printf("  --    %-12s %3zu B  GUEST      lost (expected on "
                       "this arm)\n", m->name, m->size);
            }
        } else if (!is_zero(got, m->size)) {
            /* A fresh device is all zero here, so anything else can only have
             * come out of the stream. */
            fail("%-12s %3zu B  %-9s came back from the stream, but it is %s",
                 m->name, m->size, cls_name(cls), why);
        } else {
            printf("  ok    %-12s %3zu B  %-9s left at the fresh-device value "
                   "(%s)\n", m->name, m->size, cls_name(cls), why);
        }
    }

    bool cfg_ok = memcmp(st->dev.config, ref->dev.config,
                         sizeof(ref->dev.config)) == 0;
    printf("  %s PCI config space (256 B) %s\n", cfg_ok ? "ok   " : "FAIL ",
           cfg_ok ? "reproduced" : "NOT reproduced");
    if (!cfg_ok) {
        failures++;
    }

    printf("  guest state reproduced: %zu of %zu bytes\n", guest_ok,
           guest_bytes);
    if (expect_ac97) {
        if (guest_ok != guest_bytes) {
            fail("this arm must reproduce all guest state");
        }
        if (post_load_calls != 1) {
            fail("ac97_link_post_load ran %d times, expected exactly 1",
                 post_load_calls);
        } else if (post_load_arg != &st->ac97) {
            fail("post_load got %p, expected &state->ac97 (%p) -- the nested "
                 "VMSTATE_STRUCT opaque is wrong",
                 (void *)post_load_arg, (void *)&st->ac97);
        } else {
            printf("  ok    post_load ran once, with &state->ac97\n");
        }
    } else if (guest_ok != 0) {
        fail("the PCI-only arm recovered %zu bytes of codec state; it should "
             "recover none, and if it does this harness cannot tell a fix "
             "from a no-op", guest_ok);
    }

    free(st);
    free(ref);
}

/* The pre-fix field list, kept so the harness has an arm it is REQUIRED to
 * report as losing everything. A check that can only pass is not a check. */
static const VMStateDescription vmstate_mcpx_aci_pci_only = {
    .name = "mcpx-aci",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (const VMStateField[]) {
        VMSTATE_PCI_DEVICE(dev, MCPXACIState),
        VMSTATE_END_OF_LIST()
    },
};

static void coverage_report(void)
{
    static uint8_t cover[sizeof(AC97LinkState)];
    static uint8_t dummy[sizeof(AC97LinkState)];
    WalkCtx c = { .op = OP_MAP, .cover = cover, .cover_len = sizeof(cover) };
    size_t covered = 0;

    printf("\n== byte coverage of AC97LinkState by the ACI field list ==\n");
    walk(&vmstate_mcpx_aci_ac97, dummy, 0, &c);

    for (size_t i = 0; i < ARRAY_SIZE_LOCAL(link_members); i++) {
        const HarnessMember *m = &link_members[i];
        const char *why = NULL;
        int cls = classify(m->name, &why);
        size_t n = 0;

        for (size_t b = 0; b < m->size; b++) {
            n += cover[m->offset + b];
        }
        covered += n;
        if (cls == CLS_GUEST && n != m->size) {
            fail("%-12s GUEST: %zu of %zu bytes in the field list", m->name,
                 n, m->size);
        } else if (cls >= 0 && cls != CLS_GUEST && n != 0) {
            fail("%-12s %s: %zu bytes are in the field list and should not be",
                 m->name, cls_name(cls), n);
        } else {
            printf("  ok    %-12s %-9s %3zu of %3zu bytes in the list\n",
                   m->name, cls_name(cls), n, m->size);
        }
    }
    printf("  %zu of %zu struct bytes covered (the rest is padding, host "
           "pointers and derived state)\n", covered, sizeof(AC97LinkState));
}

int main(void)
{
    printf("aci-vmstate: %zu AC97LinkState members, %zu AC97BusMasterRegs "
           "members, sizeof(AC97LinkState) = %zu\n",
           ARRAY_SIZE_LOCAL(link_members), ARRAY_SIZE_LOCAL(bm_members),
           sizeof(AC97LinkState));

    coverage_report();
    round_trip("hw/xbox/mcpx/aci.c as it stands", aci_vmsd, true);
    round_trip("PCI-only, the pre-fix field list (control)",
               &vmstate_mcpx_aci_pci_only, false);

    printf("\n%s: %d failure(s)\n", failures ? "FAILED" : "PASSED", failures);
    return failures ? 1 : 0;
}
