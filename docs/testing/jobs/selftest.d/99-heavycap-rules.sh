# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, ok/bad/check. Not executable, no shebang, no exit. Reads no other
# fragment's leftovers.
#
# heavycap1022 (#433): the rules that decide when a slow or heavy guest frame
# is logged (`hakuX-heavy` blocks) and when a heavy stretch saves a state by
# itself (HAKUX_HEAVYSAVE=1). They are pure functions in
# hw/xbox/nv2a/heavyrule.h, so this builds them on the host and pins:
#
#   1. the trigger: over 50 ms, over 1000 draws, a host main pass over 33 ms;
#      at the bar is quiet;
#   2. the block rate limit: one block per 10 s and never while one is still
#      collecting, so 600 s of 33 ms heavy frames print at most 61 blocks;
#   3. the save: 1 s of consecutive heavy flips (counted from the start of the
#      first heavy frame, ended by any flip at or under the bar), or three
#      frames over 50 ms whose ends fall within 2 s; at most one per 60 s;
#   4. where it goes: four heavy slots past hxs.h's HXS_SLOT_COUNT (so never
#      slots 0-9, never auto), the first empty one or else the oldest.
#
# Then each rule is put back to its plausible weaker form in a copy of the
# header (text replacement; the old text must occur exactly once) and the case
# for that rule must fail. A mutant that does not build, or does not run to
# its summary, counts as NOT caught.
#
# Two call-site rules are checked in profile.c and hxs.c the same way: a frame
# that holds a heavy save's pause fires no trigger and feeds no save rule (the
# capture never triggers on itself), and hxs.c's heavy slots are heavyrule.h's.
# Last, the tag profile.c logs under must be in the dispatcher's LOGCAT_SPEC
# at I or below, or a soak's logcat holds none of it.

echo "== heavycap1022: hw/xbox/nv2a/heavyrule.h trigger, rate limit, save and slot rules"
HC="$T/heavycap"
mkdir -p "$HC"
HC_HDR="$REPO/hw/xbox/nv2a/heavyrule.h"
HC_HXS_H="$REPO/android/app/src/main/cpp/savestate/hxs.h"
HC_HXS_C="$REPO/android/app/src/main/cpp/savestate/hxs.c"
HC_PROF="$REPO/hw/xbox/nv2a/pgraph/profile.c"
HC_COUNT=$(sed -n 's/^#define HXS_SLOT_COUNT \([0-9][0-9]*\)$/\1/p' "$HC_HXS_H")
HC_AUTO=$(sed -n 's/^#define HXS_SLOT_AUTO \([0-9][0-9]*\)$/\1/p' "$HC_HXS_H")
check "hxs.h names HXS_SLOT_COUNT and HXS_SLOT_AUTO (read, not assumed)" \
    test -n "$HC_COUNT" -a -n "$HC_AUTO"

cat > "$HC/heavyrule_test.c" <<'C'
#include <stdio.h>
#include <string.h>
#include <heavyrule.h>

#define MS 1000000LL
#define SEC 1000000000LL

static int cases, fails;

static void report(const char *name, int ok, const char *detail)
{
    printf("%s %s %s\n", ok ? "ok" : "FAIL", name, detail);
    cases++;
    fails += !ok;
}

/* ---- the trigger ---- */

static void trig_cases(void)
{
    char d[160];
    unsigned a = hc_trigger(50 * MS, 1000, 33 * MS, 1000);
    snprintf(d, sizeof(d), "50 ms, 1000 draws, 33 ms main pass -> %u", a);
    report("trig.at_bar_quiet", a == 0, d);

    unsigned s = hc_trigger(50001 * 1000LL, 0, 0, 1000);   /* profile.c: us */
    unsigned w = hc_trigger(16 * MS, 1001, 0, 1000);
    unsigned all = hc_trigger(50 * MS + 1, 1001, 33 * MS + 1, 1000);
    snprintf(d, sizeof(d), "50.001 ms -> %u, 1001 draws -> %u, all -> %u", s, w,
             all);
    report("trig.over_bar_fires", s == HC_TRIG_SLOW && w == HC_TRIG_DRAWS &&
           all == (HC_TRIG_SLOW | HC_TRIG_DRAWS | HC_TRIG_GPU), d);

    unsigned g = hc_trigger(16 * MS, 100, 33 * MS + 1, 1000);
    snprintf(d, sizeof(d), "16 ms frame, 100 draws, 33.000001 ms pass -> %u", g);
    report("trig.gpu_over_33ms_fires", g == HC_TRIG_GPU, d);

    unsigned o = hc_trigger(16 * MS, 501, 0, 500);
    snprintf(d, sizeof(d), "draws bar 500 (HAKUX_HEAVYCAP_DRAWS), 501 -> %u", o);
    report("trig.draws_bar_is_the_argument", o == HC_TRIG_DRAWS, d);
}

