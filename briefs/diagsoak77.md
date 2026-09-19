# lane.diagsoak77 -- drive #77's new frame dump on the artifact itself

Issue: #77 (Galleon deck/ground stipple, 10-14 stipple frames per 100)
Base: master (post PR #143, ref ab471cc80f + 841a38736c and later)
Files: none. Do not edit hw/xbox/nv2a/debug.h, hw/xbox/nv2a/pgraph/vk/renderer.c,
android/app/src/main/cpp/xemu_android.cpp or
android/app/src/main/java/com/rfandango/haku_x/LauncherActivity.kt -- the dump
instrument in them is finished and released to [free]; this lane only uses it.

## What's already done

PR #143 (merged) built a marker-file-armed per-draw frame dump that does not
force `pgraph_vk_finish` per draw -- confirmed NOT SERIALISED on a real device
dump (29 `submit_count` advances over 3,847 draws, 30 distinct `nv2a_frame`
values). Arm it with:

    adb shell 'echo <spec> > /sdcard/Android/data/com.jreinach.hakux.debug/files/frame_dump.on'

Spec tokens: frame count, `noimages`, `capNN` (MB cap), `afterNN` (delay
start), `diag` (old serialising path, for a control arm). `XEMU_FRAME_DUMP=<spec>`
arms at startup via `request.sh --env`. `docs/lanes/diagdump77/framedump_check.py`
parses a dump and reports per-draw merge/submit state; read its selftest before
trusting a verdict from it. Read nv2a_issues.toml's issue.77 entry and PR #143's
own body (`gh pr view 143`) before starting -- they cover what "serialised" vs
"not serialised" means in this dump and two instrument defects already fixed
(a lagging PPM, a hardcoded `per_draw_finish` field).

## Goal

Arm the dump on a Thor soak of the Galleon deck/ground scene, sized to cover
enough guest frames to include several of the stipple occurrences that
`docs/testing/galleon_flash_rate.py` already locates by HF/anisotropy (10-14
per 100 frames on deck, 0-14 on ground). Correlate the dump's per-draw records
(submit/merge state, `cb_draws`, barrier-adjacent counters) against the
stipple vs. non-stipple frame classification. The question #77 has been
blocked on since before #143: does merging or barrier state actually differ
between a stipple frame and a clean one, or is the artifact upstream of
anything this instrument can see (texture data, sampler state) -- the PR body
already says draw_merge defaults off and this dump can't see clears/blits, so
say plainly if the answer is "not visible to this instrument" rather than
stretching a null result.

## Falsifier

Name, before reading the dump, what a stipple frame's per-draw record would
have to show (relative to a clean frame in the same dump) for merging/barrier
state to be implicated -- e.g. a specific counter taking a different value
range on stipple-classified frames vs. others, at a size that survives the
same run-count discipline #65 and #77's own history got burned by (single-run
claims here have already produced one withdrawn conclusion on this issue).
If no such distinguishing signal exists in the data, that refutes the
merge/barrier hypothesis; it does not mean the dump failed.

## Done when

One (or more, if run-count discipline needs it) Thor soak with the dump armed
on Galleon deck/ground is on disk, analysed against galleon_flash_rate.py's
stipple classification, and the correlation result (positive, negative, or
"not visible to this instrument") is posted to #77 with the dump path and the
counters cited. Do not fix the stipple in this lane even if the mechanism
becomes obvious -- that is a follow-up dispatch once the mechanism is named.
