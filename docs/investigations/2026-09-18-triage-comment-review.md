# lane.triage -- comment-review pass 1

Standing lane, territory wave 85 (`fc6129b01b`). Read-only: I have edited
neither `docs/testing/nv2a_issues.toml` nor `territory.toml`.

Scope: all 31 open issues (`gh issue list --state open`) plus closed #78 and
#82 where an open row depends on them. Every claim below was verified against
the tree at the ref named beside it, not taken from the comment.

**Dating note on my own evidence.** I snapshotted the tracker at
`f343580647`. While I was reading, the orchestrator committed `391ac6bfb9`
("board: M1 is fixed") and `fc6129b01b`, which rewrote six entries (#44, #77,
#84, #88, #89). I re-read those five at `391ac6bfb9` and **dropped one finding
I had against #84**, which that commit had already fixed. Nothing below rests
on the stale snapshot.

---

## 1. #43 -- CLOSABLE, and the result is invisible on the board AND on the issue

**This is the item I would act on first.** It is a 1.81-million-pixel closed
result that neither the tracker nor the issue records, and it retires an
instrument and a not-yet-filed defect at the same time.

**The issue's last comment is a bare unexpanded file reference.** Comment of
2026-09-13T23:23:26Z on #43 is, in its entirety:

> `@/tmp/claude-1000/-home-justin-hakuX/afb31e59-6fc4-4685-81b2-b4db438e1cf3/scratchpad/done.md`

The content was never posted. The file still exists on this host (4,611 bytes,
mtime Sep 13 16:23) and is in a session-local scratchpad, so it will vanish
with the session directory. It contains:

> `better 30  worse 0  same 126  noise 0` / `differing 4,644,590 -> 2,833,490
> (-1,811,100)` / `VERDICT: PASS -- all 126 registered checks hold.`

Arms `d99be2b35d -> 86a1c53195`, thor, prediction bound at queue time.

**Verified landed at HEAD**, not taken on report: `86a1c53195` ("#43 ring 0 root
cause -- a cache key on a register the cache does not watch") *is* an ancestor
of HEAD, and the mechanism it describes is live -- `DECL(S, signedBlendPass,
int, 1)` at `glsl/psh.h:205`, the runtime gate at `glsl/psh.c:3462`, and the
`signed_blend_fold` field gone from `PshState` (only the comments at
`psh.h:82/95` and `vk/draw.c:424` remember it).

**What the tracker should say.** #43's `status_note` currently ends:

> "The sign fold remains -- 365,491 channels per capture, a defect with a known
> rule that provably cannot be blend state"

That is five days stale. Both halves are now closed by measurement: the factor
half (`ab4a829316`, already recorded) and the sign fold (`86a1c53195`). Four
further things from the same result, each worth its own line:

- **`fold alone = 0` and `unexplained = 0`.** The `fold alone 54,015` recorded
  earlier was the stale-shader bug, so **the second blend defect that was about
  to be filed does not exist.** Recording a negative that stops a filing.
- **The residual is #78's entirely**, and #78 is CLOSED `fixed-verified`. So
  #43 has no residual of its own: `Texture_signed_component_tests`, the suite
  built to isolate this defect, is bit-exact on all three captures.
- **The `[signfold]` counters' retirement condition is MET.** #43's own
  `blocked_on` says "reading `staged_high` off an arm RETIRES the [signfold]
  counters". The arm reads `staged_high=5376`, and `staged_low` fell
  `36,339 -> 5,376` (exactly `folds`). They can go.
- **An instrument is now stale in the dangerous direction.** The region tool's
  `LEG 2` reports failure on all 15 captures because its masks were derived
  from the pre-fix state, so it **reports a correct fix as a mechanism
  refutation**. `ink_mask()` must be re-derived before that tool judges
  anything again. Nobody has been told this.

**Evidence class: MEASUREMENT** -- a pre-registered arm, 126 checks, re-judged
legs, plus a source read at HEAD confirming the commit is present.

**Action:** post `done.md`'s content to #43 before the scratchpad is reaped,
then close #43. Route the `ink_mask()` staleness to whoever owns that tool.

---

## 2. #79 -- CLOSABLE as a duplicate of #44, and it has been waiting four days

Tracker already carries `status = "fixed-verified"` and `blocked_on` ending
"close as a duplicate of #44 when it does". The issue is still OPEN. It is the
only open issue whose tracker row reads `fixed-verified`.

The comment of 2026-09-14T01:59:57Z asks the board directly:

> "**Suggest closing as a duplicate of #44** once someone confirms -- the board
> then carries one cost decision ... instead of two open defects."

Nobody answered. Evidence class: **MEASUREMENT** -- `XEMU_OPT_FIFO_SKEW_BOUND`
0 vs 1, Stencil x4 per arm, PRE-REGISTERED PASS on all 16 checks, 7 wrong of 64
-> 0 of 64; a V0 validity gate against an 11.2% floor taken from fourteen
earlier runs *before* queueing, so a quiet arm A would have invalidated the arm
rather than passing it; V2 on a direct counter rather than a proxy; Fisher
p = 0.013 within the pair.

**Action:** close #79 pointing at #44. It carries no work of its own, and
#44's row is now complete (below), so there is nothing left for the "when the
decision lands" condition to wait for.

---

## 3. #44 -- NEEDS AN OWNER DECISION, and the recommendation is not on the issue

The tracker says outright: "**THE ROW IS COMPLETE, 2026-09-18, 6 OF 6 LEGS
HOLD, AND #44 HAS NO MEASUREMENT GAP LEFT**", with a final recommendation
(mode 2 if a bound is enabled; not as a global default; a per-title setting is
the natural home, reachable with no rebuild because `fifo_skew_bound_mode()`
reads `HAKUX_FIFO_SKEW_BOUND`).

**That recommendation exists only in `nv2a_issues.toml`.** #44's last GitHub
comment is 2026-09-14T02:00:08Z. AGENTS.md's "Disposition an item, update its
issue" runs the other way too: the tracker is not the issue log, and a decision
recorded only in a hand-maintained TOML is one the owner will not find.

**Action:** post the dominance table and the two-part recommendation to #44,
and put the enable/leave-off question to the owner in one line. This is the
decision #79 is nominally waiting on.

---

## 4. #82 -- closed `fixed-verified` on a fix that is not on this branch, and its durable instrument cannot run here

#82 is CLOSED and the tracker row is `fixed-verified`. Neither the fix nor the
checker works at HEAD.

**The fix is not here.** `git branch -a --contains 197370948e` and
`--contains 622183271b` both return **only**
`remotes/origin/claude/docs-tooling-agentic-coding-u152m1`. The four
`floatx80_to_int{32,64}[_rtz]_nds` helpers do not exist in
`target/i386/tcg/fpu_helper.c` on this branch; `grep` for
`floatx80_to_int32_rtz_nds` returns nothing, and `git log -S` over that file
finds it in exactly one commit, `622183271b`, which is not an ancestor.

**The instrument the close rests on fails at HEAD, and fails obscurely.** The
tracker's argument for closing is that `docs/testing/x87_conv_check.py` is the
durable replacement for a scratchpad harness -- "A NUMBER THAT CANNOT BE
RE-RUN IS A CLAIM". Run at HEAD it prints:

```
source: target/i386/tcg/fpu_helper.c  (1 lines carved)
...
undefined reference to `floatx80_to_int32_nds'
native compile FAILED
```

The cause is a positional slice with no ordering check. `carve()` takes
`lines[s:e+1]` where `START = 'static inline double floatx80_round_to_int_nds'`
and `END = '#define floatx80_to_int64_round_to_zero'`. On **this** branch the
END marker matches the *pre-fix truncating macro* at `fpu_helper.c:251` --
`#define floatx80_to_int64_round_to_zero(a, s) ((void)(s), (int64_t)(a))` --
which sits *before* START at :284. So `e < s`, the slice is empty, the script
reports "1 lines carved" and dies at the linker. It is loud rather than silent,
which is the good half; but "native compile FAILED" is indistinguishable from a
broken host toolchain, and the 35-assertion result the close cites cannot be
reproduced here at all.

Incidentally that same line 251 is a direct confirmation that **#74 is live at
HEAD**: the truncating macro #74 was filed against is still there verbatim.

**What the tracker should say:** #82's status should be `fixed-unlanded`, which
is the value `check_cited_commits.py`'s own failure text names for exactly this
case ("Either the work landed under another sha -- then cite that one -- or it
did not, and the status is wrong. `fixed-unlanded` is the honest value when a
fix exists elsewhere"). And `carve()` should refuse `e < s` rather than
returning an empty block -- that is a toolsmith item, and it is the
"establish what your instrument cannot see" rule arriving through a slice
index.

**Related, same root:** `check_cited_commits.py` **FAILs at HEAD** -- 9 entries
claim a fix not on this branch (#38, #66, #68, #82 x6) and 22 cited commits are
absent as patches. I checked whether this is blocking anyone and **it is not**:
`preflight.sh` runs only `nv2a_index.py check`, `check_territory.py` and
`check_coverage.py`. So the tracker's cited-commit hygiene is unmonitored --
the instrument exists, fails today, and nothing runs it. Worth wiring in, or
worth saying explicitly that it is a manual tool.

---

## 5. #60 -- the tracker names an INERT arm as "a real falsifier", and the arm has been run

Tracker `status_note` ends:

> "Nothing judges it and the device lane cannot -- it is Vulkan ... The arm it
> needs is already specified in the thread: **a105a51a00 against its parent on
> the GL lane, predicting that no capture moves at all, which is a real
> falsifier of the format-table audit.**"

The comment of 2026-09-14T00:32:46Z ran that arm and refuted the claim about
it, in the terms AGENTS.md uses for a tautological leg:

> "`a105a51a` is **+104 lines, 0 deletions** -- it adds `drawn_format` and
> populates it. The read side is a *separate, later* commit, `082bc0ac` ... A
> pure addition cannot change behaviour until something reads it. **This arm is
> inert by construction, not by evidence about the format table.**"

0 of 44 captures moved. The lane also recorded that its own prediction on that
arm was refuted because it had not read the named commit's diff first.

Three corrections the tracker should carry, and one that has since become
stale in the *good* direction:

- **Replace the named arm** with `082bc0ac` against `1a879e56`. Measured there:
  `Blend_surface::ARGB8_Add_SrcA_1-SrcA` +13,363, `ARGB8_Add_SrcA_DstA` +9,881,
  `DstAlpha_XA_O1A7RGB8` +8,192, net **+31,436 px**, two runs per arm, every
  arm 44/44 byte-stable against its own repeat.
- **#60 is not blocked on the GL lane. It is blocked on #59, and on one
  capture.** With #71's single line applied, two of the three movers return to
  the *exact* parent value and only `DstAlpha_XA_O1A7RGB8` (+8,192 px) remains,
  attributed to #59's pad-alpha semantics. The tracker has no `blocked_on`
  field for #60 at all.
- **The comment's headline ask is now SATISFIED -- do not re-route it.** It
  said "The campaign branch should take `f75a4aad`", and that "`f75a4aad` is
  not an ancestor of it, and `min_filter = 0xFFFFFFFF` appears **zero** times
  in its `gl/surface.c`". At HEAD: `f75a4aad1a` IS an ancestor,
  `texture->min_filter = 0xFFFFFFFF;` is at `gl/surface.c:1458`, and
  `fada1d89d4` (#66) is an ancestor too. Both #71 and #66 closed on 09-18. The
  comment reads as a live blocker and is four days out of date.
- **Therefore a live consequence nobody has stated:** HEAD carries #60's read
  side *and* #71's fix together, which per the measurement above means a
  standing +8,192 px on `Blend_surface::DstAlpha_XA_O1A7RGB8` owned by #59.
  Nobody has re-measured that at HEAD, and this host cannot -- those 44-capture
  GL runs are the desktop lane's.

---

## 6. #62 -- four of six fixed at HEAD, ONE COMMENT OVERSTATES, and finding 2 is confirmed live

The last comment (2026-09-14T05:17:35Z) tabulates all six as "Four fixed, one
now fixed, one live and not mine". I read the live file at HEAD for each.

| # | comment says | at HEAD |
|---|---|---|
| 1 R5G6B5 abort | fixed | **confirmed** -- `case ..._LE_R5G6B5:` at `gl/surface.c:552` with the conversion body |
| 2 blit bypasses replication | LIVE | **confirmed live** -- `gl/surface.c:635` still `case ..._LE_R5G6B5: return false;` unconditionally, inside `android_surface_to_texture_needs_guest_reinterpretation()` |
| 3 over-read | fixed | **confirmed** -- `texsize` at :1376, `bufsize = max(...)` at :1377-1378, `g_malloc` at :1381 |
| 4 `compare_surfaces()` names the format | "**fixed just now** -- `6b78d91f`" | **NOT AT HEAD** |
| 5 zeta bound | fixed | **confirmed** -- `map_len` at :2785-2793, bounded against the map actually selected |
| 6 dead function | fixed | **confirmed** -- zero occurrences of `android_sanitize_surface_format` |

**Finding 4 is the overstatement.** `compare_surfaces()` at
`gl/surface.c:2712-2739` has the full `DO_CMP` list and it contains **no**
`shape.color_format` and **no** `shape.zeta_format` -- only the four
`shape.clip_*`, `gl_buffer`, five `fmt.*`, and the geometry and time fields.
`6b78d91f24` ("nv2a/gl: the eviction trace can now name the format that
changed") exists but `git branch -a --contains` puts it only on
`remotes/origin/claude/docs-tooling-agentic-coding-u152m1`. The comment does
say "on this lane's branch at `6b78d91f`", so it is honest about where it is --
but the table reads "fixed", and the tracker would inherit that. It is
**unfolded, not fixed**, and it is the two lines #60's eviction trace needs.

**What the tracker should say.** #62's `status_note` currently reads "The
remaining findings of the six have NOT been re-checked this way and the
paragraph below still stands for them." That is no longer true: 5 and 6 are
verified fixed at HEAD by content read, 4 is verified unfolded, and 2 is
verified live at a named line. The "ORIGINAL FOLLOWS" paragraph saying zero of
six landed should be cut rather than carried -- it is the ancestry error the
entry above it already corrects, and leaving both invites the next reader to
believe the wrong one.

Finding 2's disposition is right as the comment leaves it and should be
recorded: it is #59's replication semantics, and it is unmeasurable from either
scored lane (device lane is Vulkan; the desktop GL build does not define
`__ANDROID__`), so it needs #59's lane or an Android GL arm that does not
exist.

---

## 7. #51 -- the tracker says the thread has zero comments. It has five, and the last one reports the fix

`status_note` contains:

> "The coordinate range this issue is titled on is unimplemented and no arm has
> judged anything on it. **The thread carries none of the above: it has zero
> comments**, and the #51 probe build's own measurements are recorded on #40
> instead."

There are five comments. The last (2026-09-14T04:40:32Z) is
"**Fixed: 296,177 px -> 150, on both renderers, one capture byte-exact**",
`4a08abef`, registered before writing (`d74eb64f`), 6 better / 0 worse /
-296,027 px *identically* on OpenGL and Vulkan, GL vs Vulkan 78/78
byte-identical afterwards, two runs per arm per renderer all byte-stable.

The entry is internally inconsistent rather than simply stale: a later
paragraph in the *same* note audits `4a08abef66` for M1 and M2 and says "the
campaign branch does not carry 4a08abef66 at all". So the note both audits the
fix and says the thread that reports it is empty.

**Verified at HEAD:** the fix is indeed unfolded -- `dotSTR3Dir` appears
nowhere in `glsl/psh.c`, and `check_cited_commits.py` lists `4a08abef66`
("#51 DOT_STR_3D fetches the +Z face corner, not the raw d...") as absent.

**What the tracker should say:** cut the "zero comments" sentence; record the
measured result and its legs; and set the status to `fixed-unlanded` rather
than `open`, since a measured fix exists elsewhere and M1/M2 are confined to it
("THE FOLD IS THE MOMENT THEY BECOME LIVE" is already in the entry and is the
right framing).

---

## 8. #39 -- three comments the tracker does not reflect, one of which asks for a tracker note by name

Not closable, and the comments are right to refuse it. But the row misses
everything after 2026-09-13T17:26.

- **The four reproducers no longer fire.** 25 runs, 1,402 captures compared by
  sha256, **zero** run-to-run variation, against the issue body's own recorded
  rates. Then a wider search: whole `iso_surf1`, three runs per renderer --
  Vulkan 236/236 agree, OpenGL 235/236, and the one unstable capture is
  `Surface_pitch::Swizzle` **under OpenGL**, not the renderer this was filed
  against. 2,818 captures across 31 runs, one unstable capture.
- **The comment asks for a tracker note in as many words**, and it has not
  landed: *"it should carry a note that its reproducers are stale, so the next
  person does not spend a day on the suspect list against discs that no longer
  separate anything."*
- **#44's skew bound closes the desktop race, and GL then equals Vulkan byte
  for byte.** `HAKUX_FIFO_SKEW_BOUND` 0/1/2 on a two-test disc, three runs per
  arm: off gives 15,360 / 13,056 / 11,392 and three distinct captures; both
  bounds give 10,240 x3 and **one** digest, `15845fa9e1e40032` -- the exact
  digest recorded for Vulkan over five runs. With a wall-clock positive control
  (16-18 s -> 97-105 s) so a null arm could not be confused with an unset
  variable, and `Pixel_shader::Passthru` byte-stable in all three arms as the
  did-not-change-everything control. The tracker's current sentence -- "Every
  intervention is a timing knob and the full validation layer closes the window
  outright (0 of 7), which is a statement about the instrument" -- is now the
  weakest available statement of this.

**COMMENT DOES NOT OVERSTATE, and that is worth recording too**: the same
comment explicitly declines to close #39 -- "#39 is a *lost draw* on device at
7 of 13 runs on `Stencil`; this is one desktop capture whose *content* varied.
They share a mechanism and the same remedy closed both -- evidence of one
family, not proof." Keeping #39 open is the correct outcome.

**One cheap cross-check that would strengthen #87, since it turns on the same
digest.** #87's entry says its race-free reference is "not a 09-18 desktop run
(that capture is NOT on disk) but FIVE pinned DEVICE runs ... byte-identical,
digest 15845fa9e1e40032". #39's comment attributes that same digest to five
**desktop-lavapipe Vulkan** runs, and to GL with the bound on. If all three
agree byte-for-byte across lavapipe and Adreno, that is a much stronger
reference than either entry claims and #87's Morton fit rests on firmer ground;
if they do not, one of the two provenances is wrong and #87's mechanism rests
on the wrong capture. Either way it is a `sha256sum` away.

---

## 9. #34 -- NEEDS A DECISION, and the device half is impossible rather than un-run

The tracker row is **correct and more complete than the thread** -- it names
all seven fix commits, the positive control, and the measurement gap. No
correction needed. What is missing is an answer.

Both surviving comments ask the board to decide, on 09-13 and 09-14:
*"Suggest this issue closes once someone confirms on Adreno, since desktop is
clean and the consequences were all stated as device-side."* Four days, no
answer.

**I checked the one fact that decides it, and it turns "un-run" into
"currently impossible".** The tracker says "nothing in `android/` packages
`libVkLayer_khronos_validation.so`". Verified: `grep -rn` over `android/` for
`VkLayer_khronos_validation`, `validationlayers` and `vulkan-validation`
returns **zero hits**, and `vk/instance.c:111` matches the layer against
`available_layers`, so it can only find one that is packaged. So the Adreno
confirmation is not waiting on a device; it is waiting on someone adding the
layer to the APK.

**Evidence class for the desktop half: MEASUREMENT with a control.** Three
discs / 120 captures at 0 VUIDs, layer version pinned to the same 1.3.275 the
issue names, and the control is not silence -- the layer still emits four
`Undefined-Value-ShaderOutputNotConsumed` warnings per run, so the callback is
firing. Also: `Surface clip`, the disc this issue says the *layer* segfaults
on, runs to completion, 47 captures, `QEMU_EXIT=0`.

**The decision is a fork, not a judgement call, and either branch is
defensible under this campaign's own precedents:**

- Close it as measured-out on the only oracle that exists, the way
  `apu-sink-short-read` closed; or
- keep it open and file the APK-packaging work, which is the #82 outcome --
  open on an honest caveat.

Naming it either way costs nothing; leaving it costs a row that looks active.

---

## 10. #81 -- `blocked_on` describes a blocker that has been cleared, and the tracker's own note contradicts it

`blocked_on` says:

> "this issue's first step is establishing whether the tier-1 mechanism fires at
> all, and that needs `hakuX-tier1:D` in `dispatcher.sh`'s `LOGCAT_SPEC`, which
> is routed to lane.toolsmith. **Until that lands**, the zero `[tier1]` lines on
> every logcat on disk are NOT EVIDENCE EITHER WAY."

It landed. `dispatcher.sh:1042` now reads
`... hakuX-lane:I hakuX-tier1:D hakuX-pages:I ...`, and the same entry's
`status_note` already says the measurement happened -- "`tb_lookup_cmp()`'s note
... says `tier1_consume_request()` 'never fires'. That is measured false in the
absolute ... It closes with its own falsifier -- 'Establishing it needs a run
with that tag enabled' -- **which has now happened**".

`check_coverage.py` independently flags the other half at HEAD: "#81 names
`cpu-exec.c`, `translate-all.c` ... so the obstacle they describe does not
currently exist -- they are grant requests rather than walls."

**Action:** rewrite #81's `blocked_on` as a grant request, and cut the
"until that lands" clause.

---

## 11. Five cited artefacts do not resolve at HEAD

I checked every `docs/`, `hw/`, `target/`, `android/` path cited anywhere in
the tracker and anywhere in the comments of all 31 open issues. **The tracker
is clean -- zero missing paths.** The comments are not:

| cited by | path | where it lives |
|---|---|---|
| #34 | `docs/investigations/issue34-validation-findings-are-gone.md` | not on this branch |
| #39 | `docs/investigations/skew-bound-closes-the-desktop-race.md` | added by `1ab0a57051`, not an ancestor |
| #51 | `docs/testing/predictions/issue51-dot-str-3d-sign-table.json` | added by `faa5abdd36`, not an ancestor |
| #60 | `docs/investigations/issue60-measured-on-the-campaign-branch.md` | not on this branch |
| #74 | `docs/investigations/issue74-no-oracle-the-code-never-runs.md` | not on this branch |

The #51 one is the sharpest: the fix comment says "Registered before writing
(`d74eb64f`); every leg passes", and **the file the legs live in is not here**,
so the four legs cannot be re-checked on this branch. That is the #82 lesson
("a number that cannot be re-run is a claim") in a second place.

Two false alarms I am recording so nobody chases them: #38's comment flagged
`interpolator_phase.py` and `interpolator-sample-position.md` as existing only
on a retired worktree -- **both are at HEAD now**, in `docs/testing/` and
`docs/investigations/`. And #89's `docs/investigations/desktop-runs.md` is a
prefix typo; the file is `docs/testing/desktop-runs.md`.

---

## 12. FBSTP has no row, and #74's own entry says to give it one

#74's `blocker_tested` ends:

> "(b) `helper_fbst_ST0` (`fpu_helper.c:1461`, FBSTP) is a live compiled
> truncation bug on Android that a fix should cover, and `fbstp` count = 0 in
> the corpus, so no test here can ever guard it. **File that separately rather
> than losing it inside #74.**"

It was not filed. `fbst`/`FBSTP` appears in exactly two tracker rows, #74 and
#82, and `gh issue list --state all --search FBSTP` returns only those two. It
is a defect with a named site, a known reason no arm can reach it, and an
explicit instruction to give it a row -- which is the "somewhere for the work to
live" condition from AGENTS.md's routing rule.

---

## 13. Asks that have already been answered -- do NOT re-route these

Recording these so the same routing does not get done twice.

- **#54's `dispatcher.sh` ask is DONE.** The comment of 2026-09-13T17:09:48Z
  proposed one token at `dispatcher.sh:548` -- adding `hakuX-phase:I` and
  `xemu-work:I` to `LOGCAT_SPEC` -- and declined to apply it from that lane.
  Both tags are in the spec at `dispatcher.sh:1042`. The second half of the
  same ask is also done: the comment said "the **soak path** records no
  `logcat` field at all ... from a soak result alone, 'the filter dropped it'
  and 'the code does not log it' are indistinguishable", and
  `dispatcher.sh:628` now writes `logcat=dict(spec=_spec, lines=int(lines))` on
  the soak path, with no fallback literal (`:625`).
- **#59's `dualSrcBlend` ask is answered.** The comment's "next step is one
  line and one boot" is recorded in the tracker as "ANSWERED -- available. The
  query at `vk/instance.c:870-900` has run four times, and lane.falsifiers
  found the output unread." Note the answer did *not* come from the
  `desired_features` table, which still lists nine features and no
  `dualSrcBlend` -- so anyone re-checking by reading that table will conclude
  the opposite. Worth one clause in the entry.
- **#38's stale-artefact note is satisfied** (see item 11).

---

## 14. Quiet and correct

Read against their comments and spot-checked in the tree, no correction owed:
**#10, #13, #31, #38, #50, #53, #65, #68, #73, #77, #83, #85, #86, #87, #88,
#89, #90**. Several of these are the best-kept rows on the board -- #10's
"the tracker recorded this morning's R16B16 arm as never run ... when two
results named it and it had passed" has already been folded in along with the
premise correction that Y16/YUV go through BUMPENVMAP rather than HILO, #31
carries its own refuted-blocker audit, #74's blocker is confirmed by an
exhaustive XBE disassembly *with a positive control* (#67's oracle is visible
to the same instrument: 5 `frndint` sites at RC=down, 5 at RC=up), and #84 was
corrected by the orchestrator against its own issue text while I was reading.

---

## 15. One structural observation, not an issue finding

**The tracker is now ahead of the issue log, and that is a new failure
direction for this board.** The 2026-09-18 conclusions on #44 (the final
shipping recommendation), #87 (the Morton mechanism), #88 and #89 (arm A run 1,
which settled the composition question) exist only in
`docs/testing/nv2a_issues.toml`. #88, #89 and #90 have zero comments; #44's
thread has been silent since 09-14 while its row grew by thousands of words.

AGENTS.md's argument for the issue log -- "a finding that lives only in a
commit message, a doc or a PR thread is one nobody will find before re-deriving
it" -- applies verbatim to a finding that lives only in a hand-maintained TOML
on one branch. #43 above is what that costs: a 1.81M-px result that is in
neither place, with its only copy in a scratchpad directory.


---
---

# RE-VERIFICATION AT `72035a2121`, written at wind-down

Everything above was established against `f343580647` / `391ac6bfb9`. Between
then and now the orchestrator applied most of it (`4c436f335c`, "board:
triage's first pass"), folded 77 of lane.remote's commits (`24d1eaffb5`), and
filed #91-#95. **I re-checked every finding above against the tree at
`72035a2121` rather than restating it.** Nine of the fifteen are now resolved.
What follows is only what is still true.

## RESOLVED since my pass -- do not re-apply these

| item | what closed it, verified at HEAD |
|---|---|
| #82's fix absent | the four `_nds` conversion helpers are in `fpu_helper.c` (2 hits for `floatx80_to_int32_rtz_nds`) |
| #82's checker unrunnable | `608aaf5a75` fixed the marker ordering; `x87_conv_check.py` now prints **35 assertions, 0 failed** and cross-compiles for aarch64 |
| #51 unfolded | folded as `8b50aefbd4`; the +Z sign-bit rule is in `glsl/psh.c` in prose and code, and M1/M2/L8 as `28eeff3d88` (`textureLod` now present, 1 hit) |
| #51 prediction file missing | `docs/testing/predictions/issue51-dot-str-3d-sign-table.json` is at HEAD (`9b4c634944`) |
| #60's missing `blocked_on` | now reads "BLOCKED ON #59, one capture and 8,192 px" |
| #34 / #39 / #60 / #74 write-ups missing | all four now at HEAD (`45da03b8fc`, `bde4b8b237`, `6520163e77`, `3497c6946e`) |
| #43's result unrecorded on the board | applied to the tracker verbatim, including all four ride-alongs |
| #62's finding 4 unfolded | **folded as `b5b3e188a8`** -- see the correction below |

## STILL LIVE at `72035a2121`

### A. #62 -- the tracker now carries MY finding, and HEAD has overtaken it

This is the one I most want applied, because the stale sentence is one I put
there.

#62's `status_note` now ends:

> "ONE COMMENT OVERSTATES ... **FINDING 4 IS NOT AT HEAD**, because
> `compare_surfaces()` at :2712-2739 has no `shape.color_format` and
> `6b78d91f24` is lane-branch only. Unfolded, not fixed."

That was true when I wrote it and is **false now**. At `72035a2121`,
`gl/surface.c:2724-2725` reads:

```c
    DO_CMP(shape.color_format)
    DO_CMP(shape.zeta_format)
```

folded by `b5b3e188a8` ("nv2a/gl: the eviction trace can now name the format
that changed") in the 77-commit fold. So **finding 4 is fixed at HEAD**, and
the finding's value survives only as history -- the comment *was* ahead of the
tree for four days.

**State of all six, read from the live file at `72035a2121`:**

| # | at HEAD | evidence |
|---|---|---|
| 1 | fixed | `case ..._LE_R5G6B5:` at `gl/surface.c:552` |
| 2 | **LIVE** | `gl/surface.c:635` still `case ..._LE_R5G6B5: return false;` |
| 3 | fixed | `texsize` :1376, `bufsize = max(...)` :1377-8 |
| 4 | **fixed** | `DO_CMP(shape.color_format)` :2724 |
| 5 | fixed | `map_len` :2785-93 |
| 6 | fixed | zero occurrences |

**What the tracker should say:** replace the "FINDING 4 IS NOT AT HEAD"
sentence with "finding 4 folded as `b5b3e188a8`"; and **cut the ORIGINAL
paragraph** that still reads "Of the six listed findings, zero landed on this
branch" -- five of six have now landed and that sentence has been wrong in two
different ways. #62 is now **one live finding**, #2, and it is explicitly not
that lane's (it is #59's replication semantics, unmeasurable from either scored
lane).

### B. `check_cited_commits.py` still FAILs -- 5 entries, and the diagnosis splits two ways

Re-run at HEAD: **5 entries claim a fix not on this branch** (was 9), 18 cited
commits absent as patches (was 22). I checked each against the tree rather than
reporting the list, and the five are **not** one class:

**Landed under another sha -- re-cite, do not change the status:**

| entry | cited | landed as | verified at HEAD |
|---|---|---|---|
| #51 | `4a08abef66` | **`8b50aefbd4`** | the sign-bit rule and its comment are in `glsl/psh.c` |
| #51 | `4c3364bcb1` | **`28eeff3d88`** | `textureLod` present, border-remap ordering fixed |
| #66 | `5b707602` | **`a9d06195fd`** | the `glLineWidth` guard is at `gl/draw.c:55-77` |

**Genuinely unfolded -- `fixed-unlanded` is the honest status, which is the
checker's own wording:**

| entry | cited | why I am confident it is absent |
|---|---|---|
| #38 | `24a75d6e3c` | `vk/blit.c:175-179` still carries the **exact text that commit deletes** -- "Reciprocal approximation ... `(val + 0x3FC0) >> 15`". `gl/blit.c:152` has the fix (`(a + b + max_beta_mult / 2) / max_beta_mult`); Vulkan does not. |
| #68 | `937848c9e7` | `tb-maint.c:60` still has `hakux_inval_would_survive` with its **pre-retirement** comment and still increments it at :1795; the commit's "RETIRED 2026-09-14 by #68" block is absent (grep count 0). |

**A trap I nearly fell into, recorded because the next reader will hit it.**
My first check for #38 used `max_beta_mult = 0x7f80` as the marker. That is
present in *both* backends and `git log -S` attributes it to `a5385803db`
("nv2a: Add Vulkan renderer") -- it **predates the fix**, which is about the
*divisor*, not the constant. Keying on it says "the fix is in" when it is not.
The discriminating text is the deleted `>> 15` reciprocal comment.

The checker is still **not wired into `preflight.sh`** (which runs only
`nv2a_index.py check`, `check_territory.py`, `check_coverage.py`), so this
FAIL is invisible unless run by hand.

### C. #43 -- the board was fixed, the ISSUE was not

`4c436f335c` applied my #43 finding to the tracker in full. But #43's last
GitHub comment is **still** the bare unexpanded reference, re-checked just now:

```
comments: 13   last: 2026-09-13T23:23:26Z
body: @/tmp/claude-1000/-home-justin-hakuX/afb31e59-6fc4-4685-81b2-b4db438e1cf3/scratchpad/done.md
```

The rescue happened on the board, not in the issue log. The content is
preserved at
`$DISPATCH_DIR/board-requests/triage-issue43-done-rescued.md` and committed on
`origin/lane/triage`, so it no longer dies with the session -- but it is still
not where AGENTS.md says the project's memory lives.

### D. #81 -- `blocked_on` still describes a cleared blocker

Unchanged since my pass. It still reads "that needs `hakuX-tier1:D` in
`dispatcher.sh`'s `LOGCAT_SPEC` ... **Until that lands**, the zero `[tier1]`
lines ... are NOT EVIDENCE EITHER WAY". The tag is at `dispatcher.sh:1042`, and
the entry's own `status_note` already says the measurement happened.
`1c9935f102` granted #81 its files, which was the other half; the tag clause
was not touched.

### E. #34 -- still no `blocked_on` at all, and the decision is still unanswered

`blocked_on` is literally `None`. The Adreno confirmation both comments ask
about is not merely un-run: `grep -rn` over `android/` for
`VkLayer_khronos_validation` / `validationlayers` / `vulkan-validation` returns
**zero hits**, and `vk/instance.c:111` can only match a packaged layer. So it
waits on APK packaging, not on a device.

### F. #79 -- unchanged: `fixed-verified` and open

`blocked_on` still ends "close as a duplicate of #44 when it does". See the
recommendation section below.

### G. FBSTP still has no row

Re-checked: `fbst`/`FBSTP` appears in exactly two tracker entries (#74, #82)
and `gh issue list --state all --search FBSTP` returns only those two, despite
#74's `blocker_tested` saying "**File that separately rather than losing it
inside #74.**" Site: `helper_fbst_ST0`, `fpu_helper.c:1461`; `fbstp` count = 0
in the corpus, so no arm on this fleet can ever guard it.

---

# RECOMMENDATIONS -- NOT APPLIED. Closing is a decision.

Flagged per the wind-down rule. I have applied none of these.

1. **Close #79** as a duplicate of #44. Tracker already reads `fixed-verified`
   and says to. Evidence is a MEASUREMENT: pre-registered 16/16, 7 wrong of 64
   -> 0 of 64, V0 validity gate set against an 11.2% floor from fourteen prior
   runs *before* queueing, V2 on a direct counter, Fisher p = 0.013.
2. **Close #43.** Both halves closed by measurement (`ab4a829316` and
   `86a1c53195`, the latter verified an ancestor), residual entirely #78's and
   #78 is `fixed-verified`. Do this *after* posting the rescued content, or the
   evidence closes with the issue.
3. **Decide #34, either way.** Close it as measured-out on the only oracle that
   exists (the `apu-sink-short-read` precedent), or keep it open and file the
   APK-packaging work (the #82 precedent). Both are defensible; leaving it is
   the only option that is not.
4. **Narrow #62 to finding 2 alone** -- five of six are fixed at HEAD.

Not recommended for closing, and I want that on the record too: **#39 should
stay open.** Its own comment refuses to close it, correctly -- "a rate that fell
is indistinguishable from a rate that reached zero", and #39 is a lost draw on
device while the desktop evidence is one capture whose content varied.