/* ---- the block rate limit ---- */

/* profile.c: after the admitting flip the block collects HC_POST records,
 * then prints 1 + HC_PRE + 1 + HC_POST lines, HC_LINES (4) per flip. */
#define BUSY_FLIPS (HC_POST + (1 + HC_PRE + 1 + HC_POST + 3) / 4)

static unsigned sim_blocks(int64_t frame_ns, int64_t span_ns, unsigned *fires,
                           unsigned *sup_seen, unsigned *sup_left)
{
    HcBlockRule br;
    unsigned blocks = 0;
    int busy = 0;

    memset(&br, 0, sizeof(br));
    *fires = *sup_seen = 0;
    for (int64_t now = frame_ns; now <= span_ns; now += frame_ns) {
        unsigned t = hc_trigger(frame_ns, 1500, 0, HC_DRAWS_DEFAULT);
        int inprog = busy > 0;
        uint32_t sup = 0;

        if (busy) {
            busy--;
        }
        if (!t) {
            continue;
        }
        (*fires)++;
        if (hc_block_admit(&br, now, inprog, &sup)) {
            blocks++;
            *sup_seen += sup;
            busy = BUSY_FLIPS;
        }
    }
    *sup_left = br.suppressed;
    return blocks;
}

static void block_cases(void)
{
    char d[200];
    unsigned fires, sup_seen, sup_left;
    unsigned b = sim_blocks(33 * MS, 600 * SEC, &fires, &sup_seen, &sup_left);
    snprintf(d, sizeof(d), "600 s of 33 ms heavy frames: %u blocks, %u fires, "
             "%u + %u refused", b, fires, sup_seen, sup_left);
    /* at most one per 10 s, and not fewer: a rule that never re-admits is
     * as wrong as one that floods */
    report("block.rate_600s_of_33ms", b >= 59 && b <= 61 &&
           sup_seen + sup_left == fires - b, d);

    HcBlockRule br;
    uint32_t sup = 99;
    memset(&br, 0, sizeof(br));
    int a0 = hc_block_admit(&br, 0, false, &sup);
    int a1 = hc_block_admit(&br, 10 * SEC - 1, false, &sup);
    int a2 = hc_block_admit(&br, 10 * SEC, false, &sup);
    snprintf(d, sizeof(d), "admit at 0, 9.999999999 s, 10 s -> %d %d %d, "
             "sup on the third %u", a0, a1, a2, sup);
    report("block.gap_10s", a0 && !a1 && a2 && sup == 1, d);

    memset(&br, 0, sizeof(br));
    a0 = hc_block_admit(&br, 0, false, &sup);
    a1 = hc_block_admit(&br, 11 * SEC, true, &sup);
    b = sim_blocks(1 * SEC, 120 * SEC, &fires, &sup_seen, &sup_left);
    snprintf(d, sizeof(d), "fire at 11 s while collecting -> %d; 120 s of 1 s "
             "frames -> %u blocks (busy %d flips)", a1, b, BUSY_FLIPS);
    report("block.not_while_collecting", a0 && !a1 && b <= 3, d);
}

/* ---- the save ---- */

/* 10 ms frames with 100 draws, except a 60 ms frame ending at each slow end.
 * Returns the saves fired up to end_ms; the first one's time and reasons. */
static unsigned sim_slow(const int *slow_end_ms, int nslow, int end_ms,
                         int *first_ms, unsigned *why)
{
    HcSaveRule r;
    unsigned n = 0;

    memset(&r, 0, sizeof(r));
    *first_ms = -1;
    *why = 0;
    for (int t = 10; t <= end_ms; t += 10) {
        int slow = 0;
        for (int k = 0; k < nslow; k++) {
            slow |= slow_end_ms[k] == t;
        }
        unsigned w = hc_save_check(&r, t * MS, slow ? 60 * MS : 10 * MS, 100,
                                   HC_DRAWS_DEFAULT);
        if (w) {
            if (!n) {
                *first_ms = t;
                *why = w;
            }
            n++;
        }
    }
    return n;
}

