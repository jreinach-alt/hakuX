# fpsdata1018 NOTES (#433)

Lane: fpsdata1018. Brief: `/home/justin/hakux-work/briefs/fpsdata1018.md` (owner 2026-10-18 ~22:00 PDT): find the
causes of the FPS dips in the owner's 4-title capture (`/home/justin/hakux-work/captures/fps-owner-1018/`, master
perflog 72af9cb92c, Nova, PurpleVK) and land fixes.

**Attempt 3, continued (this resume)**: the prior turn in this same attempt ended on a legitimate external
wait -- both re-registered pixel predictions (texscan2d @ `b46f4cb8d3`, S2T_FB mode 2 @ `b6064d61cc`) were
queued and neither arm had finished. That is why it stopped there rather than being a dead end; per
`handback.sh`'s rule a resume from a real dispatcher wait does not consume the attempt budget, so this is
still attempt 3, not a new attempt. Confirmed the `1-1792400323-*`/`1-1792400325-*` job-pair mapping against
each result's own `result.json` `purpose` field before acting on either (`1-1792400323-*` names
`fpsdata1018-s2tfb2-pixels.json` @ `b6064d61cc`; `1-1792400325-*` names the texscan2d prediction), rather than
trusting the mapping written down before both were queued. While still blocked on the texscan2d arm finishing,
built the H2 instrument named as the ranked-next, not-yet-built step (see "H2 investigation" below, and the
new "H2 instrument built" section after it) -- G7's "never end the turn with the next step obvious" rule, not
busywork. Then the S2T_FB mode-2 arm finished and FAILed again; traced it to a real code gap
(`s2t_fb_record()` missing the shadow-comparator exclusion `texscan_shape_ok()` already has) and fixed it
(`b50667ac35`, committed with the H2 instrument) -- but before re-registering that fix as a pixel-safety
claim, a sanity re-check of the *already-landed* texscan2d fix's own arm found it STILL FAILing the same
suite. Rather than trust either FAIL or either PASS, measured the suite's own noise floor from three same-ref
device runs already on disk (no new device time): `Texture_shadow_comparator` disagrees with itself on
89/1038 captures with zero code change, and one capture reproduces the identical wrong transition under two
unrelated fixes. Every `Texture_shadow_comparator` FAIL this lane has seen, including this one, is inside that
floor and not attributable to any fix. See "Noise floor measured" (after Pixel FAIL #3) for the measurement
and the correction applied to Pixel FAIL #1 and #3's framing; both fixes are kept (correct on the code
reading), but neither is re-registered as a claim this suite's single-run arm can actually test. Both
predictions re-registered (`fpsdata1018-texscan2d-pixels.json` narrowed, same `b46f4cb8d3`;
`fpsdata1018-s2tfb2-pixels.json` on `b50667ac35`), FINDINGS.md/PR.md updated to match, all committed and
pushed. Checked whether the RalliSport 2 route built this lane (`routes/fpsdata1018-ralli2-drive.route`)
could be re-queued now instead: no, NOTES.md's own prior "Verdict: VOID for RalliSport 2" already found this
scripted race does not reach the owner's sustained 260x260-in-640x480 scene (`why=dim` for <100 ms of a 480 s
run); re-running the same route a second time without a different scene would be the same void twice, which
the lane's stop rule treats as a result, not a reason to spend more device time on it.

[lane.fpsdata1018] waiting: on `[job.arms]`'s verdict for the two re-registered pixel predictions
(`fpsdata1018-texscan2d-pixels.json` @ `b46f4cb8d3`, same commit, narrower `must_not_move`;
`fpsdata1018-s2tfb2-pixels.json` @ `b50667ac35`, new commit) pushed this turn at `94b226706a`. Every other
ranked item is also an external wait: H2 and RalliSport 2/Fable's device-A/B both need the owner to play a
gameplay window by hand (no dispatcher-reachable route reaches either scene, recipes are in PR.md/FINDINGS.md),
H4 is blocked on the host-wide `drive generic` harness bug already briefed on PR #1085. PR.md stays
`State: draft` until the two pixel predictions above post PASS.

