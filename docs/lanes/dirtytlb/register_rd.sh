#!/bin/bash
# Registers the three predictions of #548's fix arm: HAKUX_TCG68_RD on by
# default (accel/tcg/cputlb.c), so tlb_reset_dirty() and tlb_set_dirty() walk
# only the MMU modes that can hold a live entry.
#   dirtytlb-rd.json         the Crimson soak pair, hand-queued (queue_rd.sh)
#   dirtytlb-rd-pixels.json  11 suites through the vertex and texture paths
#   dirtytlb-rd-signed.json  the twelfth, three runs per arm: its capture
#                            txt_A8R8G8B8_ADD moved in the counter's one-run arm
# Usage: register_rd.sh A_REF B_REF   (A: the counter, RD off; B: RD on)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
A=$1; B=$2
P=docs/testing/predictions
WHY="B turns HAKUX_TCG68_RD on by default and changes nothing else (accel/tcg/cputlb.c, one line). The walk then covers only the modes in tlb.c.dirty. A mode outside it holds only -1 entries, which tlb_reset_dirty_range_locked() rejects on TLB_INVALID_MASK and tlb_set_dirty1_locked() never matches, so every entry A re-arms B re-arms, and no dirty bit differs (docs/audits/2026-09-25-tcgchurn-pass1.md read the same argument)."

python3 docs/testing/ab_compare.py --register $P/dirtytlb-rd-pixels.json --force \
  --who lane.dirtytlb --issue 548 --a-ref "$A" --b-ref "$B" \
  --must-not-move 'Texture_CPU_Update/*' \
  --must-not-move 'Texture_3D_as_2D/*' \
  --must-not-move 'Texture_render_update_in_place/*' \
  --must-not-move 'Texture_format/*' \
  --must-not-move 'High_vertex_count/*' \
  --must-not-move 'SetVertexData/*' \
  --must-not-move 'Zero_stride/*' \
  --must-not-move 'Attrib_carryover/*' \
  --must-not-move 'DMA_corruption_around_surfaces/*' \
  --must-not-move 'Inline_array_size_mismatch/*' \
  --must-not-move '3D_primitive/*' \
  --prediction "#548 fix arm, pixels. $WHY PREDICTED: all 318 captures of these 11 suites are byte-identical between the arms, as they were in the counter's arm (dirtytlb-counter-pixels.json, 318 of 318 in these suites). REFUTED by any capture that moves: a guest store reached a page through an entry B left writable, so a vertex or texture upload was skipped, and the switch is not exact. Texture signed component tests is in dirtytlb-rd-signed.json with three runs per arm. Read scores1.tsv for unreadable rows and run1.log for UtilAcceptVsock before trusting a same."

python3 docs/testing/ab_compare.py --register $P/dirtytlb-rd-signed.json --force \
  --who lane.dirtytlb --issue 548 --a-ref "$A" --b-ref "$B" \
  --disc-suites "Texture signed component tests" \
  --must-not-move 'Texture_signed_component_tests/*' \
  --prediction "#548 fix arm, pixels, the suite with a capture that moved in the counter's one-run arm (txt_A8R8G8B8_ADD, 168,960 against 153,427). $WHY PREDICTED: with three runs per arm, every capture's B runs fall inside A's measured band. REFUTED by a capture whose three B runs all fall outside A's band, txt_A8R8G8B8_ADD included: if A's three runs agree with each other and B's three all differ from them, the shorter walk changes what that test samples, and the fix does not land as it stands."

python3 - "$A" "$B" $P/dirtytlb-rd.json $P/dirtytlb-rd-signed.json <<'EOF'
import json, sys, time
a, b, soak, signed = sys.argv[1:5]

d = json.load(open(signed))
d["runs_per_arm"] = 3
json.dump(d, open(signed, "w"), indent=2)
open(signed, "a").write("\n")