/* 25 ms frames (under the 50 ms bar, so only the draws rule can fire) ending
 * at 25 ms, 50 ms, ..., each with 1500 draws except the flip ending at
 * light_ms, which has exactly the bar (1000). Returns the saves up to end_ms
 * and their times. */
static unsigned sim_draws(int light_ms, int end_ms, int *at_ms, int max_at,
                          unsigned *why0, uint32_t *refused)
{
    HcSaveRule r;
    unsigned n = 0;

    memset(&r, 0, sizeof(r));
    *why0 = 0;
    for (int t = 25; t <= end_ms; t += 25) {
        uint32_t dr = t == light_ms ? 1000 : 1500;
        unsigned w = hc_save_check(&r, t * MS, 25 * MS, dr, HC_DRAWS_DEFAULT);
        if (w) {
            if (!n) {
                *why0 = w;
            }
            if ((int)n < max_at) {
                at_ms[n] = t;
            }
            n++;
        }
    }
    *refused = r.refused;
    return n;
}

static void save_cases(void)
{
    char d[200];
    int first;
    unsigned why, n;

    static const int in2[] = { 1000, 1500, 2900 };
    n = sim_slow(in2, 3, 5000, &first, &why);
    snprintf(d, sizeof(d), "slow ends 1.0 1.5 2.9 s -> %u saves, first at %d "
             "ms why %u", n, first, why);
    report("save.slow_three_within_2s", n == 1 && first == 2900 &&
           why == HC_SAVE_SLOW, d);

    static const int over[] = { 1000, 1500, 3600 };
    n = sim_slow(over, 3, 5000, &first, &why);
    snprintf(d, sizeof(d), "slow ends 1.0 1.5 3.6 s -> %u saves (first %d ms)",
             n, first);
    report("save.slow_three_over_2_6s_quiet", n == 0, d);

    static const int two[] = { 1000, 1500 };
    n = sim_slow(two, 2, 5000, &first, &why);
    snprintf(d, sizeof(d), "slow ends 1.0 1.5 s -> %u saves (first %d ms)", n,
             first);
    report("save.slow_two_frames_quiet", n == 0, d);

    int at[8];
    uint32_t refused;
    n = sim_draws(-1, 1000, at, 8, &why, &refused);
    snprintf(d, sizeof(d), "25 ms frames over the bar from 0 s -> %u saves by "
             "1.0 s, first at %d ms why %u", n, n ? at[0] : -1, why);
    report("save.draws_run_1s", n == 1 && at[0] == 1000 &&
           why == HC_SAVE_DRAWS, d);

    /* heavy to 0.6 s, one flip at the bar (not over it) ending at 0.625 s,
     * then heavy again: the run restarts at the start of the 0.65 s frame
     * (0.625 s) and saves at 1.625 s */
    n = sim_draws(625, 1625, at, 8, &why, &refused);
    snprintf(d, sizeof(d), "heavy to 0.6 s, a flip at the bar at 0.625 s, heavy "
             "-> %u saves, first at %d ms", n, n ? at[0] : -1);
    report("save.light_flip_ends_run", n == 1 && at[0] == 1625, d);

    n = sim_draws(-1, 125000, at, 8, &why, &refused);
    snprintf(d, sizeof(d), "125 s of heavy 25 ms frames -> %u saves at %d %d "
             "%d ms, %u refused", n, n > 0 ? at[0] : -1, n > 1 ? at[1] : -1,
             n > 2 ? at[2] : -1, refused);
    report("save.one_per_60s", n == 3 && at[0] == 1000 && at[1] == 61000 &&
           at[2] == 121000 && refused > 0, d);
}

/* ---- the slot ---- */