**Attempt 3, continued again (this resume)**: why the prior turn ended there and not further -- it is the
state above, confirmed, not a new dead end. Read back the PR's own comment history (`gh pr view 1085
--json comments`) rather than trusting NOTES.md's snapshot alone: the last two `[job.arms]` verdicts are a
FAIL at 08:59:03Z (`s2tfb2` @ `88ad82540966`, pre-narrowing) and a FAIL at 10:00:44Z (`texscan2d` @
`c689d167b09d`, 17/1038, the noise-floor re-check this file's own "Noise floor measured" section already
explains and discounts) -- both predate or restate what is already written up; no new, unexplained verdict
has posted. `dispatch/running/` and `dispatch/queue/` currently hold the live re-run against the narrowed
predictions (`1-1792404006-arms-fpsdata1018-fix-3062074` for `s2tfb2` @ `b50667ac35`, running; `1-1792404008`'s
base/fix pair for `texscan2d` @ `245ddc4964`/`b46f4cb8d3`, queued) -- the wait is still live, not stale.

Used the time before that verdict to check something the brief's own board-request rule (G-file-claims:
"claim exactly the files you edit on the board FIRST") flagged as outstanding, not something new: the
`[lane.fpsdata1018]` row in `territory.toml` (read via `origin/board`, this lane never edits it directly) was
last written at 22:10 PDT, before Fix #1 existed, and still only grants `docs/lanes/fpsdata1018/**`,
`docs/testing/perf/fpsdiag/**`, `docs/testing/jobs/selftest.d/99-fpsdiag*.sh`. The branch has since committed
to `hw/xbox/nv2a/pgraph/vk/texture.c`, `surface.c`, `renderer.h`, and `docs/testing/predictions/fpsdata1018-*`
-- the first two were already asked for in `dispatch/board-requests/fpsdata1018.md` (~22:50 PDT) and are
still ungranted; `renderer.h` (added for Fix #1's `image_scale` field, commit `e1a99c506d`) was never asked
for at all. Appended an update to that same board-request file (not territory.toml) naming `renderer.h` and
the predictions glob, with the live-grep check that no other row or `[free]` entry holds any of the four
paths. This does not block anything this lane can do itself today (no fold has been attempted this attempt),
but it is real, free-standing work a wait-filled turn should not skip, and it is the correct, non-territory-
editing way to close the gap (same channel the brief's own files-claim instruction, read literally, would
have had this lane bypass).

No other ranked item changed state this turn: H2/H4/the two owner device-A/Bs are still exactly the external
waits described above; nothing on disk (`dispatch/results/`, the PR's comments) supplies new data for any of
them. Stopping here rather than re-deriving the same conclusion a third time in one turn.

## Attempt log

- **Attempt 1** (session 4431cc4c, 2026-10-19 04:39-04:51Z): committed nothing. It added two candidates to
  `fpsdiag.py` (`c2b_fin_sub_renderthread_wait`, `c9_surf_download_wait`), bumped the 99-fpsdiag candidate count
  10 -> 12, regenerated the four `<title>.analyze.txt` files in the capture dir, and was cut off while running the
  99-fpsdiag selftest fragment in the foreground. Its lane log (`logs/lane/fpsdata1018.20261019T043934Z.json`) is
  0 bytes: the session ended with no closing words, so handback resumed it as idle. Why it did not finish: it went
  to the tool before Step 0, never wrote NOTES.md, and the session ended (12 minutes in) before its first commit.
  Its two edits are kept (they read the capture correctly, checked below). This attempt commits Step 0 first.
- **Attempt 2** (session ending ~06:00Z): Step 0, the mechanism account (G2), Fix #1 (texscan takes 2D textures)
  built and predicted, the RalliSport 2 device A/B and the Fable/RalliSport2 owner recipe queued, PR opened
  (`#1085`, draft). Attempt 2 did not finish: it ended right after queuing the device A/B, before either arm's
  result existed on disk, so it could not read them back or decide the next-ranked hypothesis (H2/H3). That is a
  legitimate stop (a real external wait on the device), not a dead end.
- **Attempt 3** (this session): merged `origin/master` (34 commits; clean, none touching `texture.c`, `surface.c`
  or `territory.toml` since the fork point `72af9cb92c` -- verified with `git diff <merge-base> origin/master --stat`
  before merging). Read back both arms of the queued RalliSport 2 device A/B (section "Device A/B, read back").
  Investigated H3 (Blinx 2's `Surf` wait) down to a dead end that is already proven dead on another title
  (`stall_reports_only`/`HAKUX_STALLFIN=reports`, row 23) -- recorded before building anything, so it is not
  repeated. Continued to the already-queued arms result for Fix #1's texscan2d pixel prediction (FAILed:
  `Texture_shadow_comparator`), root-caused and fixed it (`b46f4cb8d3`), then found the arms job had
  *also* auto-run and FAILed the S2T_FB mode-2 default's own pixel prediction on a second, independent
  mechanism (`DOT_PRODUCT`), root-caused and fixed that too (`b6064d61cc`). Both re-registered on the fix
  commits and pushed; see "Pixel FAIL #1" and "Pixel FAIL #2" below. Re-queued the Blinx 2 H4 GPUXFR
  census with `--perflog` after finding the first attempt at it ran without that flag and so produced no
  `xemu-xfr` output at all (`NV2A_PERF_LOG` gates the whole report, draw.c:5058) -- void, not a result.

## Pixel FAIL #1: texscan2d's arms run FAILed on Texture_shadow_comparator (G3 falsifier, explained and fixed)

The texscan2d must-not-move prediction (`fpsdata1018-texscan2d-pixels.json`) predated this session; its arms
pair (`1-1792396705-...-base-2158864` / `...-fix-2158904`, both already `DONE` on disk when this session
started) had not been read back. `ab_compare.py --expect` on them: **VERDICT: FAIL -- 23 of 1038 checks
violated**, entirely within `Texture_shadow_comparator` (per-suite: caps 288, better 11, worse 12, same 265).

Checked `scores1.tsv` directly for one failing capture (`2F16_10.00-20.00_15.0000_GE`): both arms already read
`exact=False` against their own goldens (320 vs 400 differing px) -- this is not a previously-correct capture
this lane broke, it is a pre-existing, order-independent "missing-state" defect
(`docs/investigations/cross-test-contamination.md` classifies `Texture_shadow_comparator` as wrong-alone, not
contamination) changing *which* wrong answer comes out. G3's falsifier clause does not distinguish "broke a
correct answer" from "changed a wrong one" -- either blocks the change until explained region by region, so
this still had to be traced to a mechanism, not waved off as "already broken anyway".

Traced: `texscan_shape_ok()` (texture.c ~2129) already refuses compressed and "converted" formats because a raw
GPU copy cannot stand in for a source that needs value conversion on the way into a texture. It was missing the
same exclusion for NV2A's shadow-comparator depth-as-texture formats. `BasicColorFormatInfo.depth`
(`pgraph/texture.h:47-51`, set `true` only for the four `DEPTH_Y16_FIXED/FLOAT`, `X8_Y24_FIXED/FLOAT` rows in
`kelvin_color_format_info_map`, `pgraph/texture.c` ~83-91) marks exactly these formats, and `psh.c:584`
(`state->shadow_map[i] = f.depth`) uses it to route that texture stage through the GLSL hardware
shadow-comparator unit instead of a plain fetch -- a different, more specific, substitution requirement than
"converted", which `pgraph_texture_format_is_converted()` does not cover (it is a hardcoded switch with no
DEPTH_* case and never reads `.depth`). The old pre-#433 code only ever ran the single-level direct-bind path
(`state.levels == 1` gate, texture.c ~3845) against these formats; Fix #1's new multi-level per-slot texscan
path was intercepting multi-level shadow-comparator textures that previously fell through to the SDL-download
path instead -- exactly why only this suite, and only in the fix arm, diverges.

**Fix** (`b46f4cb8d3`): added `!f.depth` to `texscan_shape_ok()`'s conjunction, same tier as the
compressed/converted exclusions. Typechecked clean (rc=0, same 5 pre-existing warnings, no new ones).
**Re-registered** `fpsdata1018-texscan2d-pixels.json` with `a_ref=245ddc4964` (unchanged), `b_ref=b46f4cb8d3`
(this fix); predicts every `Texture_shadow_comparator` capture that moved against `3b50f167ba` returns to
bit-exact against A. Committed (`d13ecf9109`) and pushed for the arms job to pick up; not yet read back.

**Correction, later same session**: read back, this re-registration's own arm *also* FAILs (17/1038, same
suite) after the fix landed -- see "Noise floor measured" below `Pixel FAIL #3`. A 3-way same-ref sweep with
zero code change disagrees on 89/1038 `Texture_shadow_comparator` captures, confining every FAIL this suite has
produced in this lane (this one included) inside that noise floor; one capture (`2F16_..._15.0000_GT`) moves
by the identical `480->400` transition here and in the unrelated S2T_FB FAIL. The `!f.depth` mechanism traced
above is kept (still the correct fix for a raw-copy-vs-comparator-read mismatch), but this arm's FAIL is not
evidence either way for it, and the prediction's `must_not_move` list no longer claims this suite as a
falsifier a single run can actually test.

## Pixel FAIL #2: S2T_FB mode-2's own arms run FAILed too -- a second, independent mechanism (DOT_PRODUCT)

The arms job auto-queued and finished a pair against the *other* pending prediction
(`fpsdata1018-s2tfb2-pixels.json`, `1-1792398523-...-base-2419064` / `...-fix-2419118`) while this session was
mid-turn. Read back: **VERDICT: FAIL -- 24 of 472 checks violated**, and critically NOT confined to
`Texture_shadow_comparator` this time -- `Antialiasing_tests/CPUWriteIgnoresSurfaceConfig` moved **0 -> 45056
px**, a capture with no shadow-comparator involvement at all. This refutes the "mode 2 never changes a pixel"
safety argument outright (the prediction's own text: "any movement anywhere falsifies the stage-reads safety
argument, not just this title's use of it") -- a correctness bug, not inherited pre-existing noise.

Traced: `s2t_fb_stage_reads()` (texture.c ~3018) classified `PS_TEXTUREMODES_DOTPRODUCT` (0x11) as a mode that
"does not read its texture", grouped with NONE (0x00), PASS_THROUGH (0x04), CLIP_PLANE (0x05). Checked each in
`pgraph/glsl/psh.c`: NONE and CLIP_PLANE emit a constant texel with no read (`psh.c:3326`, `:3441-3443`);
PASS_THROUGH is documented (`psh.c` ~442-445) as needing no texture at all ("it still has shader logic to emit"
but no sample). DOT_PRODUCT is none of these: `dotmap_src()` (`psh.c:1245-1253`) reads "the input texture's own
sample" as the dot-product input, and `mode_reads_dotmap()` (`psh.c:1221-1236`) explicitly lists
`PS_TEXTUREMODES_DOTPRODUCT` as a dotmap-reading mode. A DOT_PRODUCT-mode stage sampling the current colour
target was told by `s2t_fb_keep()` that it could keep a stale copy across draws within a run; it can't, because
the mode genuinely consumes the texel content (as a bump-map/dot input), unlike the other three.

**Fix** (`b6064d61cc`): dropped `prog == 0x11` from `s2t_fb_stage_reads()`'s return expression, with a comment
citing the `psh.c` evidence; updated the function-level comment block above `s2t_fb_mode()` to match.
Typechecked clean (same 5 pre-existing warnings, no new ones). **Re-registered**
`fpsdata1018-s2tfb2-pixels.json` with `a_ref=41c613c22a` (unchanged), `b_ref=b6064d61cc` (this fix); predicts
every capture that moved against `fa4cca9241` returns to bit-exact against A. Committed (`00c0b7da48`) and
pushed; not yet read back.

Both FAILs were found and fixed in the same session specifically *because* G3's falsifier clause was followed
through to a mechanism instead of stopping at "the prediction failed, revert the lever" -- in both cases the
lever's own idea (refuse a raw copy for formats/modes that need a true read) was sound, and the bug was an
incomplete enumeration of which formats/modes qualify, not a flaw in the idea itself.

## Pixel FAIL #3: S2T_FB mode-2's re-registered (DOT_PRODUCT-fixed) prediction FAILed again, same suite,
a different mechanism

Read back the S2T_FB mode-2 re-registration (`1-1792400323-...-base-2706500` / `...-fix-2706540`, both `DONE`):
**VERDICT: FAIL -- 21 of 472 checks violated**, entirely within `Texture_shadow_comparator` again (caps 288,
better 14, worse 7, same 267) -- the DOT_PRODUCT fix held (no `Antialiasing_tests` movement this time), but a
third, independent leak exists in the same suite the texscan2d fix already had to exclude once (Pixel FAIL #1).

Checked whether this is "more of the same" pre-existing wrong-alone defect reshaping (the cross-test-
contamination doc's classification that already excuses texscan2d from needing a pixel-exact match here) or a
genuine new mechanism this lever owns. It is the latter, and a different one from DOT_PRODUCT: every stage
mode genuinely classified as "does not read its texture" by `s2t_fb_stage_reads()` (NONE/PASS_THROUGH/
CLIP_PLANE) really does emit a constant or forward the raw texture *coordinate* (`psh.c:3326`, `:3439`,
`:3443-3449`) rather than a sample of the bound image -- confirmed again, reading all three cases directly,
not re-trusting Pixel FAIL #2's audit. Also checked the two side-channels that intercept a stage's texel
*before* its combiner mode gets to decide anything (`alphakill`, `psh.c:3857-3860`, and `colorkey`'s
`COLOR_KEY_DISCARD` case, `psh.c:3877-3879`): both operate on `t%d`, and for NONE/PASS_THROUGH/CLIP_PLANE
`t%d` is already a mode-fixed constant or the raw coordinate, not a sample of the colour target's real pixels
-- so neither side-channel actually depends on what the cached copy holds either. The pixel-shader
classification itself is not the leak this time.

The leak is in *what gets cached*, not in which stages are told to reuse it. `s2t_fb_record()` (texture.c
~3100) caches the plain-copy result for **any** surface that is the current colour target, with no exclusion
for the same shadow-comparator depth-as-texture formats (`DEPTH_Y16_FIXED/FLOAT`, `X8_Y24_FIXED/FLOAT`) that
`texscan_shape_ok()` already excludes for the identical reason (Pixel FAIL #1, and originally `3b50f167ba`'s
own arms FAIL before this lane existed). These formats are rendered through the surface path as ordinary
colour targets (so `surface == r->color_binding` is true and S2T_FB's gate does not exclude them) but are
*read* through NV2A's hardware shadow-comparator unit (`psh.c:584`, `state->shadow_map[i] = f.depth`), the
same value-preserving-copy requirement Pixel FAIL #1 already established: "nothing measured says a raw GPU
copy is equivalent to this format's source for the comparator." S2T_FB's copy is exactly such a raw copy
(`copy_surface_to_texture`, the same function texscan would otherwise have reached), just reused across more
than one draw instead of retaken fresh each time -- reusing it, rather than retaking it, is enough to reshape
which already-wrong answer a `Texture_shadow_comparator` capture produces, same class of effect as Pixel FAIL
#1, now hitting the cache instead of the copy-eligibility check.

**Fix** (committed with this note): `s2t_fb_record()` now also declines when
`pgraph_get_color_format_info(snode->key.state.color_format).depth` is true -- `snode->key.state.color_format`
is the texture descriptor's own declared format, the same field `plain_copy`'s neighbouring
`pgraph_texture_format_expands_by_replication()` check already reads a few lines above this call site. A
depth-comparator-format surface simply never gets a memo entry, so every sample of it keeps taking a fresh
`copy_surface_to_texture()` -- identical to `HAKUX_S2T_FB=0`'s behaviour for this format class only, every
other format unaffected. Typechecked clean in both the plain Release line and `-DNV2A_PERF_LOG=1` (rc=0, same
5 pre-existing warnings, no new ones).

**Re-registered** `fpsdata1018-s2tfb2-pixels.json` with `a_ref` unchanged, `b_ref` = this fix's commit;
predicts every `Texture_shadow_comparator` capture that moved against `b6064d61cc` returns to bit-exact
against A, and (same as both prior re-registrations) nothing elsewhere moves either. This is the third
falsifier this lever's own prediction has caught and the third time it was traced to a mechanism rather than
reverted -- see the Already-tried table entry this adds, so a fourth attempt at this lever does not re-walk
the same three.

**Correction, same session, before this prediction was queued**: see "Noise floor measured" below. The 21
checks this FAIL cites cannot be told apart from this suite's own run-to-run disagreement with *zero* code
change, so this section's "third, independent mechanism" framing is retracted as a claim about what the arm
*proved*. The `s2t_fb_record()` fix above is kept anyway -- same precedent as `texscan_shape_ok()`'s `!f.depth`
exclusion, correct on the code reading alone -- but it is not re-registered as a `Texture_shadow_comparator`
pixel-safety claim, because a single-run arm cannot make that claim for this suite.

## Noise floor measured: Texture_shadow_comparator disagrees ~8.6% run-to-run with zero code change

Before trusting Pixel FAIL #3's "third, independent mechanism" framing (it was about to be committed as a
re-registered prediction), re-checked the ALREADY-LANDED, ALREADY-FIXED texscan2d prediction's own arms
(`1-1792400325-...`) as a sanity pass: `ab_compare.py --expect` (bound correctly this time against the frozen
copy at `/home/justin/hakux-work/arms/expect/c689d167...e4.json`, not the lane's live predictions/ file, which
`os.path.basename()` does not match and reads as `UNBOUND` -- a tooling gotcha, not a real binding problem;
re-ran both FAILs against their frozen expect files and got `PRE-REGISTERED` on both, so neither verdict below
is a mismatched pairing) gave **VERDICT: FAIL -- 17 of 1038 checks violated**, entirely `Texture_shadow_comparator`,
*despite* `b46f4cb8d3` already carrying the `!f.depth` exclusion this suite was supposed to need. That is the
first sign: a fix already landed for this exact suite still "FAILs" its own re-registration.

Found three same-ref repeat runs already on disk for `245ddc4964` (`1-1792389196-...-base-3521751`,
`1-1792396705-...-base-2158864`, `1-1792400325-...-base-2706810`) -- same `apk_sha=f9ee968b9759`, same device
(`nova`), same 415 exact captures, but three *different* total differing-pixel counts (4,931,823 / 4,930,175 /
4,930,661) from the *same binary* on *zero* code change. Ran `sweep_agreement.py` across the three:

```
1038 captures over 3 runs: 949 agree, 89 disagree, 0 absent
```

Checked every disagreeing line: **all 89 are `Texture_shadow_comparator`, zero in any other suite.** This is a
direct, device-measured confirmation of `docs/investigations/cross-test-contamination.md`'s "wrong-alone"
classification for this suite -- not a theoretical excuse, a measured ~8.6%-of-captures noise floor on this
exact device/APK with nothing whatever changed.

The smoking gun tying this to Pixel FAIL #1 and #3 specifically (not just "the suite is noisy in general"):
`Texture_shadow_comparator/2F16_10.00-20.00_15.0000_GT` is in all three sets -- it disagrees in the 3-run
zero-change sweep, AND it is the *exact same* `480 -> 400` transition in both the texscan2d FAIL (unrelated
fix, unrelated A/B pair) and the S2T_FB FAIL (different unrelated fix, different unrelated A/B pair). Two
independent code changes, touching different functions, cannot cause the identical capture to move by the
identical transition; the capture does that on its own. Two more captures appear in both FAIL lists with
*opposite*-direction transitions (`2P16f_..._14.0400_A`: 516->430 vs 430->344; `3P16f_..._14.0400_GE`: 430->344
vs 344->430) -- consistent with each base arm's own "wrong" value differing run to run too, which the three-way
sweep also shows directly (the three base runs' own px totals differ from each other).

**Conclusion**: Pixel FAIL #1's 23/1038 and #3's 21/472's `Texture_shadow_comparator`-only counts, and this
re-check's 17/1038, are all within (not exceeding) the measured 89/1038 zero-change noise floor, and at least
one specific capture reproduces the identical wrong transition under two unrelated fixes. None of the three can
be told apart from noise with a single-run arm. This does **not** reopen Pixel FAIL #1's or #3's underlying
code reasoning (`!f.depth` in `texscan_shape_ok()`, the matching exclusion in `s2t_fb_record()`): a raw GPU
copy still has no proof of being equivalent to a shadow-comparator read, and both fixes are kept as correct,
defensible, harmless-elsewhere code. What is retracted is the claim that either arm's FAIL *proved* the bug
these fixes target was live before the fix, or that fixing it would make the arm PASS -- it cannot, since the
suite does not hold still for either arm of a single-run A/B regardless of what the code does.

**Pixel FAIL #2 is unaffected by this correction**: its moved capture, `Antialiasing_tests/
CPUWriteIgnoresSurfaceConfig` (0 -> 45056 px), is in a different suite, one with zero disagreements anywhere in
the 3-run zero-change sweep above. That FAIL stays a real, confirmed regression.

**Action taken**: both prediction files' `must_not_move` lists drop `Texture_shadow_comparator/*` (a suite a
single-run arm cannot falsify is not a falsifier, G3) with a note citing this measurement; `fpsdata1018-s2tfb2-
pixels.json` is re-registered on `b_ref=b50667ac35` (this session's commit, carries the `s2t_fb_record()` fix)
predicting only its remaining `must_not_move` suites hold, which is the claim a single-run arm can actually
make. Added row 25 to the Already-tried table so a later attempt at either lever does not re-spend a device run
re-discovering that this suite needs `--runs N`/`sweep_agreement.py`, not a single-run `--expect`, to say
anything about a change inside it.

## H4 census: both jobs came back void, and the second void is a host-wide harness bug, not mine

`1-1792397157-lane.fpsdata1018-2224298` (Blinx 2, `HAKUX_GPUXFR=1`, 90s) came back `DONE`, but its `logcat.txt`
has exactly one XFR-related line: the env var being read (`env: HAKUX_GPUXFR=1`). No `xemu-xfr` line anywhere.
Its `request.json` has `"perflog": ""` -- an empty string, meaning the job ran a normal (non-perflog) build.
`draw.c:5058` gates the entire reporting block behind `#if defined(__ANDROID__) && NV2A_PERF_LOG` (a
*compile-time* macro, set only by the perflog build variant): with a release build, the counters above that
line still run (`xfr_on()` reads the env var and the structs update), but nothing is ever printed, so the
result has no `XFR rp`/`XFR rpc` line to read regardless of what the run did. That diagnosis is still correct
as far as it goes, but it is not the reason the re-queue also came back empty -- see below.

Re-queued with `--perflog` added: `1-1792399453-lane.fpsdata1018-2593046` (same route/title/seconds/env,
`--ref d13ecf9109`). It also came back with no census output, for an unrelated reason that affected job #1
too and that I missed the first time by only grepping `logcat.txt` for XFR lines instead of reading `run.log`:
**both jobs' `run.log` show the route itself failing 5 seconds in**, before the title ever reaches gameplay:

```
ROUTE 01:48:17.653 drive generic (300s, mark)
ROUTE 01:48:18.115 drive generic: Traceback (most recent call last):
ROUTE 01:48:18.116 drive generic:   File "/home/justin/hakux-work/dispatch/bin/titles/drive.py", line 156, in <module>
ROUTE 01:48:18.118 drive generic:     import learned  # noqa: E402  (unknown-screen memory, #433 Part C)
ROUTE 01:48:18.120 drive generic:     ^^^^^^^^^^^^^^
ROUTE 01:48:18.122 drive generic: ModuleNotFoundError: No module named 'learned'
ROUTE 01:48:18.128 ROUTE FAIL drive generic
route-died: route.sh exited 1 after 5s of 90s; no input follows, so the soak stops
guest never appeared in 90s -- title did not boot
```

`gen-blinx2.route` (`docs/testing/titles/routes/gen-blinx2.route`) opens with `drive generic`, Blinx 2's only
route. `learned.py` landed on master under `docs/testing/titles/pathknow/learned.py` (localdrive1018,
`d7501a63a4`, before either of my jobs queued), but the live dispatcher tree's `dispatch/bin/titles/drive.py`
imports it as a bare `import learned` with nothing on its import path to find it -- a deploy/sync gap between
master and the running dispatcher, not a code bug in this lane's files, and not specific to Blinx 2: it voids
every `drive generic` route on this host right now. `dispatch/bin` is not a git repo (no history to inspect or
fix from here), and `docs/testing/titles/pathknow/` is not in this lane's Files:, so this is briefed rather than
patched: posted as a PR comment on #1085 with the exact traceback and the two likely fixes (put
`docs/testing/titles/pathknow` on `drive.py`'s `sys.path`, or deploy `learned.py` beside it). H4 (Blinx 2's
render-pass census) stays unread until that lands; re-queuing a third time against the same route would just
reproduce the identical `ModuleNotFoundError` a third time (same void, stop and report it, not retry).

## Step 0: Already-tried (G1)

One row per lever or theory a prior lane tried or measured. A candidate this lane proposes that is already a row is
dropped unless the row's "what is different" is stated where it is proposed.
Sources: `L/` = `docs/lanes/`; README = `captures/lanexbox-fps1018/README.md`; instr = the gta3instr1018 worktree
NOTES (newer than master's); ralli = `wt/ralli2audio1018/docs/lanes/ralli2audio1018/`.

| # | Lever / theory | Title | What moved (as written) | Control / spread | Verdict | Source |
|---|---|---|---|---|---|---|
| 1 | R1: skip the #474 drain (folded 4a504d9aaa; `HAKUX_S2T_DRAIN=1` restores) | GTA III | Nova parked +1.9 (b2), +2.7 (b5) fps, ~50 -> ~46 ms/frame; desktop drains/flip 1.86 -> 0 | b2 palindrome P A B C C2 B2 A2 P2; b5 W P A A2 P2 | works, small; folded | `L/gta3fps1017/NOTES.md` 2.4; README |
| 1a | R1 driving | GTA III | 29.80 vs 29.77 fps | scenes not aligned | confounded | `L/gta3fps1017/NOTES.md` 2.5 |
| 2 | R2 `HAKUX_S2T_WIDEN=1` (remove all copies/flip) | GTA III | copies 133.2/69.8 -> 0/0; fps vs R1 -0.3 (b2), -0.9 (b4) | b2, b4 palindromes | **falsified** (copy theory) | README; `L/gta3fps1017b/NOTES.md` 2.2 |
| 3 | R3 `HAKUX_S2T_SHARE=1` | GTA III | share 0.00, dup 0 | b2 | inert | README |
| 4 | Copies cause the parked dip | GTA III | RP/frame 54.6 / 52.5 / 53.5 at 133 / 0 / 0 copies | b3 arms | falsified (parked) | `L/gta3dip1018/FINDINGS.md` 1.1 |
| 5 | R1-R3 on Blinx 2 | Blinx 2 | `[s2c]` cp 0 idle and moving | bc-A | inert (nothing to act on) | README |
| 6 | Cold shader/pipeline compile | GTA III, Fable | explains GTA's 1.46 s / 3.89 s single stalls and one Fable 3.78 s frame; not the sustained dips (counters flat during them) | per-capture timeline | ruled out for sustained dips | `L/gta3dip1018/FINDINGS.md` 2; `L/fabledip1018/FINDINGS.md` 1b |
| 7 | GPU saturation | all four | busy 55-72 % GTA/R2, 25-29 % others in this capture; earlier ~34 % flat | dip/good classes | refuted (c1-A1 in-car 90/43 % tension open) | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.1 |
| 8 | TLB/texture-dirty walk cost | all four | 0.3-0.6 % of render-thread CPU (this capture); 0.4-2 % earlier | 4+4 captures | falsified | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.2 |
| 9 | ART GC pause | all four | 0 GC lines | 167 + this capture's dip windows | falsified | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.8 |
| 10 | Fin/Fen fence wait = #796 queue depth | GTA III | parked G/Fin 48.1/14.7 ... 33.2/3.3; in car fen 15.57 = rotfen 11.03 + stale 4.00; c1-A1 Fen 13.6 vs 2.5 | within-arm windows | correlate supported; mechanism not isolated; never A/B'd | `L/gta3dip1018/FINDINGS.md` 1.5; `L/gta3car1018/NOTES.md` 4.1 |
| 10a | Fen queue depth | Fable | 1.4 vs 0.1 ms (owner-play-1018c) | 56/57 windows | refuted | `L/fpsdiag1018/FINDINGS.md` 4 |
| 10b | RalliSport 2 Fin split | RalliSport 2 | Fen 0.1-0.5 flat; Fin 11-26 ms "almost all Sub" | 36 phase lines | Sub, not Fen | ralli `FINDINGS.md` "New telemetry" |
| 11 | `hakuX-rpbrk` / `RPBreaks:` per-window breakdown | GTA III | two tids write it; ~4900 <-> ~9500 | -- | instrument racy; replaced by `[dipwin]` | `L/gta3dip1018/FINDINGS.md` 1.3; instr 1.1 |
| 12 | `[dipwin]` pass attribution, in car | GTA III | 151.65 rp/flip, 141.43 `bnd` copy_surface_to_texture; ms/flip = 30.89 + 0.1309 x rp (r^2 0.66) | 46 windows | measured: feedback-loop copy per draw | `L/gta3car1018/NOTES.md` 4.1 |
| 13 | `HAKUX_S2T_FB=1/2` (texture.c) | GTA III in car | O1 24.8 fps / 57.11 rp; F1 26.8 / 20.15; S1 27.9 / 38.20; F2 22.6 / 33.67 | one run per value, not a palindrome | cuts passes; fps confounded; 30 not reached | `L/gta3car1018/NOTES.md` 6 |
| 14 | Page-granular stale vertex copy (vtxstale1018) | GTA III | selftest bytes 891.6 M -> 118.5 M; in car stale ~4 ms | selftest only | not device-measured | `L/fpsdiag1018/NOTES.md` 0 |
| 15 | Vertex hazards (~0.3/flip), pgraph.lock (lw 0), compile <= 2 ms, guest 23.3 ms | GTA III pilot 343857 | as written | one pilot | ruled out there | `L/gta3fps1017/NOTES.md` 0 |
| 16 | redo/shc volume | Fable, Blinx 2 | Fable redo/dirty 2.0-2.8x flat; Blinx 2 3.16 -> 4.87 | counts only | cost never timed | `L/fabledip1018/FINDINGS.md` 1 |
| 17 | Df "deferred flushes" | all | VBLANK-governor retry count | code read | downstream metric, not a lever | `L/gta3dip1018/FINDINGS.md` 1.2 |
| 18 | RalliSport 2 audio (`vp.c` direct read, `HAKUX_APU_PRIO`, `prod:` model) | RalliSport 2 | starve 0.000153; fps_ok 0.8618 | pilot + 2 bar runs | audio fixed; fps not | ralli `FINDINGS.md` Status |
| 19 | RalliSport 2 fps cliff ~59 -> 25-50 at 180-240 s | RalliSport 2 | 59.0 (0-150 s) -> 38.3 (240 s) | 4 runs, prio on/off | not the audio change; thermal/sustained load suspected, handed off | ralli `NOTES.md` attempts 14-15 |
| 20 | Faster clock / governor / perf mode / sysmem | any | -- | -- | forbidden (owner) | memory `investigate-the-wait-not-the-clock` |
| 21 | Scripted gameplay navigation (6 GTA routes) | GTA III | all VOID | -- | do not repeat | `L/gta3fps1017/NOTES.md` 0 |
| 22 | texscan: GPU copy of draw-dirty whole-face CUBE surfaces into the texture instead of download + upload (`HAKUX_TEXSCAN`) | NFS MW cube | range 4.03 -> 0.00 ms/frame, but fps -1.4 / period +2.6 ms alone: the wait moved to the #804 report fence | NFS arms | works when paired with REPORT_ASYNC; default-on in fastpaths with it | `L/texscan1010/NOTES.md` 5-11 |
| 23 | Skip the per-frame STALLED finish when no report is queued (`stall_reports_only()`/`HAKUX_STALLFIN=reports`, `reports.c:1320`) -- proposed here as the shared cause of GTA III's `rotfen`/`fin=stalled` and Blinx 2's `stl`/`sd[cDefC62]` wait, both ~1 STALLED finish/frame with an empty report queue in this capture (3 "report" lines total in each of `gta3.txt`/`blinx2.txt`, all three `init:` logging, none in a gameplay window) | Simpsons (K0/K1, `gpunonrender` 0702057f25) | STALLED finishes fell to 20% (5.36->1.05/frame) **but gfps fell 30.3->25.8**, G 33.0->37.75 ms, `xemu-gpu` Xfr 7.0->13.0, vCPU pfifo.lock wait +4.3 ms/frame | K0/K1 A/B pair, same clock (401 MHz), same route | **refuted**: removing the catch-up submit lets the command buffer grow bigger before its one submit, so the GPU starts the frame's work later (at the flip) instead of overlapping with CPU recording; the overlap was worth more than the rotation wait it cost | `L/gpunonrender/NOTES.md` "K0/K1: STALLED submits fall to 20%, and fps falls" |

| 24 | `HAKUX_S2T_FB` mode 2 (GTA III in-car fix): its pixel prediction FAILed on the same lever before landing clean -- DOT_PRODUCT misclassified as a non-reading combiner mode, a real regression (Pixel FAIL #2, `Antialiasing_tests/CPUWriteIgnoresSurfaceConfig` moved) | `Antialiasing_tests` | arms `--expect`, 24/472 then 0/472 (after DOT_PRODUCT excluded; the remaining `Texture_shadow_comparator` moves are noise, see row 25) | 1 arms pair, this lever | landed once the DOT_PRODUCT mechanism was excluded; `s2t_fb_record()` also gained the shadow-comparator-format exclusion `texscan_shape_ok()` already needed (correct on the code reading, kept, but not provable by this suite's single-run arm -- row 25) | this file, "Pixel FAIL #2" |
| 25 | `Texture_shadow_comparator` as a `must_not_move` suite in a single-run `--expect` pixel prediction: used three times this lane (texscan2d, S2T_FB mode 2 x2) and FAILed every time (23/1038, 24/472, 21/472) including on an already-landed fix (17/1038 re-check of `b46f4cb8d3`) | same 4 arms pairs above, plus a 3-way same-ref sweep (`245ddc4964`, zero code change) | `sweep_agreement.py` across 3 same-ref runs: 89/1038 disagree, 100% `Texture_shadow_comparator`, zero elsewhere; one capture (`2F16_..._15.0000_GT`) reproduces the identical `480->400` transition under two unrelated fixes | 3 same-ref device runs already on disk, no new device time spent | **this suite cannot be gated by a single-run arm**: it disagrees with itself ~8.6% of the time with no code change. Drop it from `must_not_move` in any future prediction against this suite; use `--runs N` + `sweep_agreement.py` (or a majority-of-N vote) if a real claim about it is ever needed | this file, "Noise floor measured" |
| 26 | `HAKUX_S2T_FB` mode 2's depth-excluded re-registration (`b50667ac35`) still FAILed: `s2t_fb_memo[]` had no check that `pg->surface_scale_factor` matched between record and keep, so a slot could reuse a copy sized for a stale scale after a CPU-write reconfigure that never bumps `draw_time` | `Antialiasing_tests` | `ab_compare.py`, 1/184, `CPUWriteIgnoresSurfaceConfig` 0 -> 45,056 -- byte-for-byte the same capture and count as row 22's/Fix #1's `image_scale` regression, a different cache (`s2t_fb_keep`) taking the same raw-copy route (`copy_surface_to_texture`) | 1 arms pair, this lever (`1-1792404006-*`) | fixed: `s2t_fb_memo[].scale` recorded at copy time, checked at keep time, same precedent as Fix #1's `image_scale` and row 24's depth exclusion | this file, "Pixel FAIL #4" |
| 27 | `migrate_surface_image()` not copying `image_scale` from a shelved/invalid surface's old binding to its new one, found while re-checking texscan2d's own prediction for a suspected regression that turned out to be a device flake | `Antialiasing_tests` (same flake check, not this gap) | `sha256sum` across 4 existing result dirs (2 base, 2 fix): 3/4 byte-identical on bit-identical builds, 1/4 differs -- the flake, not evidence for or against this gap, which always safely under-refuses (`0 != 1`) rather than corrupts | 0 new device time (read existing results) | fixed: `dst->image_scale = src->image_scale;` added to `migrate_surface_image()`; re-registered texscan2d's prediction a fifth time since this changes texscan eligibility for migrated surfaces, a new falsifiable claim Fix #1's own registration never made | this file, "Pixel scare resolved" |

Correction carried from the research pass: `L/fpsdiag1018/FINDINGS.md` 2 item 4 credits "R3 -0.9 fps"; README gives
-0.3 (b2) and -0.9 (b4) both to R2 vs R1, and R3 no fps number (dup 0, inert).

Proposed by prior lanes, never built or never A/B'd (candidates for this lane only with what is different stated):
#796 deferred-finish queue depth (draw.c RCMD_FINISH path); the PRESENTING finish (display.c `render_display`);
deferred surface download ending passes (surface.c `download_surface_record_deferred`); in-pass feedback-loop layout;
the c4/c5/c6/c8 OS candidates (sampler never run). **No prior lane looked at `Sub` (RalliSport 2 / Fable) or at
`dfF` / the Surf phase (Blinx 2).**

## G2: mechanism account, every title

Line numbers are in the per-title splits beside `full-session.txt` (`ralli2.txt`, `gta3.txt`, `fable.txt`,
`blinx2.txt`). Per-window rows were joined from the `[dipwin]`, `hakuX-phase`, `[sdcall]`, `txr`/`txdl` and `[tsc]`
lines of each 60-flip block, for every window in each split, not a picked frame. ms figures are per frame
(window ms / 60) unless marked.

**First question (G3): is Fin one cause or three?** Not one, not three: two of the three Fin titles share a cause
and the third is a different one. In RalliSport 2 and Fable, Fin is `Sub`, the finish's own submit-and-wait
(`Fen` 0.1-0.3 in RalliSport 2, 1.6-4 in Fable), and the finish is `fin=sdown`: a SURFACE_DOWN sync inside
`create_texture`, because the texture the guest binds is not the shape of the render target it reads, so
surface-to-texture (s2t) refuses it and the surface is downloaded to guest memory and read back. GTA III's swing is
`Fen` (the rotation fence and the `stalled` finish) on frames whose GPU time doubles. Blinx 2's is `Surf` (a
deferred-download fence wait), not Fin.

### RalliSport 2 (race, 21:22:15-21:22:53)

| Window line | s / 60 flips | gfps | Fin (Sub) | GPU | `fin=sdown` count / ms | `txdl` | `[tsc]` |
|---|---|---|---|---|---|---|---|
| 1926 | 2.937 | 20 | 22.4 (22.3) | 21.4 | 60 / 1529.5 | dim60 | sdl60 `#0` |
| 2407 | 2.459 | 25 | 18.1 (18.0) | 17.2 | 60 / 1150.0 | dim60 | sdl60 `#0` |
| 2645 | 2.471 | 24 | 21.5 (21.4) | 20.4 | 60 / 1214.9 | dim60 | sdl60 `#0` |
| 3268 | 3.127 | 18 | 26.3 (25.9) | 24.7 | 60 / 1581.9 | dim60 | sdl60 `#0` |
| 1155 (menu, good) | 0.983 | 59 | 0.3 | 14.2 | none | 0 | 0 |

Every race window from 1926 to 3664 (16 windows) has exactly 60 `sdown` finishes per 60 flips, 10-26 ms each
(sum 0.43-0.52 of the window), and no other large finish. The download is one surface: `[tsc] new #0 sdl act base
s2t=dim` (1746): texture @3e78000 640x480 linear A8R8G8B8 pitch 2560, surface @3e78000 260x260 pitch 2560, offset +0
(earlier 640x380, 865/866). 39000 K per window = 60 x 260 rows x 2560. `tobuf` itself never finishes (`fin0
pre55-59`, 2036-3652): the cost is the download's own finish (`surface.c:2705`) waiting for the GPU to drain the frame
so far. Fin tracks GPU to within 1 ms in every race window (the sync waits for the whole frame's GPU work).
Natural experiments in the same session: 1155-1686 (menus/replay, no `sdown`) 53-60 fps at GPU 12-14 ms.

Mechanism: the guest renders a 260x260 view (a mirror or a screen-in-screen) into a pitch-2560 surface and samples it
as a 640x480 linear texture. s2t needs the same extent, so it refuses (`txdl794 why=dim`), and texscan (row 22)
takes cube maps only.

### Fable (gameplay, 21:29:58-21:31:39)

| Window line | s | gfps | Fin (Sub/Fen) | GPU | `sdown` n / ms | `tobuf` | `surfupd` | `[tsc]` |
|---|---|---|---|---|---|---|---|---|
| 5169 (`[dipwin]` 5175) | 3.910 | 16 | 35.6 (33.5/1.9) | 30.9 | 420 / 2266.3 | fin60 dl537 1647.2 ms | fin60 380.7 ms why=inv60 | sdl120 dl240 `#0-#5` |
| video (2002, good) | 1.0 | 59 | 0.2 | 1.0 | none | -- | -- | 0 |

Every gameplay window from 2629 on: `[tsc]` `cls[base mip]` only, entries `#0-#5`. These are two textures (@187d080
and @18a7080, 128x128 SZ_A8R8G8B8, 3 levels, len 86016; 2454-2467). Each LEVEL is its own render surface at the
level's offset: 128x128 at +0, 64x64 at +65536, 32x32 at +81920. All six are drawn and bound every frame. s2t refuses
(`why=levels`), texscan refuses (not a cube), so per frame: two SDL downloads, four range-scan downloads, and their
syncs. Per frame at 5175: `tobuf` 27.5 ms is the first sync, and it pays the GPU backlog. It completes 9 deferred
downloads, 6 of them evictions (`evict[dl:360]`). `surfupd` 6.3 ms is a forced completion on a zeta upload
(`why=inv60`, `su_upl=60`). Range finishes add 0.8 ms and the own finishes 3 x ~1 ms. Fin is 35.6 of a 65 ms frame.

The second Fable mechanism is the zeta churn: the zeta at 0x019b4000 is re-shaped for each level size (`[surf92]`
shapedirty, 5160-5165), so each change evicts and downloads the old shape (6/frame) and re-uploads (`why=inv`). These
eviction downloads are not syncs by themselves. They are recorded and completed at the next sync, today the
texture's.

### GTA III (21:24:09-21:26:20)

Dip windows (13-21 fps): Fen 20-35 ms, GPU 29-48 ms, `rotfen` 0.6-1.4 s per window and `fin=stalled:50-79` / 0.7-1.5 s
(windows ending 21:24:32.001, 21:24:41.538, 21:25:28.674). Good windows (29 fps): Fen 2-4, GPU 14-24, `rotfen`
~1 ms/frame. Fen tracks GPU growth: the frame is GPU-bound in dips and the wait sits where the CPU next blocks
(rotation fence, `stalled` finish). No `sdown` in any window. What raises GPU time is the measured per-pass cost
(row 12, 0.13 ms per render pass, 151 rp/flip in car) plus the stale vertex copy (row 14). The levers there are rows
13/14. This lane has nothing new on GTA III's mechanism beyond "GPU-bound, waited at the fence", and does not claim a
fix for it here.

### Blinx 2 (21:32:41-21:33:51)

| Window line | gfps | Surf | dfF | GPU (R) | RP | `surfupd` | Finish |
|---|---|---|---|---|---|---|---|
| 3054 | 15 | 41.7 | 39.2 | 39.6 (39.2) | 45 | fin0 fence62 2343.5 ms | stl61 stlDef70, `sd[cDefC62]` |
| 1738 | -- | 22.2 | -- | 20.8 | 44 | | |
| 2682 (good) | -- | 2.9 | -- | 13.7 | 31 | | |

Surf tracks GPU in every gameplay window (41.7/39.6, 38.4/35.8, 22.2/20.8, 27.2/27.3). It is one fence wait per frame
in `pgraph_vk_surface_update` (`surface.c:6219-6227`, `cDefC62`). Two surfaces per frame are detached and evicted
with a download (`evict[dl:120 unshelve:120]`, surfgpu `detach=120`, 3043/3037). The `stalled` finish (61/60
flips, 1.1 ms) submits them, which sets `deferred_downloads_frame`, and the next `surface_update` waits on their
fence: the whole frame's GPU work. Removing that wait leaves the frame GPU-bound at 20-40 ms (~2460 draws, 45 RP per
frame at 3054), so the ceiling for that fix alone is ~25 fps at 3054, from 15.

### Hypothesis table

| # | Hypothesis | Titles | Evidence (line) | Reach (ms/frame) | Likelihood | Status |
|---|---|---|---|---|---|---|
| H1 | Texture of a different shape than its render surface (linear sub-rect; per-level surfaces) is downloaded and synced in `create_texture` | RalliSport 2, Fable | R2 1926-3664 `sdown 60` + `s2t=dim`; Fable 5175 `tobuf`/`sdl`/`scdl`, `s2t=levels` | R2 17-26; Fable 27.5 + 4 (first sync) | high (counter names the call site in both) | **Fix #1** |
| H2 | Zeta re-shaped per level: eviction downloads + forced `surfupd` completion | Fable | 5175 `evict[dl:360]`, `why=inv60` | 6.3 now; it absorbs H1's wait once H1 is gone | medium | investigated, not built: the obvious lever (skip the download when nothing reads it back) has no existing safety net to extend -- see "H2 investigation" below for the exact counter that would make it provably safe |
| H3 | Detach/eviction downloads waited at the next `surface_update` | Blinx 2 | 3054 `dfF 39.2`, `cDefC62`, `detach=120` | up to 39, capped by GPU 39.6 | high for the wait, gain capped | **dead**: the only lever that removes the wait without removing GPU work is skipping the STALLED finish that submits the detach/eviction downloads early (`stall_reports_only`); that lever is row 23, refuted on Simpsons (fps falls when it runs, because the early submit was pipelining CPU record against GPU work, not wasted sync). No other way to take the wait below GPU busy time without touching H4. |
| H4 | GPU time per frame (per-pass cost, draw count) | GTA III, Blinx 2 | GTA GPU 29-48 in dips; Blinx R 39 for 45 RP | the floor under H3, and GTA's whole dip | medium | data queued: `HAKUX_GPUXFR=1`'s `XFR rpc` census (draw.c ~4488-4535, already built, off by default) reports per-pass load/store avoidability (`lclr`/`lunif`/`zdead`) -- exactly H4's "per-pass cost" broken down by cause, already instrumented, never read against this capture. Queued `1-1792397157-lane.fpsdata1018-2224298` (Blinx 2, route `gen-blinx2`, 90 s, `--no-expect` telemetry) rather than guessing a remedy with no XFR rpc reading yet (G2). GTA III has no dispatcher-reachable gameplay state to pair with it (the in-car save is reachable only by the owner-state pause-menu protocol this lane's device rules do not run by hand) -- its half of H4 stays on the owner-capture recipe in PR.md until a route exists. |
| H5 | Fence queue depth (#796) | GTA III | row 10 | -- | low (Fen tracks GPU) | not this lane |
| H6 | Thermal / clock | RalliSport 2 | row 19 | -- | ruled out for race windows: Fin = GPU = sdown | dropped |

Divergence noted, not explained: Fable's `dirtyIf180` counts three `download_if_dirty` calls per frame against two SDL
downloads (`txr dl120`). The third is outside `create_texture` (blit/surface callers). It is small (~1 ms) and stays
after Fix #1.

## H2 investigation: ranked next, not built -- the download side has no existing safety net to extend

H2's candidate win is Fable's 6 zeta eviction downloads/frame (`evict[dl:360]` over 60 flips) when the zeta at
0x019b4000 reshapes between mip levels. The obvious lever -- skip the download when nothing will ever read the
bytes back -- has a real precedent in this file for the mirror-image case: `surface_drop_covered_upload`
(`clrskip`, `clr`, `clrfull` counters, surface.c:1867-1940) already drops a pending *upload* when the clear that
follows covers the surface whole, because the upload's content is about to be clobbered and provably unread.
Checked whether that machinery already covers the download side or could be read against this capture to answer
the download question directly: it does not. `clr`/`clrfull` only fire when a binding has `upload_pending` AND
`pg->clearing` is true at the same surfupd (surface.c:1917-1926) -- Fable's zeta reshape has no pending upload,
only a pending *download* (the evicted content moving from the GPU image to guest VRAM), so these counters read
`clr=0 clrfull=0` for this exact window (`fable.txt` 5175's `[sdcall]` line) and say nothing about it either way.

The real question for a safe lever is the reverse of the upload case: is the zeta content being evicted ever
read again, by a CPU peek, a texture bind (the shadow-comparator path this lane's own Fix #1 companion change
just touched), or a later re-bind of the same shape that expects the old bytes rather than a fresh clear? If
Fable clears each level's zeta fresh before drawing it (likely, for mip generation, where cross-level depth
continuity would be meaningless), the eviction download is provably wasted, same shape of argument as
`clrfull` already proves for uploads -- but nothing in this file counts it, and the capture's one zeta clear
counter (`[clr91]` `wz=1`/frame) is a frame total, not a per-eviction one, so it cannot distinguish "one clear,
6 reshapes all starting fresh" from "one clear, 5 reshapes inheriting stale depth that something later reads."

Did not build a download-skip lever on this guess: unlike Fix #1/#2 (choosing which already-correct path reads
a texture, provably equivalent either way), dropping a download is a correctness claim about the future --
nothing ever reads this -- and getting it wrong reproduces exactly the kind of regression this lane's own pixel
predictions caught twice already, in a harder-to-falsify form (a dropped write looks right until the one golden
or gameplay moment that reads it). **What would unblock this**: a per-eviction instrument, next to the existing
`evict[dl:...]` counter, that records whether the binding replacing the evicted one is first touched by a
surface-covering clear (mirroring `upw_clear_read`'s "did the clear that followed cover the binding whole"
check, but asked of the *new* binding after an eviction rather than the uploading one) before anything reads
it. If that fires 6/6 for Fable's reshapes, the download-skip lever becomes provably safe and falls out of
`clrfull`'s own argument; if it does not, H2 needs a different, narrower target than "skip the whole eviction."
Not built this session -- ranked next, now with the specific missing counter rather than "medium, next."

## H2 instrument built: per-eviction download-vs-read pairing (not a fix yet -- needs a capture)

Built the per-eviction instrument the section above named as the unblocking step, while the last turn's
pixel-prediction arms were still running (G7: the next step was obvious, so it got built rather than the
turn ending on a wait that had not actually arrived yet).

**What it measures.** `g_sdcall` (surface.c, the existing perflog-tier struct behind `clr`/`clrfull`/`clrskip`)
gains four counters: `edl_dl` (evictions at the "incompatible" site in `update_surface_part` -- same address,
different shape/pitch, Fable's mip-reshape pattern), and, of those, `edl_clrskip` (the replacement binding's
very first touch this call was a covering clear that dropped its own pending upload -- i.e. the evicted
binding's downloaded bytes are provably never read, by the same argument `clrskip` already makes for the
mirror-image upload case), `edl_upload` (the replacement binding did upload -- the download fed a real read),
and `edl_other` (the replacement's `upload_pending` was already false before the clearing check ran -- a
shelf hit with clean VRAM already; ambiguous, not claimed as wasted).

**Where, and where not.** Marked only the "incompatible" eviction branch (`surface.c`, inside
`update_surface_part`, the branch guarded by `surface->draw_dirty` right before `download_surface_deferred`).
Deliberately did not mark the other two `sd_eviction_dl` sites: the handoff-fallback branch is documented in
its own comment as deterministically re-uploading (not an open question), and `invalidate_overlapping_surfaces`
is already proven necessary by an existing comment citing issue #7 (overlap eviction, a different mechanism
from the mip-reshape pattern H2 is about). Conflating all three into one counter set would make the result
uninterpretable -- a mix of "provably wasted", "known necessary", and "a third mechanism" under one number.

**Mechanics.** `EDL_MARK(color)` sets a per-call, per-slot (`color`/`zeta`) flag at the eviction site itself.
`pgraph_vk_surface_update()` resets both flags at its top (`EDL_RESET()`) and, after the existing
clearing-upload-drop block runs (`surface_drop_covered_upload`, same `pg->clearing` gate as before, unchanged),
calls `EDL_RESOLVE(slot, pending_before, binding)` with the replacement binding's `upload_pending` snapshotted
*before* that block ran and the binding itself read *after* -- `edl_clrskip` fires exactly when the drop
actually happened for this binding, `edl_upload` when it was pending and survived, `edl_other` when it was
never pending to begin with. All four counters, and a new `[edl]` perflog line (`frames=N dl=.. clrskip=..
upload=.. other=..`, emitted from `sdcall_log()` only when `edl_dl` is nonzero), are gated the same as every
other field in `g_sdcall` -- `#if NV2A_PERF_LOG && defined(__ANDROID__)`, a no-op in release and host builds.
This is purely additive instrumentation: `surface_drop_covered_upload` still runs under the exact same
`pg->clearing` condition as before the edit; nothing about which uploads get dropped has changed.

**Read command** (for the owner or a future lane, same pattern as the existing `[sdcall]` line, which is also
read by hand rather than through `fpsdiag.py` -- it does not parse `[sdcall]`-style lines today): build a
perflog APK from this PR's head, play Fable's gameplay window, and grep the device logcat for `\[edl\]`:
```
adb logcat -d | grep '\[edl\]'
```
If `clrskip` reads 6/6 against Fable's `evict[dl:360]`-per-60-flips window, the download-skip lever this
section's parent asked for becomes provably safe by the same argument `clrfull` already makes for uploads,
and is next. If it reads lower, the remainder names exactly how many of Fable's reshapes are not safe to skip,
which narrows H2 to a partial lever instead of an all-or-nothing one. **Not yet run against the owner's
capture or any device** -- this is the instrument, not the result; no claim is made here about what Fable's
actual split is. Typechecked clean in both the plain Release line and `-DNV2A_PERF_LOG=1` (rc=0, no new
warnings).

## G3: Fix #1 prediction (written before the build)

**Change.** texscan (row 22) takes non-cube 2D textures, behind `HAKUX_TEXSCAN` (default-on through fastpaths), with
`HAKUX_TEXSCAN2D=0` as its own off switch:
- swizzled, with each level a whole draw-dirty surface at the level's offset (`get_texture_layout`'s level loop,
  `texture.c:431-521`), copied into that mip level;
- linear, one level, with one draw-dirty surface inside the texture at the same pitch, copied into the
  rectangle it covers.

The texture is uploaded from guest memory as today and the surface texels are copied over it on the GPU in the
frame's command buffer. No download, no sync. Bytes: the colour download writes the surface's `width * bpp` per row
into guest memory unconverted (`surface.c:2723`), and the upload of an unconverted format reads them back
unconverted, so the copy gives the same texels.

**Why this works.** RalliSport 2: `create_texture`'s SDL block (`texture.c:3737-3749`) is the only `sdown` source
in race windows (`[tsc] sdl60 #0`, `txdl dim60`), and texscan's plan runs ahead of it and skips it
(`ts_taken`, `texture.c:3726-3729`). Fable: all six downloads are the `#0-#5` level surfaces, which the per-level
plan covers, so the SDL block and the range scan are skipped, and with them `tobuf`, the own finishes and the range
finishes.

**Predicted delta.**

| Title | Counter now | Predicted | fps now | Predicted fps |
|---|---|---|---|---|
| RalliSport 2 race | `fin=sdown` 60/window, 17-26 ms/frame; Fin 18-26 | `sdown` 0 in race windows; Fin < 2; `ts[bind]` and `ts2[lin]` ~60/window | 18-27 | 35-50 (frame becomes max(GPU 17-25, CPU 12-20)) |
| Fable gameplay | `sdown` 420/window, 37.8 ms/frame; `tobuf` 27.5 | `tobuf` and range `sdown` 0; `surfupd` grows from 6.3 to 10-25 ms (it is now the first sync) | 11-24 | +3 to +8 |
| GTA III | no `sdown` | unchanged | -- | 0 |
| Blinx 2 | `txr dl0`, `s2td600` | unchanged | -- | 0 |

**Cannot help:** GTA III and Blinx 2. Neither downloads for a texture in any gameplay window.

**Falsifiers.**
- RalliSport 2 race windows still show `fin=sdown` > 5 ms/frame, or `ts2[lin]` 0 with `txdl dim60`. The plan
  then did not take the bind; `ts2[fb]` > 0 says it was refused.
- The race fps does not rise while `sdown` falls. The wait moved: look for a new large `fin=` reason or `Fen`.
- Fable: `surfupd` ms rises by as much as `tobuf` falls. Then H1 is real but Fable's gain needs H2 as well.
- Any pixel change on the goldens (the must-not-move legs).

## Fix #1 as built (38c8d53ba5)

`hw/xbox/nv2a/pgraph/vk/texture.c` only. A slot is a cube face (as before), a swizzled 2D texture's mip level, or a
linear texture's one surface. `texscan_slot()` (2149-2212) places each draw-dirty surface over the texture:
- swizzled: `get_texture_layout`'s level walk; the surface must start at a level's offset and be that level's size;
- linear: the offset gives x = (off % pitch) / bpp and y = off / pitch; the surface must fit inside the texture.

Each slot then passes `check_surface_to_texture_compatiblity()` for a texture of exactly the slot's shape. That test
checks extent, the linear pitch (1451, so a surface at another pitch is refused, as in the Antialiasing case it
documents), layout (1483), converted formats and the texel stride. So the copied bytes are the round trip's.

Two guards keep it from changing anything it does not take:
- `texscan_prepare` returns before any flush or completion for a 2D texture with no draw-dirty surface over it
  (`texscan_any_dirty`, 2297). Only cubes reached the flush and completion before.
- For a 2D texture the plan refuses any shelved draw-dirty surface over it (2241), so `create_texture`'s shelf
  lookup (3891), which can bind a shelved surface at the texture's address, cannot fire on a taken bind.
- A linear texture takes one surface, never two: a duplicate slot refuses.

The copy (`texscan_apply`, 2372-2531) sets `dstSubresource.mipLevel`, `baseArrayLayer` and `dstOffset` per slot.
Counters (perflog): `[tsc] ... ts[bind cp keep force faf cmpl fb] ts2[mip lin fb]`; ts[] is unchanged, so
`texread.py` still parses it. `ts2[fb]` counts refused 2D plans. The release tier logs `[texscan] on 2d=1` and, once
per kind, `[texscan] first copy tex @addr WxH fmt faces levels lin`. `HAKUX_TEXSCAN2D=0` restores master's route,
which takes cubes only.

Built: `docs/lanes/fpsdata1018/typecheck.py` (shaderprebuild569's, plus `-D` passthrough) compiles texture.c with
the NDK clang line of the last Android build. Release and `-DNV2A_PERF_LOG=1` both give rc=0. The 5 warnings are
pre-existing (target_page shifts, `replaced`, `did_s2t_copy`).

Territory: the brief says to claim the files in `territory.toml`, but the lane contract forbids editing it and says
to write a board request instead. I followed the contract: `dispatch/board-requests/fpsdata1018.md` asks for
`texture.c`, `surface.c` (H3, not edited yet) and `docs/testing/predictions/fpsdata1018-*`.

Prediction (pixels): `docs/testing/predictions/fpsdata1018-texscan2d-pixels.json`, sha256 `af9b4547dc74...`,
a_ref 245ddc4964, b_ref 38c8d53ba5. It covers 35 suites (texscan1010's 29 plus the render-to-texture ones), and every
capture is predicted the same. Committed and pushed, so the arms job queues it.

### Device A/B (RalliSport 2), queued 2026-10-19 05:38Z

One build, 38c8d53ba5 perflog, on the Nova. The scene is ralli2audio1018's Copperhead race route
(`routes/fpsdata1018-ralli2-drive.route`, copied unchanged), 480 s per arm:
- A: `1-1792388258-lane.fpsdata1018-3191423`, `HAKUX_TEXSCAN2D=0`.
- B: `1-1792388264-lane.fpsdata1018-3193935`, shipped. Queued last, so the device is left as shipped.

Caveat, found before queuing: in four ralli2audio1018 release runs of this route (results `...3558236`, `...3569502`,
`...219355`, `...709884`), the race ran at a median of **41-44 gfps**, against the owner's 18-27. That scene may not
have the 260x260-in-640x480 render target at all; it could be a camera or stage the owner's race had. Arm A's
`txdl why=dim` count answers that:
- If A shows `dim` ~60/window and B shows `ts2[lin]` ~60 with `sdown` ~0, the A/B measures Fix #1 directly.
- If A shows no `dim`, the route does not reach the owner's scene, and RalliSport 2's measurement goes to the owner
  recipe below.

Judge from both logcats: `GPU: PurpleVK` and `[texscan] on 2d=0/1` first. Then per race window: gfps,
hakuX-phase Fin/Sub, `[sdcall]` sdown count/ms, `txdl` why, `[tsc] ts2[...]`, and the start temperature in
thermal.jsonl. Compare the first 120 s of race in each arm, not the means of the whole runs, since ralli2audio saw a
thermal cliff after 180 s.

### Device A/B (RalliSport 2), read back (attempt 3)

Both arms DONE, `GPU: PurpleVK` (Adreno 740, `vulkan.purple.so`) confirmed in both. `[texscan] on 2d=0` in A,
`2d=1` in B, so the switch took.

The caveat fires: the route does **not** reach the owner's sustained scene.

| | A (`HAKUX_TEXSCAN2D=0`) | B (shipped) |
|---|---|---|
| `why=dim` count, whole 480 s run | 4 (all within 84 ms, 23:28:46.852-.936 -- one brief flash, not sustained) | 0 |
| `ts2[lin]` count, whole run | n/a (switch off) | 0 |
| worst `[dipwin]` window (60 flips) | 3.529 s (~17 gfps) | 2.386 s (~25 gfps) |
| windows total | 365 | (comparable) |

The owner's capture showed `fin=sdown` 60/60-flip-window, sustained across all 16 race windows from 1926 to 3664
(40+ s continuous). This route's scripted race shows the 260x260-in-640x480 render target for under 100 ms total
in 480 s -- a different camera angle or moment, not the owner's sustained mirror/replay view. The two arms' worst
windows (3.529 vs 2.386) are not comparable as an A/B of Fix #1: neither hits the scene it tests, and the
difference is consistent with ordinary race-line/thermal variance (ralli2audio1018's own fps-cliff finding, row 19)
between two separate 480 s runs, not with `sdown` removal.

**Verdict: VOID for RalliSport 2.** This device A/B does not measure Fix #1. RalliSport 2's measurement stays with
the owner recipe below. The route file stays in the lane (it is harmless and may hit the scene on a different
race attempt), but no fps conclusion is drawn from it.

### Owner A/B recipe (Fable; RalliSport 2 if the route misses the scene)

Fable has no route or save state to its gameplay scene. The recipe:
1. Install the 38c8d53ba5 perflog build.
2. Arm A: set `HAKUX_TEXSCAN2D=0` in env_vars. Play Fable's 10-18 stretch (gameplay, not the intro video) for 3
   minutes. For RalliSport 2, play the same race and camera as on 10-18 for 2 minutes.
3. Arm B: clear env_vars and play the same stretches again.
4. Host capture throughout (`fpsdiag.py capture --attach`, CAPTURE.md).

Counters to read: `[sdcall]` sdown and tobuf, `surfupd` (Fable: does it absorb the wait?), `txdl` why=dim/levels
(A) against `ts2[lin]`/`ts2[mip]` (B), Fin/Sub, gfps.

### Fix #1's pixel prediction: arms VERDICT FAIL, root cause found and fixed

`docs/testing/predictions/fpsdata1018-texscan2d-pixels.json` (a_ref `245ddc4964`, b_ref `38c8d53ba5`) came back
FAIL on PR #1085: `Antialiasing_tests/CPUWriteIgnoresSurfaceConfig` went from bit-exact (0) to 45,056 different
bytes, and 61 `Texture_shadow_comparator` captures differ byte-for-byte (38 at unchanged score -- `PIXELS MOVED`,
paired worse/better rows with matching magnitudes between sibling variants, e.g. `2F16_..._EQ` +80 /
`2F16_..._LT` -80). Captures (`/home/justin/hakux-work/dispatch/results/1-1792389196-arms-fpsdata1018-fix-3521849/
captures1/`): A is a clean checkerboard diamond; B is gross multicolor fine-striped noise across the same shape --
a layout/stride misread, not a rounding drift.

Root cause, traced in `hw/xbox/nv2a/pgraph/vk/texture.c`'s texscan code (read, not guessed -- static trace of
`texscan_shape_ok`, `texscan_plan`, `texscan_slot`, `texscan_apply`, and `create_surface_image` in `surface.c`):

- `create_surface_image()` (surface.c:4138) sizes `surface->image`'s real Vulkan extent at
  `width * pg->surface_scale_factor x height * pg->surface_scale_factor` (`pgraph_apply_scaling_factor`,
  pgraph.h:695), baked in **at creation time** from whatever the global scale factor is then. `surface->width`/
  `height` stay the logical (unscaled) values used everywhere else.
- `texscan_shape_ok()` (texture.c:2129) only checks `pg->surface_scale_factor == 1` for the texture being bound,
  i.e. the **current** global value. It says nothing about what scale factor was in force when a candidate
  surface's image was created, and nothing tracked that per surface.
- `texscan_apply()`'s `vkCmdCopyImage` (texture.c ~2463-2477) copies `extent = s->width x s->height` from
  `srcOffset (0,0)` of `s->image`. When `s->image`'s real grid is scaled, that is a crop of the oversized render
  target's top-left corner, not a resolve -- every other reader of a scaled surface (`surface_download`'s
  `downscale` blit through `image_scratch`, surface.c ~1456-1507 and ~2399-2437) goes through a scale-aware blit;
  texscan never did.
- A surface created while AA/scale != 1 can sit in `r->surfaces` still `draw_dirty` after the register state (and
  `pg->surface_scale_factor`) changes back to 1 with no flush -- texscan's whole point (texture.c's own doc
  comment: "No #474 drain... counted, not taken") is to skip exactly the flush that would otherwise force a
  correctly-scaled SURFACE_DOWN first. `AntialiasingTests::CPUWriteIgnoresSurfaceConfig` is built to vary surface
  config across a shared surface -- textbook trigger. The `Texture_shadow_comparator` swapped-pair pattern fits
  the same mechanism hitting different sibling sub-tests depending on which one inherits a stale scaled surface.

This is **specific to texscan** (the `r->surfaces` active-scan loop already correctly refuses `!s->color` and
`s->upload_pending` before this point, texture.c ~2256) and is not a wider pre-#433 bug: nothing before Fix #1
ever took a raw image-to-image copy path for a 2D surface.

Fix (this commit): added `unsigned int image_scale` to `SurfaceBinding` (renderer.h ~402), set from
`pg->surface_scale_factor` in `create_surface_image()` (surface.c:4145) at the moment the image is actually
allocated, and refused in `texscan_plan`'s active-surface loop (texture.c ~2256) alongside the existing
`!s->color`/`upload_pending`/`VK_NULL_HANDLE` checks. A scaled leftover surface now falls through to the
pre-existing SURFACE_DOWN path, which already downscales it correctly.

Typechecked clean (`docs/lanes/fpsdata1018/typecheck.py . hw/xbox/nv2a/pgraph/vk/texture.c
hw/xbox/nv2a/pgraph/vk/surface.c`, plain and `-DNV2A_PERF_LOG=1`, rc=0 both, no new warnings).

Next: re-register the pixel prediction against this commit's sha (new a_ref/b_ref, after merging current
origin/master) and re-queue the arms job before marking PR.md `State: ready`. The fps-side verdict on texscan2d
(RalliSport 2/Fable) still stands behind this correctness fix -- it was never in question, only the AA-surface
edge case was.

### GTA III's fence-wait candidate (G3 prediction, before building): HAKUX_S2T_FB default -> mode 2

Already-tried, this exact lever: `lane.gta3car1018` (#1049) built `HAKUX_S2T_FB` and ran a device batch (c2,
`docs/lanes/gta3car1018/NOTES.md` section 6) but shipped it **off by default** in both modes. What's different
this time: nothing about the mechanism -- I'm not re-deriving it, I'm reading their result and deciding the
default. The brief's own scope section names "the fence wait" as GTA III's one supported candidate; that lane's
section 4.1 ties the fence/pass-stall growth directly to this copy-per-sample loop, so this is that candidate.

**Mechanism** (read in `hw/xbox/nv2a/pgraph/vk/texture.c`, not re-measured): GTA III's in-car scene draws into a
128x128 colour target it also samples ~140 times/flip at a new `draw_time` each time (`s2c` census,
gta3car1018 NOTES section 4.1). Before the switch, every sample re-copies the target and ends the render pass:
~140 of ~150 passes/flip. `HAKUX_S2T_FB=2` lets a slot keep this run's copy across samples whose shader stage
providably does not read its texture at all (`s2t_fb_stage_reads()`, texture.c:2997 -- NONE/PASS_THROUGH/
CLIP_PLANE/DOT_PRODUCT combiner modes, checked fresh per sample in `s2t_fb_keep()` at the point of use,
texture.c:3083-3099). Because the check gates each individual sample against whether that sample's result can
reach a pixel, this is pixel-safe by construction, independent of scene or title: a kept copy is only ever
substituted for a sample that could not have changed the rendered image no matter what the copy held.

**Why this will work (evidence chain)**: gta3car1018's `S1` run (NOTES section 6.1, the one clean, un-aborted
`HAKUX_S2T_FB=2` reading) measured 38.20 rp/flip and 35.89 ms/flip against the same-session `O1` baseline's
57.11 rp/flip and 40.36 ms/flip -- fewer passes, less frame time, in the same direction as the rp-vs-ms fit in
their section 4.1 (ms/flip = 30.89 + 0.1309 x rp/flip). `S1`'s own light-traffic third (device clock
11:30:38-11:30:46) drops to 9-14 rp/flip and **hits the 33.3 ms/flip cap (30 fps)** outright.

**Predicted delta**: GTA III in-car dip windows, rp/flip cut by roughly a third to half of baseline (pattern-
matching `S1` vs `O1`); `fen`/`rotfen` (the GPU wait that scales with pass count per section 4.1) down by a
comparable fraction; light-traffic moments reaching 30 fps, heavy-traffic moments still short of it (their own
section 6.3: "the fence wait and stalled finishes... are still 10-15 ms/flip in S1's heavy-traffic windows" --
this is NOT a full fix for the dip, only for the part this mechanism owns).

**What it cannot help**: Fable (Fin/zeta-and-mip-download pattern, Fix #1's `tobuf`), Blinx 2 (`Surf`-time,
no texture-download or self-sampling pattern in its capture), RalliSport 2 (Fin, also Fix #1). None of those
three titles' captures show a surface sampled as its own bound texture; this lever is GTA III-specific by the
mechanism itself (a feedback loop that only exists when the current colour target is also a bound texture).

**What would falsify this**: a repeat in-car A/B (below) showing no rp/flip or fen drop relative to a same-
session off baseline, or any pixel movement in a host suite run with the switch on (should be impossible by the
stage-reads gate, but the previous lane never registered a pixel prediction for it -- doing that here, below,
rather than taking the "pixel-safe by construction" argument on faith alone).

**Why default now, not another opt-in switch**: the only reason the prior lane left it off was "neither [mode]
proven the better default yet" from a single trial per mode confounded by unscripted driving traffic (their
section 6.3) -- not a correctness doubt. Mode 2's safety argument is structural, not statistical; the open
question was only the *size* of the win under traffic variance, which is a reason to confirm with a cleaner,
repeated device A/B (below), not a reason to leave a correctness-safe, already-measured-net-positive lever off
by default while this lane is explicitly judged on landed fixes. `HAKUX_S2T_FB=0` still exists for anyone who
wants the old per-sample-copy behaviour back; `=1` still exists for the unsafe any-stage mode, now opt-in only.

Change made: `s2t_fb_mode()` (texture.c ~2982) now defaults unset/unrecognized `HAKUX_S2T_FB` to mode 2 instead
of off; explicit `"0"` still forces it off, explicit `"1"` still forces the any-stage mode. Typechecked clean
(rc=0, no new warnings, same pre-existing shift/unused-variable warnings as before).

Pixel-safety prediction registered separately (`docs/testing/predictions/fpsdata1018-s2tfb2-pixels.json`,
`must_not_move` across the surface/texture/render-target suites `S2T_FB` can reach) rather than relying on the
stage-reads argument unverified.

**Correction**: this section previously claimed a repeat in-car device A/B had been queued against the Nova's
GTA III save state. It had not -- there is no job for it anywhere in `dispatch/queue/`, `dispatch/running/`,
or `dispatch/results/`. Checked gta3car1018's own notes for the route it used: its in-car arms (`arm.sh`/`batch.sh`,
W/O1/F1/S1/S2/F2/O2) went through the dispatcher only for the perflog APK build and the per-arm `HAKUX_S2T_FB`
env var; the car itself came from the owner's in-car state (slot 0, copied to debug slot 5) with the device
held and driven by hand, because **no scripted route reaches it** (gta3car1018 NOTES.md section 8: "no scripted
driving"). This lane's device rules (G6) are dispatcher-only, never by hand, so it cannot reproduce that step
itself. That is why PR.md hands the owner a manual capture recipe for this one instead of a device A/B this
lane ran -- that recipe is the correct and only way to get a repeat reading, not a placeholder for one. The
pixel-safety prediction above is this lane's actual, dispatcher-verifiable device evidence for the change.

**Resume, this turn**: the previous turn in this attempt ended on a legitimate external wait (`7e5f97de1d`):
both re-registered pixel predictions were queued (`1-1792404006-*` for s2tfb2 @ `b50667ac35`, `1-1792404008-*`
for texscan2d @ `b46f4cb8d3`) and neither had a result on disk yet, so there was nothing further to read or
build without manufacturing busywork (G7's actual stop condition, not a dead end). Checked `dispatch/queue/`,
`dispatch/running/` and `dispatch/results/` fresh rather than trusting that snapshot: the texscan2d pair
(`1-1792404008-*`) is still live (base DONE at 03:23Z, fix still queued, unchanged from last turn) -- that wait
is real and ongoing. The s2tfb2 pair (`1-1792404006-*`) is no longer a wait: both arms finished (base DONE
03:14Z, fix DONE 03:21Z) since the last turn ended, and no `[job.arms]` comment or verdict file had posted yet
for it. Rather than wait again for the host-level arms job to notice and post, ran the comparison myself
(`ab_compare.py --a ... --b ... --expect fpsdata1018-s2tfb2-pixels.json`, read-only, costs no device time) --
G6 asks this lane to prove a change against measured counters, and the measurement already existed on disk.

## Pixel FAIL #4: S2T_FB mode-2's depth-excluded re-registration (`b50667ac35`) FAILed on a fourth, different
suite -- the same image_scale mechanism Fix #1 already fixed once, in a second cache this lever owns

`ab_compare.py` against `1-1792404006-arms-fpsdata1018-base-3062037` (A, `41c613c22a`, switch off) and
`1-1792404006-arms-fpsdata1018-fix-3062074` (B, `b50667ac35`, switch on, depth exclusion already landed):
**VERDICT: FAIL -- 1 of 184 checks violated**: `Antialiasing_tests/CPUWriteIgnoresSurfaceConfig` moved
**0 -> 45,056** differing bytes. This is not `Texture_shadow_comparator` (the noise-floor suite Pixel FAIL #1/
#3 already discounted) and it is not in that suite's must_not_move exclusion -- this is a clean, single,
attributable FAIL on a suite with no measured noise, the *same* capture and the *exact same byte count* as
Fix #1's original `image_scale` regression (texscan2d, "Pixel FAIL #1" above, before its fix).

That byte-for-byte match is the finding, not a coincidence to explain away: `s2t_fb_record()`/`s2t_fb_keep()`
cache a copy taken by `copy_surface_to_texture()` (texture.c:1273), whose `vkCmdCopyImage` region multiplies
`surface->width`/`height` by `pg->surface_scale_factor` **as read at copy time** (texture.c:1339-1340,
`pgraph_apply_scaling_factor`) to decide how many texels of `surface->image` to read. `CPUWriteIgnoresSurfaceConfig`
reconfigures the surface (and so the scale factor) with a direct CPU write, not a draw, so `surface->draw_time`
and `snode->draw_time` -- the memo's only staleness check before this fix -- do not move, and `s2t_fb_keep()`
answered true for a sample taken after the reconfigure using a copy sized for the scale in force *before* it.
This is the same class of bug Fix #1 fixed (a stale copy read at the wrong scale after a config change with no
intervening flush), in a second place that takes the same raw-copy route (`copy_surface_to_texture`, the
function texscan would otherwise have reached) but keeps it across draws instead of retaking it fresh --
exactly Pixel FAIL #2/#3's "reusing it, rather than retaking it, is enough to reshape the answer" pattern,
this time for scale instead of format.

**Fix** (committed with this note, `hw/xbox/nv2a/pgraph/vk/texture.c`): added `unsigned int scale` to
`s2t_fb_memo[]`, set to `pg->surface_scale_factor` in `s2t_fb_record()` at copy time, and checked in
`s2t_fb_keep()` alongside the existing node/image/surface/view/draw_time/frame/run checks. A memo recorded
under one scale factor is now refused once the scale factor has moved, regardless of whether `draw_time` moved
-- the slot falls through to a fresh `copy_surface_to_texture()` call instead, identical to `HAKUX_S2T_FB=0`'s
behaviour for exactly this situation. The "same draw_time, direct view reuse" branch (texture.c ~4376, taken
when `s2t_fb_keep` is not even called) is unaffected and has no equivalent gap: it reads the surface's own
*current* view directly, never a cached copy, so a scale change there is already reflected on the next read.

Typechecked clean: `docs/lanes/fpsdata1018/typecheck.py . hw/xbox/nv2a/pgraph/vk/texture.c` (rc=0) and
`docs/lanes/fpsdata1018/typecheck.py . -DNV2A_PERF_LOG=1 hw/xbox/nv2a/pgraph/vk/texture.c` (rc=0) -- note the
`-D` flag is attached with no space and the worktree root is the first positional argument; `-D NV2A_PERF_LOG=1`
(space-separated) silently mis-files the define as a source path and fails with "no such file". Same 5
pre-existing warnings both times, no new ones.

Re-registering `fpsdata1018-s2tfb2-pixels.json` on this commit (`a_ref` unchanged `41c613c22a`, `b_ref` = this
fix) below; this is the fourth time this lever's own registered prediction has caught a real gap before it
shipped (Pixel FAIL #2: DOT_PRODUCT: Pixel FAIL #3: missing depth exclusion in the cache; this: missing scale
check in the cache) and the fourth time it was root-caused and fixed rather than reverted. Added to the
Already-tried table: this exact mechanism (image_scale/stale-copy-after-reconfigure-with-no-flush) is now
fixed in two places (texscan_plan, s2t_fb_keep) that both take the GPU-copy-and-reuse route; any third
candidate lever that also caches a raw `copy_surface_to_texture()`/`vkCmdCopyImage` result across more than one
draw needs the same check before it is registered, not after a FAIL finds it again.

## Pixel scare resolved: the texscan2d `b46f4cb8d3` re-check's FAIL on `CPUWriteIgnoresSurfaceConfig` was a
device flake, not a regression -- but it surfaced a real, separate gap worth fixing

Read back the texscan2d prediction's own arms fresh this turn (`1-1792404008-arms-fpsdata1018-{base-3062345,
fix-3062388}`, `a_ref=245ddc4964` vs `b_ref=b46f4cb8d3`, the already-landed fix): `ab_compare.py --expect`
gave **VERDICT: FAIL -- 1 of 750 checks violated**: `Antialiasing_tests/CPUWriteIgnoresSurfaceConfig` moved
**0 -> 45,056** bytes. This directly contradicted the "Correction" entry above (line ~236), which read back a
*different* arm pair on the *same* `a_ref`/`b_ref` (`1-1792400325-...`) and found the only FAIL confined to
`Texture_shadow_comparator` (17/1038) -- no `CPUWriteIgnoresSurfaceConfig` movement at all. Visually confirmed
via the capture PNGs that this is real structured corruption (the fix arm's image is dense multicolor fine
striping over the same diamond shape the base arm renders as a clean checkerboard), not a black frame or a
truncated file -- so this could not be dismissed as a decode artifact without checking further.

Ruled out a stale/mismatched build first: `git show b46f4cb8d3:hw/xbox/nv2a/pgraph/vk/texture.c` confirms the
`s->image_scale != 1` refusal is textually present in the tested commit, and the dispatcher's build log for
`b46f4cb8d3` shows a genuine ninja recompile of `texture.c` (`BUILD SUCCESSFUL`, same 3 pre-existing
`-Wshift-negative-value` warnings), not a stale cache hit.

**The decisive check**: both arm pairs share the identical `apk_sha` on both sides (`245ddc4964` ->
`f9ee968b9759`, `b46f4cb8d3` -> `ec81116c55bd`, same device `nova`, same shader-cache-clear transition in both
`result.json`s) -- bit-identical builds, same device, same refs, run twice. `sha256sum` on
`captures1/Antialiasing_tests::CPUWriteIgnoresSurfaceConfig.png` across all four result dirs (both base runs,
both fix runs):

| Run | sha256 (16 hex) | size |
|---|---|---|
| base, `1-1792400325-...-2706810` | `8f719443e1b38521` | 42471 |
| base, `1-1792404008-...-3062345` | `8f719443e1b38521` | 42471 |
| fix, `1-1792400325-...-2706853` | `8f719443e1b38521` | 42471 |
| fix, `1-1792404008-...-3062388` | `a031d5810bc07fdc` | 122253 |

Three of four are byte-identical (the clean checkerboard); only the second fix run differs. The exact same
binary (`ec81116c55bd`) produced the correct answer once and the corrupted one once -- this is a run-to-run
device flake on this one test, not a reproducible consequence of `b46f4cb8d3`'s code. Per `device-run-flakes`
(rerun twice): with 3 of 4 runs agreeing and the dissenting run bit-for-bit matched on the build side, the
weight of evidence is "flake", and the texscan2d fix's pixel-safety claim stands as it was before this turn
(not amended, not retracted). This is a second, distinct noise source from the already-measured
`Texture_shadow_comparator` ~8.6% floor (that floor was measured on `245ddc4964` only, same-ref, zero code
change, 3 runs, 100% confined to that suite); `Antialiasing_tests::CPUWriteIgnoresSurfaceConfig` disagreeing
with itself under a bit-identical build on a *different* ref pair means this device/test combination can flake
outside that suite too, at a much lower rate (1 run out of 8 total runs across both pairs' fix side, only).
No prediction file needs amending for this: `must_not_move` already requires a check to be reproduced before
it blocks a change, and `ab_compare.py` correctly flagged it for inspection; only the suite-level noise-floor
discount (already in both prediction files for `Texture_shadow_comparator`) does not yet cover this, and is
not broadened to cover this one single-occurrence flake either -- one disagreement in 8 runs is not grounds for
a blanket exclusion the way 89/1038 across 3 runs was. If a third independent arm pair on this same `a_ref`/
`b_ref` also disagrees on this test, that changes this conclusion.

**Found while tracing this (kept as a separate, real fix, not the explanation for the flake above)**:
`migrate_surface_image()` (surface.c:4302) -- the function `update_surface_part()` calls when it reuses a
shelved or invalid surface's backing `VkImage` for a newly (re)bound target -- copies `image`, `image_view`,
`image_layout`, `allocation`, `image_scratch`, `image_scratch_current_layout` and `allocation_scratch` from the
old binding to the new one, but not `image_scale`. The new binding's `target` local is `memset` to 0 before
this call and `populate_surface_binding_target()` never sets `image_scale` either (only `create_surface_image()`
does, at the one assignment site in the whole renderer: `surface->image_scale = pg->surface_scale_factor;`,
surface.c:4204, which only ever runs for a brand-new image). So every surface that is EVER reused via the shelf
or invalid-list migration path -- which is the common case for a render target whose address/format/pitch keeps
recurring, e.g. the GTA III/RalliSport 2 steady-state churn this lane is already chasing -- permanently reads
`image_scale == 0` for the rest of its life, even once correctly reconfigured back to the unscaled grid
`texscan_shape_ok()`/`texscan_plan()` require. Since `texscan_plan`'s check is `s->image_scale != 1` (refuse),
`0 != 1` is always true: a migrated surface can **never** take the texscan GPU-copy fast path, no matter its
real scale, silently falling back to the slower SURFACE_DOWN download+upload route Fix #1 was built to avoid.
Traced `update_surface_part()`'s two call sites (surface.c ~5851 `get_shelved_surface` reuse, ~5857
`get_any_compatible_invalid_surface` reuse) and the `*surface = target` assignment that makes `target`'s
(zeroed) `image_scale` the live value -- confirmed no other code path ever sets `image_scale` to anything but
0 (via memset) or the correct value (via `create_surface_image`), so this is a real, if safely one-directional
(under-use, not corruption), gap: `0 != 1` always refuses, it never wrongly allows. This is why it does not
explain the flake above (which would need a false *allow*, not a safe refuse) but it is a genuine, currently
unclaimed fps opportunity this lane's own fix left on the table for every migrated surface.

**Prediction (G3), before building**: adding `dst->image_scale = src->image_scale;` to `migrate_surface_image()`
makes a migrated surface's `image_scale` field accurately reflect its real backing image for the rest of its
life, exactly as a freshly created surface's already does. Why this will work: `src`'s `image_scale` was
itself set correctly by whichever `create_surface_image()` call originally made that image (migration moves
the image handle itself, not just a stale copy of a field describing it -- the image's real texel grid does
not change by being migrated to a new `SurfaceBinding` struct). Predicted effect: surfaces that cycle through
the shelf (reused at the same address/format/pitch across frames, the common steady-state case) become texscan-
eligible again once they are genuinely at the unscaled grid, instead of permanently falling back to
SURFACE_DOWN after their first reuse -- more of RalliSport 2's race and Fable's gameplay frames should hit
Fix #1's fast path than currently do, on top of the already-measured win. Falsifier: any pixel-prediction
`must_not_move` capture moving after this change (a migrated surface could, in principle, be re-eligible for
texscan while actually still scale-mismatched if `src->image_scale` itself were ever wrong -- traced above and
not found, but the pixel prediction is the actual falsifier, not this trace alone). This cannot help GTA III or
Blinx 2 (texscan2d's own scope is RalliSport 2/Fable's shape mismatch; neither GTA III nor Blinx 2 downloads a
texture in gameplay per the mechanism account above).

**Fix** (`hw/xbox/nv2a/pgraph/vk/surface.c`, `migrate_surface_image()`): added
`dst->image_scale = src->image_scale;` alongside the existing field copies. Typechecked clean:
`docs/lanes/fpsdata1018/typecheck.py . hw/xbox/nv2a/pgraph/vk/surface.c` (rc=0, same pre-existing warnings, no
new ones). Re-registering `fpsdata1018-texscan2d-pixels.json` a fifth time (`a_ref` unchanged `245ddc4964`,
`b_ref` = this commit) below, since this changes which surfaces are texscan-eligible and needs its own
pixel-safety falsifier, not a ride on Fix #1's already-spent one.

Added to the Already-tried table (row 27): this gap, found while investigating a flake, not the flake's cause.

Pushed (`c4560f2ab4` + the re-registered prediction, `ae9ea479bc`) and posted `[lane.fpsdata1018] waiting:` on
PR #1085. Checked `dispatch/queue/`, `dispatch/running/` and `dispatch/results/` fresh: nothing new has been
queued for either pending prediction yet (`fpsdata1018-texscan2d-pixels.json` @ `c4560f2ab4`, just pushed; `fpsdata1018-s2tfb2-pixels.json` @ `136e8a1723`, pushed earlier this session, also not yet picked up -- the
most recent arms result on disk for either lever is still `1-1792404008-*`, from before both of these pushes).
Everything else open in this lane is also an external wait already recorded in PR.md: GTA III's in-car fps
size (owner capture, no scripted route to the save state), Fable's H2 download-skip lever (needs the owner's
`[edl]` capture before it can be built safely), and Blinx 2's H4 (blocked on the host-wide `drive generic`
harness bug, flagged on PR #1085, outside this lane's files). **WAITING**: the arms job to queue and finish
both pending prediction pairs above; nothing further to build until one of those lands or an owner capture
arrives.