d = {
    "registered_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "who": "lane.dirtytlb",
    "issue": "548",
    "title": "Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso",
    "route": "crimson-skies",
    "device": "thor",
    "seconds": 240,
    "frames_every": 0,
    "runs_per_arm": 1,
    "perflog": True,
    "a_ref": a,
    "b_ref": b,
    "queue_order": "B FIRST, then A, both on the Thor, each through the soak's COOLDOWN gate: docs/lanes/dirtytlb/queue_rd.sh. Both arms carry [rdc] and [tlb68]; they differ in one line of accel/tcg/cputlb.c.",
    "window": "90 to 240 s after the first hakuX-perf line (phase_read_split.py THE WINDOW), as the counter pair",
    "judge": "python3 docs/lanes/dirtytlb/walk_read.py --pair <A result dir> <B result dir> for V, W, E, X, T, U, C, F and K2; K1 from docs/lanes/remote/pair461_read.py --pair A B; J from docs/lanes/dirtytlb/jpf.py A B.",
    "prediction": "#548 FIX ARM. B walks only the MMU modes that can hold a live TLB entry (HAKUX_TCG68_RD on by default); A walks all 22. MEASURED BEFORE, on two rd0 Crimson soaks on the Thor (479870, 936387): 169.8 and 177.0 off-vCPU walks per flip (vertex sync 72%, texture check 28%) and 237.4 and 241.9 vCPU walks per flip (all code arming); 7,204 and 7,992 entries scanned per walk, of which 1,793 and 2,620 are in the two modes that hold any; 21.11 and 24.25 us per off-vCPU walk, 14.19 and 16.44 per vCPU walk; render-thread CPU 21.58 ms per flip on 936387. Time per entry agreed between the two runs (2.93 and 3.03 ns off-vCPU), so the model is that a walk's time follows the entries it scans. EXPECTED on B: about 1,800 to 2,700 entries per walk; us per walk x0.25 to x0.45 of A's on both threads; render-thread CPU per flip down 2 to 3 ms; gfps 29 in both (the game paces itself to 30).",
    "legs": {
        "V (validity)": "Each arm has at least 20 [tlb68] lines and 20 [rdc] lines in the window. A run failing V is VOID, re-queued once and reported either way. A run whose thermal record shows cpu3-7 paused inside the window is VOID for C, F and J (#507), not for E, X, T and U.",
        "W (the switch, read off the arm's own lines)": "Every [tlb68] line of A reads fx=rd0 and every one of B reads fx=rd1. A pair failing W did not run what it names: VOID, not refuted, and no leg below is read.",
        "E (mechanism, high)": "B's entries per off-vCPU walk (rdoe over rdo) are within 15% of B's live entries (the sum over [tlb68] sz of table + 8 victim entries, mean over the lines) and at most 0.6 x A's entries per walk. Fails in the world where modes fill that sz does not show at print time, so the walk still scans most of what A's does.",
        "X (exactness, the leg that tells faster from skipping work)": "Per walk, the entries B re-arms are within 15% of A's, for the vertex sync ([rdc] vtx hits over calls; 1.09 on 936387) and for the vCPU thread ([tlb68] rdh over rd; 1.00); and tlb_set_dirty per flip (sd; 473.7 and 487.2) is within 15% of A's. Fails in the world where a skipped mode held live writable entries: hits per walk drop, and so does sd, because pages that were never re-armed take no notdirty store. X failing means the switch is not exact here and it does not land, whatever T, U and C read.",
        "T (the price off the vCPU thread, moderate-high)": "us per off-vCPU walk (rdous over rdo): B at most 0.75 x A. Fails in the world where the empty tables were cheap to scan and the live ones are the cost.",
        "U (the price on the vCPU thread, moderate-high)": "us per vCPU walk (rdus over rd): B at most 0.75 x A. Same world as T.",
        "C (render-thread CPU, moderate)": "[rdc] tcpu per flip: B at most A - 1.0 ms. Fails with T passing in the world where the render thread spends the saved time on-CPU anyway (a spin elsewhere), so the walks were not what bounded its CPU.",
        "F": "B's gfps median is at least A's minus 1.",
        "J (energy per frame)": "j_per_frame (title_verdict.py, #523's power record): B at most 1.03 x A. The two rd0 runs read 0.193 and 0.190 on the same work, 1.7% apart, so 3% is the band a difference must clear to count as up.",
        "K1 (control)": "Thermal parity: every cooling device's highest cur_state inside the window is the same in both arms. A pair failing K1 is thermally confounded; C, F and J are not read on it.",
        "K2 (control)": "Same scene: the larger hakuX-cpu M median is within 10% of the smaller.",
        "Reported, not judged": "walks and us per flip on both threads; the vCPU thread's walk share of its CPU (10.6% and 12.1% before); hakuX-cpu M; [rdc] per-site calls, us and hits per flip; net W."
    },
    "falsifier": "Not exact: X fails, or a capture moves in dirtytlb-rd-pixels.json or dirtytlb-rd-signed.json. Wrong mechanism: E fails, or T and U both fail with E passing (time does not follow entries). Right mechanism, no gain: T passes and C fails, or F or J fails. W failing voids the pair.",
    "expect": {},
    "expect_counts": {},
    "expect_note": "EMPTY ON PURPOSE: a soak writes no captures, so there is no golden key; the legs are read off [tlb68], [rdc], hakuX-perf, hakuX-pace and hakuX-cpu lines by walk_read.py. The pixel half is dirtytlb-rd-pixels.json and dirtytlb-rd-signed.json, which the arms job queues."
}
json.dump(d, open(soak, "w"), indent=2)
open(soak, "a").write("\n")
for p in (soak, signed):
    json.load(open(p))
EOF
sha256sum $P/dirtytlb-rd.json $P/dirtytlb-rd-pixels.json $P/dirtytlb-rd-signed.json