static void slot_cases(void)
{
    char d[200];
    bool some[HC_KEEP] = { true, false, true, false };
    int64_t t0[HC_KEEP] = { 5, 0, 7, 0 };
    int p = hc_pick_slot(some, t0);
    snprintf(d, sizeof(d), "present 1 0 1 0 -> %d", p);
    report("slot.first_empty", p == 1, d);

    bool full[HC_KEEP] = { true, true, true, true };
    int64_t ta[HC_KEEP] = { 300, 100, 400, 200 };
    int64_t tb[HC_KEEP] = { 100, 300, 400, 200 };
    int pa = hc_pick_slot(full, ta), pb = hc_pick_slot(full, tb);
    snprintf(d, sizeof(d), "full, saved 300 100 400 200 -> %d; 100 300 400 200 "
             "-> %d", pa, pb);
    report("slot.oldest_when_full", pa == 1 && pb == 0, d);

    int ok = HC_KEEP == 4;
    for (int k = 0; k < HC_KEEP; k++) {
        int s = hc_slot_of(k);
        ok &= s >= HXS_SLOT_COUNT_H && s != HXS_SLOT_AUTO_H &&
              (k == 0 || s == hc_slot_of(k - 1) + 1);
    }
    snprintf(d, sizeof(d), "slots %d..%d, keep %d; hxs.h: count %d, auto %d",
             hc_slot_of(0), hc_slot_of(HC_KEEP - 1), HC_KEEP, HXS_SLOT_COUNT_H,
             HXS_SLOT_AUTO_H);
    report("slot.outside_owner_slots", ok, d);
}

int main(void)
{
    trig_cases();
    block_cases();
    save_cases();
    slot_cases();
    printf("summary cases=%d fails=%d\n", cases, fails);
    return fails ? 1 : 0;
}
C

hc_build() {   # <dir> [-Werror]: build the test against <dir>/heavyrule.h
    cc -std=gnu11 -O1 -Wall -Wextra ${2:-} -I"$1" \
        -DHXS_SLOT_COUNT_H="${HC_COUNT:-0}" -DHXS_SLOT_AUTO_H="${HC_AUTO:-0}" \
        "$HC/heavyrule_test.c" -o "$1/test" > "$1/cc.log" 2>&1
}
mkdir -p "$HC/real"
cp "$HC_HDR" "$HC/real/heavyrule.h"
hc_build "$HC/real" -Werror
check "heavyrule_test builds against heavyrule.h with -Wall -Wextra -Werror" test -x "$HC/real/test"
hc_run() { "$HC/$1/test" > "$HC/$1/run.log" 2>&1; }
check "every trigger, rate-limit, save and slot case passes on the real header" hc_run real
if [ -s "$HC/real/run.log" ]; then sed 's/^/       /' "$HC/real/run.log"; fi

# ------------------------------------------------------------ falsifications
# name | old text (exactly once in heavyrule.h) | new text | case that must FAIL
cat > "$HC/mutate.py" <<'PY'
import os, sys
src, out = sys.argv[1], sys.argv[2]
M = [
 ("ge", "at the bar fires too",
  "#define HC_OVER(v, bar) ((v) > (bar))", "#define HC_OVER(v, bar) ((v) >= (bar))",
  "trig.at_bar_quiet"),
 ("nogpu", "no host main-pass bar",
  "    if (HC_OVER(gpu_ns, HC_GPU_SLOW_NS)) {\n        t |= HC_TRIG_GPU;\n    }\n", "",
  "trig.gpu_over_33ms_fires"),
 ("nogap", "no 10 s block gap (only the in-progress refusal)",
  "#define HC_BLOCK_GAP_NS 10000000000LL", "#define HC_BLOCK_GAP_NS 0LL",
  "block.rate_600s_of_33ms"),
 ("overlap", "a block may start while one is still collecting (only the gap)",
  "    if (in_progress) {\n        r->suppressed++;\n        return false;\n    }\n", "",
  "block.not_while_collecting"),
 ("slow2", "two slow frames save",
  "#define HC_SLOW_N 3", "#define HC_SLOW_N 2",
  "save.slow_two_frames_quiet"),
 ("nowin", "three slow frames at any spacing save",
  "now - r->slow_t[r->slow_n % HC_SLOW_N] <= HC_SLOW_WIN_NS", "1",
  "save.slow_three_over_2_6s_quiet"),
 ("nosavegap", "no 60 s save gap",
  "#define HC_SAVE_GAP_NS 60000000000LL", "#define HC_SAVE_GAP_NS 0LL",
  "save.one_per_60s"),
 ("noreset", "a flip at or under the bar does not end the run",
  "    } else {\n        r->in_run = false;\n    }\n", "    }\n",
  "save.light_flip_ends_run"),
 ("runend", "the run counts from the first heavy flip, not its frame's start",
  "r->run_t0 = now - (frame_ns > 0 ? frame_ns : 0);", "r->run_t0 = now;",
  "save.draws_run_1s"),
 ("base10", "heavy slots right after the ten public slots",
  "#define HC_SLOT_BASE 12", "#define HC_SLOT_BASE 10",
  "slot.outside_owner_slots"),
 ("newest", "the full ring overwrites the newest state",
  "if (saved_at[k] < saved_at[pick]) {", "if (saved_at[k] > saved_at[pick]) {",
  "slot.oldest_when_full"),
]
s = open(src).read()
for key, what, old, new, case in M:
    d = os.path.join(out, key)
    os.makedirs(d, exist_ok=True)
    n = s.count(old)
    open(os.path.join(d, "heavyrule.h"), "w").write(s.replace(old, new) if n == 1 else s)
    open(os.path.join(d, "meta"), "w").write("%d\t%s\t%s\n" % (n, case, what))
    print(key)
PY
HC_MUTS=$(python3 "$HC/mutate.py" "$HC_HDR" "$HC/mut")
check "mutate.py wrote the eleven heavyrule.h mutants" test "$(printf '%s\n' $HC_MUTS | wc -l)" -eq 11
# Caught: the old text occurred exactly once, the copy differs, it built, it
# ran to its summary, it failed, and the named case is among the failures.
hc_caught() {   # <key>
    local d="$HC/mut/$1" n want
    IFS=$'\t' read -r n want _ < "$d/meta"
    [ "$n" = 1 ] || return 1
    ! cmp -s "$HC_HDR" "$d/heavyrule.h" || return 1
    hc_build "$d" || return 1
    ! "$d/test" > "$d/run.log" 2>&1 || return 1
    grep -q '^summary cases=' "$d/run.log" || return 1
    grep -q "^FAIL $want " "$d/run.log"
}
for hc_m in $HC_MUTS; do
    IFS=$'\t' read -r _ hc_case hc_what < "$HC/mut/$hc_m/meta"
    check "FALSIFIED ($hc_m): $hc_what -> $hc_case fails" hc_caught "$hc_m"
done

# --------------------------------------------- profile.c and hxs.c call sites
cat > "$HC/sites.py" <<'PY'
import re, sys
prof, hxs = sys.argv[1], sys.argv[2]
s = open(prof).read()
m = re.search(r"\nstatic void hc_flip\(void\)\n\{\n(.*?)\n\}\n", s, re.S)
if not m:
    sys.exit("profile.c: no hc_flip()")
lines = m.group(1).split("\n")
# A heavy save posted, running, or finished since the last flip marks the frame.
body = m.group(1)
if not re.search(r"if \(__atomic_load_n\(&hc_save_busy, __ATOMIC_ACQUIRE\) \|\|\n\s*sd != hc\.save_done_seen\) \{\n\s*bad \|= 4;", body):
    sys.exit("hc_flip does not set bad |= 4 for a busy or finished heavy save")
g = [i for i, l in enumerate(lines) if re.fullmatch(r"\s*if \(!\(bad & 4\)\) \{", l)]
if len(g) != 1:
    sys.exit("hc_flip has %d `if (!(bad & 4)) {` guards" % len(g))
depth, end = 0, None
for i in range(g[0], len(lines)):
    depth += lines[i].count("{") - lines[i].count("}")
    if depth == 0:
        end = i
        break
for call in ("hc_trigger(", "hc_save_check("):
    at = [i for i, l in enumerate(lines) if call in l]
    if len(at) != 1 or not (g[0] < at[0] < end):
        sys.exit("%s is not called once, inside the bad & 4 guard" % call)
# saved(): the done count moves before busy clears, so a flip that sees the
# save no longer busy also sees it finished and marks that frame.
m = re.search(r"\nvoid hakux_heavycap_saved\(.*?\n\}\n", s, re.S)
if not m:
    sys.exit("profile.c: no hakux_heavycap_saved()")
a = m.group(0).find("__atomic_fetch_add(&hc_save_done, 1")
b = m.group(0).find("__atomic_store_n(&hc_save_busy, 0")
if a < 0 or b < 0 or a > b:
    sys.exit("hakux_heavycap_saved does not count the save before clearing busy")
h = open(hxs).read()
for pat in (r"^#define HXS_SLOT_HEAVY HC_SLOT_BASE$",
            r"^QEMU_BUILD_BUG_ON\(HXS_SLOT_HEAVY < HXS_SLOT_COUNT\);$",
            r"^    slot = hc_slot_of\(hc_pick_slot\(present, saved_at\)\);$"):
    if not re.search(pat, h, re.M):
        sys.exit("hxs.c lacks %s" % pat)
PY
hc_sites() { python3 "$HC/sites.py" "$1" "$2"; }
check "profile.c: a frame holding a heavy save fires no trigger and feeds no save rule; hxs.c's heavy slots are heavyrule.h's" \
    hc_sites "$HC_PROF" "$HC_HXS_C"
sed 's/^    if (!(bad & 4)) {$/    if (1) {/' "$HC_PROF" > "$HC/prof-noguard.c"
check "falsification ran: the unguarded profile.c differs" \
    bash -c '! cmp -s "$1" "$2"' _ "$HC_PROF" "$HC/prof-noguard.c"
check "FALSIFIED: a frame holding the save's pause may trigger -> the site check fails" \
    bash -c '! python3 "$1" "$2" "$3"' _ "$HC/sites.py" "$HC/prof-noguard.c" "$HC_HXS_C"
python3 - "$HC_PROF" "$HC/prof-order.c" <<'PY'
import sys
s = open(sys.argv[1]).read()
a = "    __atomic_fetch_add(&hc_save_done, 1, __ATOMIC_RELEASE);\n"
b = "    __atomic_store_n(&hc_save_busy, 0, __ATOMIC_RELEASE);\n"
if s.count(a + b) == 1:
    s = s.replace(a + b, b + a)
open(sys.argv[2], "w").write(s)
PY
check "falsification ran: the busy-first profile.c differs" \
    bash -c '! cmp -s "$1" "$2"' _ "$HC_PROF" "$HC/prof-order.c"
check "FALSIFIED: busy cleared before the save is counted -> the site check fails" \
    bash -c '! python3 "$1" "$2" "$3"' _ "$HC/sites.py" "$HC/prof-order.c" "$HC_HXS_C"
sed 's/^#define HXS_SLOT_HEAVY HC_SLOT_BASE$/#define HXS_SLOT_HEAVY 10/' "$HC_HXS_C" > "$HC/hxs-own.c"
check "falsification ran: the hxs.c with its own heavy base differs" \
    bash -c '! cmp -s "$1" "$2"' _ "$HC_HXS_C" "$HC/hxs-own.c"
check "FALSIFIED: hxs.c with its own heavy slot base -> the site check fails" \
    bash -c '! python3 "$1" "$2" "$3"' _ "$HC/sites.py" "$HC_PROF" "$HC/hxs-own.c"

# ----------------------------------------- the tag reaches the dispatcher's capture
# The tag is read from profile.c's one log call and the spec is the value the
# dispatcher exports when sourced (the comment above LOGCAT_SPEC names the tag
# too, so a grep of dispatcher.sh would pass with the tag gone from the value).
HC_TAG=$(sed -n 's/^    __android_log_print(ANDROID_LOG_INFO, "\([^"]*\)", "%s", b);$/\1/p' "$HC_PROF")
check "profile.c logs the blocks under exactly one tag (read: '$HC_TAG')" \
    test "$(printf '%s\n' "$HC_TAG" | grep -c .)" = 1
HC_SPEC=$( (unset LOGCAT_SPEC_OVERRIDE; export DISPATCH_DIR="$HC/dispatch" SERIAL=ee317437; . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1; printf '%s' "$LOGCAT_SPEC") )
hc_keeps() { case " $1 " in *" $2:I "*|*" $2:D "*|*" $2:V "*) return 0 ;; esac; return 1; }
hc_drops() { if hc_keeps "$1" "$2"; then return 1; fi; return 0; }
check "the dispatcher's LOGCAT_SPEC keeps $HC_TAG at I or below (sourced, not grepped)" \
    hc_keeps "$HC_SPEC" "$HC_TAG"
HC_SPEC_GONE=${HC_SPEC/ $HC_TAG:I / }
HC_SPEC_WARN=${HC_SPEC/ $HC_TAG:I / $HC_TAG:W }
check "falsification ran: both weaker specs differ from the real one" \
    test "$HC_SPEC_GONE" != "$HC_SPEC" -a "$HC_SPEC_WARN" != "$HC_SPEC"
check "FALSIFIED: the spec without the tag -> the spec check fails" \
    hc_drops "$HC_SPEC_GONE" "$HC_TAG"
check "FALSIFIED: the tag at W (drops every I line) -> the spec check fails" \
    hc_drops "$HC_SPEC_WARN" "$HC_TAG"
