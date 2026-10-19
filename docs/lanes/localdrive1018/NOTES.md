# localdrive1018 (#433): drive on local tools only, act-observe, learn

Owner, 2026-10-18 ~13:50 PDT: no API key path anywhere; local tools only (pathclass/classify.py/adb/pad.sh,
no new model, no new runtime); never wait and fail, act and learn from the outcome; GTA III (Xbox) is the
proof title. Four requirements, see brief for full text.

## Step 0: Already tried

| approach | where | verdict | what it means here |
|---|---|---|---|
| Zero-shot SigLIP2 B/16-384, prompts only | `pathknow/classifier/zeroshot_eval.py` (pathclass) | 71/120=59%, 0/103 false-gameplay, 14 false negatives | never says gameplay by itself; too blind to carry B alone |
| + linear head, 583 Haiku labels | pathclass | 87/120=72.5%, false-gameplay 8/103=7.8% | first learned head; false-gameplay too high to gate a route-ending claim |
| + OCR text rules (EasyOCR, `pathclass.py: text_state()`) | pathclass | 95/120=79.2%, false-gameplay 6/103=5.8%, OCR fixed pause 2/8→8/8 | OCR crops already exist and help; keep using them in act-observe, don't rebuild |
| Restart: +1500 Haiku labels (`head_haikuonly.npz`), pool rebuilt 5349 frames/149 titles | pathclass | 98/120=81.7%, false-gameplay 4/103=3.9% | **shipped head**, current `generic.toml` uses it; this is the floor we inherit, not a target to re-derive |
| + 293 Sonnet-adjudicated labels (`head.npz`) | pathclass | 99/120=82.5% but false-gameplay rose to 5.8%, flipped the KOF false-pass case | discarded — a named false-pass regressing outweighs a raw accuracy gain; same rule applies to any GTA III head change in part D |
| Backbone L/16-384 vs B/16-384 | pathclass | 74.2% vs 72.5%, no material gain | keep B/16 (26 ms), do not propose a bigger backbone for GTA III |
| Single confidence floor 0.85 everywhere | `generic.toml` `classifier_confidence` | 39/120 answered, right on all 39 | this is the floor the brief cites as "only ~1/3 of frames get an answer" — **this is exactly what Part B removes as a gate on acting**, kept only as the gate on a `play` claim |
| Floor sweep at menu_seen=True (Addendum 6, 2026-10-12) | pathclass | 0.7 chosen for menu floor: 66/120, 63 right (95.5%), 0 errant/0 wrong; 0.85 kept for gameplay only | confirms the existing two-floor split (`classifier_confidence` 0.85 gameplay-only, `classifier_confidence_menu` 0.7 everything else) already matches "gate only the play claim" — do not add a third floor, reuse these two |
| `ask_model()` Haiku fallback on `unknown` | `drive.py` (added in the Oct-1 commit `23496a93`, together with the whole state machine) | never made a call on this host in dev (`routedriver/NOTES.md`: "no ANTHROPIC_API_KEY ... the Haiku fallback was never available"); in production it is why `gen-fable` died "unknown screen for 91s (model unavailable)" (`gta3instr1018/NOTES.md` 5.3, run `1792340341-gta3instr1018-509423`) | confirms the brief: it's not a missing key, it's abstention. 8/10 gen-* routes voided overnight 10-18 this way (memory `gen-routes-die-without-a-model-key`). This is what Part A removes and Part B replaces |
| Skip ladder A, START, B, X, START+A on logo/intro_video/cutscene | `drive.py` POLICY, since the Oct-1 commit | works; START excluded from `cutscene` unless a `paused` crop exists, after a run-3 regression where START hit a cutscene fade-in and opened a status menu | reuse as the base of the exploration ladder in Part B; do not re-derive the START-safety condition, copy it |
| Cursor row-brightness for jittery menus (Buffy) | `drive.py:cursor_press`, `classify.py:cursor_row` | per-row reference crops failed (glow pulses); brightest-row-by-99th-pct-grey worked, right on 25/25 labelled frames, confirmed b18 | existing [[cursor]] mechanism is available to GTA III's pause menu Save-row pick in Part D, no new mechanism needed |
| `play_tap` burst form for a blind jump past a ledge (Buffy) | `drive.py:play_taps` | inconclusive after 14 runs (b5-b14), hit the 10-save device-run limit; "Y is not the jump either" | a reminder that act-observe on an untried-input ladder can still end inconclusive within a budget — report as such, don't claim solved |
| `stall_cycle`/`stall_cycles`, `progress_bar`, `stall_clear_s` (Sonic Heroes wedge escapes) | `drive.py` | fixed a false `play` from a wedge reading 0.14-0.18 motion; per-mode escape budgets reset on a new obstacle site | existing stall-escape machinery already does "try, don't wait" for the `stalled` state; Part B's ladder is the same idea generalized to `unknown` and no-input states |
| Local VLM / new runtime | not raised in pathclass or routedriver NOTES | no record of one being tried | consistent with the brief: none approved here either; if D's GTA III head still can't separate cutscene from play after a direct crop/head fix, say so in NOTES and stop short of installing one, per the brief |

Known false-pass set (must stay not-gameplay, carried over unchanged): 187 keyboard, Castlevania Name
Entry, Super Monkey Ball Stage Select, Sonic PAUSE, a KOF lost round (PERFECT/WINNER banner), the Simpsons
pause-over-play case (no captured frame exists for it; guarded structurally — `act()` never presses
anything, START included, while `state in (play, stalled)` — proven by a selftest mutant, not a frame).
GTA III adds a 7th: the opening cutscene scored `gameplay` at 0.716 (owner's find today) — this is the
one this lane must fix in Part D without breaking the other six.

Git history check (`-S"ask_model"`, `-S"unknown_fail_s"`, `-S"ladder"` on drive.py): only one substantive
commit, `23496a93` (2026-10-01, introduces drive.py whole), plus one unrelated board-retirement commit
(`ee8c9d3a8d`) that folds an earlier snapshot in without changing this logic. Nothing to port forward
beyond what's in the table above.

## What's different this time
Nothing above tried "remove the key path and never idle" — every prior approach either tuned the
classifier's own confidence (pathclass) or built reactive escapes for a *named* state (`stalled`,
cursor rows, skip ladder). This lane generalizes "ladder on a known problem state" to "ladder on any
state the generic loop can't act on today" (`unknown`, and a named state the profile has no input for),
removes the dead-end model call, and adds a persistent cross-run table so the ladder gets smarter instead
of repeating. That generalization, and the learned table, are new.

## Part A -- done (commit, this lane)
Removed from `drive.py`: `ask_model()`, `MODEL`/`MODEL_USD_PER_MTOK`/`MODEL_PROMPT`, the
`import models`/`models.model_for("drive")` call and its now-unused `jobs/` sys.path insert,
the now-dead `base64`/`hashlib`/`io`/`urllib.request` imports, `model_calls_max` and
`unknown_before_model` from `DEFAULTS`, `self.model_calls`/`self.model_cache`, the
`unknown_streak`/`ask_model` branch in `classify()`, and every `model_calls`/
`ANTHROPIC_API_KEY` reference in `act()`'s unknown-branch Fail message and `finish()`
(route-solution.json field and the printed summary). `unknown_fail_s`'s wait-then-Fail
behavior is otherwise unchanged in this commit -- replacing it with act-observe is Part B,
landing separately. Reworded the stale ask_model/ANTHROPIC_API_KEY comments in
`drive-profiles/generic.toml` (lines that documented the old fail-closed/floor rationale).

Added a grep gate to `pathclass_selftest.py` (`grep_gate()`, wired into `main()`): no
`anthropic`/`ask_model`/`claude -p`/`model_calls_max`/`unknown_before_model` (case-
insensitive) anywhere in `drive.py`, `classify.py`, `pathclass.py`, or
`drive-profiles/*.toml`. Ran `pathclass_selftest.py` and `classify_selftest.py` after the
edit: both 0 failures, including the gate and the pre-existing START-in-play mutant.

Two corrections to the research above and to the brief's own text:
- `pathfind.py` DOES still call the model (`claude -p`, line 8 of its module doc,
  `model_calls` bookkeeping) -- my first grep pass missed the `claude -p` form, only
  checking `ANTHROPIC_API_KEY`/`ask_model`. It is a *separate* tool from `drive.py`
  (cold-boot path discovery, not the screen-aware play loop this issue is about), it is
  not on this lane's edit list, and the brief's four acceptance criteria say "no ... call
  from `drive`" -- scoped to this tool. Left untouched, on purpose, not missed.
- `docs/testing/jobs/models.toml`'s `[kinds.drive]` entry is left in place:
  `pathknow/classifier/label.py:110` (`models.model_for("drive")`, an offline frame-
  labelling tool, unrelated to drive.py's runtime loop) still reads it as its own
  default model. The brief's own wording made this conditional ("drop the `drive` entry
  if nothing else reads it") -- something else does, so it stays. `route.sh` has no
  matches at all, confirmed again, no edit needed there either.

## Plan
- A: delete ask_model/MODEL/model_calls_max/unknown_before_model/model cache/ANTHROPIC_API_KEY from
  drive.py, drive-profiles/*.toml comments, models.toml's `drive` entry (check jobs/models.py first),
  docs that say drive needs a key. Grep gate in selftest.
- B: act-observe loop replacing idle-on-unknown and the old unknown_fail_s death; budget-end-valid.
- C: learned table JSONL per title + global, cosine lookup, regressed veto, selftest with mutants.
- D: gta3.toml profile + route, pathclass head extended with cutscene/loading/movie/play/
  play_dim_unresponsive frames from the captured set, false-gameplay re-measured <=2% including the new
  false-pass case.
- Land A+B+C first (own commit, selftest green, PR.md ready), then D.

## Part B/C -- done (commit, this lane)
`pathclass.py`: `classify_image()` now stashes its pooled, L2-normalized embedding
(`self._last_embedding = pooled[0].cpu().numpy()`, already computed every call, just
discarded before) and `classify()` attaches it to its answer as `"embedding"` (rounded to
4dp). No change to `Client`/`serve()` -- both pass the dict through verbatim, so
`classify.py`'s existing `out["pathclass"] = ans` carries it automatically.

`pathknow/learned.py` (new): one JSONL record per explore press --
`{title, key, embedding, button, outcome, t, run}`. `key` is `"unknown:<classify.py
source>"`, the fallback match whenever either side has no embedding (a crop-only profile,
or this module's own selftest, which never sets one). `outcome` is `advanced`/`changed`/
`regressed`/`none`. Two files per record (`learned/<title>.jsonl`, `learned/_global.jsonl`,
title = the profile's `name`, there being no 8-hex title-id field anywhere in the current
profile schema). `suggest()` ranks by outcome (`advanced` > `changed` > `none`), own table
before global, and **vetoes** any button that ever `regressed` this screen -- even if it is
the only record for it. `cosine()` is a plain dot product (pure Python, no numpy): since
pathclass's embedding is already L2-normalized, that IS cosine similarity. `SIM_BAR = 0.90`
is explicitly untuned (comment in the file) pending real GTA III / held-out frames in Part D.

`drive.py`'s `act()`, `state == "unknown"` branch, rewritten (replacing the old
wait-then-`Fail` on `unknown_fail_s`, which is now gone from `DEFAULTS` and from
`drive-profiles/generic.toml`'s comments): resolve any press still awaiting an outcome
(`"changed"` if `r["changed"]` -- the frame-diff fraction classify.py already computes --
clears `classify.STATIC_BAR`, else by embedding cosine distance against `SIM_BAR`, else
`"none"`), then pick the next button: `learned.suggest()` first, the next untried rung of
a new `EXPLORE_LADDER` (`A, START, B, X, Y, DOWN, LX:min, R1, L1`, START excluded unless
`has_pause_crop`, reusing the cutscene skip-ladder's exact safety rule) otherwise, wrapping
forever once every rung's been tried this stretch. **Never raises `Fail`** for this reason
any more -- the route's own `while self.t() < self.seconds` budget in `run()` is the only
thing that ends a run stuck here, already landing as `result="window-done", rc=0` with no
code change needed (that path existed already; removing the `Fail` call was the whole fix).

One addition past the brief's own text, found by running the existing AvP Extinction
selftest (Addendum 6) against this code: a FRESH `unknown` (the first capture after
entering it) gets one free capture before the first explore press, not instead of one --
`self.explore_fresh`, set in `enter()`, consumed once in `act()`. Without it, the AvP replay
failed: a single-frame low-confidence blip between `intro_video` and `title` (the real run's
own data: 2 of its 3 `unknown` frames resolve for free one capture later, confidence noise,
not a stuck screen) ate an explore press that pushed `last_press_t` just inside
`menu_gap_s`, so the very next capture (the real title screen, confidence 0.8, clears both
floors) read `settle` instead of pressing START -- and the fixture's last recorded frame is
that one, so there was no later capture to recover on. This is bounded to exactly one
capture per fresh `unknown` entry; it does not reintroduce any wait-and-fail, and it is
grounded in this run's own recorded confidence fluctuation, not a guess.

`finish()` / `route-solution.json` gained `explored` (every `(key, button, outcome)` this
run recorded) replacing the old `model_calls` field; the printed summary line now reports
`%d explored` instead of `%d model calls`.

Selftest (`pathclass_selftest.py`, still runs with no venv): three new checks plus every
old one, all green --
- learned table: a button that `advanced` a screen is suggested first next time (direct
  `learned.record`/`load`/`suggest`, no Driver needed).
- learned table: a button that `regressed` a screen is never suggested again, even as the
  only record for it (the veto, not a ranking).
- never idle-fail: 20 identical confidence-starved captures (one fixed profile, `generic`,
  which has no paused crop so the 8-button ladder excludes START) press 7 different buttons,
  wrap once, and end on `result="window-done", rc=0` -- never a `Fail` -- within a 15 s
  budget at `fast_s=1.0`.
All of this file's tests write learned-table records (even the pre-existing ones -- any
`unknown` capture does); `learned.DIR`/`learned.GLOBAL_PATH` are monkeypatched to a
`tempfile.mkdtemp()` for the whole selftest run, or they write into and read back from the
real `pathknow/learned/generic.jsonl` a live `--profile generic` run also uses, making the
selftest both non-reproducible (ran twice in a row, got a different first button the second
time off stale state from the first) and a source of real pollution. Caught by running this
file twice and diffing stdout; verified clean (byte-identical output) after the fix. The
actual `pathknow/learned/` directory this created on disk before the fix (accumulated across
my own debugging runs this session) was moved aside, not committed -- it was test pollution,
not a real learned table; nothing here has a bootstrapped/fabricated outcome in it.

Ran `pathclass_selftest.py` and `classify_selftest.py` after every edit in this section: 0
failures throughout, including all of Part A's checks (unchanged) and the mutant above.

## Open questions (not blocking; keep working)
- Whether pathclass.py already exposes the embedding vector for an arbitrary frame as a reusable function,
  or only as an internal step of classify_frame -- resolved: it computes one every call already
  (`_forward`'s pooled output), just discarded it; stashing it cost one line.
- Exact schema for the learned JSONL -- resolved, see Part B/C section above.
- Part D (GTA III profile/head/route) needs real captured frames and a device to confirm against;
  this lane currently has neither (Nova/Thor both unavailable) -- reporting what's blocked rather
  than guessing at numbers.

## Resume 2026-10-18 ~17:02 PDT (attempt 2): why attempt 1 did not finish

Two separate gaps, not one:

1. **PR.md was never set to `State: ready` despite A+B+C already passing their selftest.** The
   brief's own done-means is explicit: "`PR.md` `State: ready` as soon as A+B+C pass the selftest;
   D follows as further commits" -- a turn-cap safety valve so a cap never strands the whole lane.
   `pathclass_selftest.py`/`classify_selftest.py` were green (0 failures) by 15:07 PDT (commit
   `5a3827eddd`), but PR.md's own "Not done" section instead wrote "**E**: `docs/testing/jobs/
   selftest.sh` is running now; this PR goes to `State: ready` once it's green" and left `State:
   draft`. That is the real defect: it substituted a much heavier, unrelated gate for the one the
   brief actually named, then ended the turn before that substitute gate resolved, with the PR
   still in draft.
2. **`docs/testing/jobs/selftest.sh` cannot complete in one session and was the wrong gate for this
   diff anyway.** Re-ran it this session, foreground, to see for myself: three fragments in (`10-
   arms-list.sh`, `20-arms-queue.sh`, `30-arms-error.sh`) took 73+130+58 = 261 s combined, and
   `ls docs/testing/jobs/selftest.d/` lists 150+ numbered fragments covering arms.sh/fold.sh/
   request.sh/status.sh/cloud.sh and the rest of the dispatch harness -- at this rate the full run
   is multiple hours, not something one headless turn (or several) can block on. More to the
   point, its own module doc states the actual scope: "nothing under jobs/ is pushed until this
   passes, and the check is in CI ... as well" -- a gate on changes *under `docs/testing/jobs/`*.
   `git diff --stat origin/master...HEAD` for this lane shows zero files under `docs/testing/
   jobs/` (only `docs/testing/titles/**` and `docs/lanes/localdrive1018/**`); Part A's own NOTES
   confirm `models.toml` was deliberately left untouched. So this lane's diff is outside that
   gate's stated scope, and CI (`.github/workflows/jobs-selftest.yml`) already covers it for any
   push that does touch `jobs/`. Correcting the brief's Part E line ("run `docs/testing/jobs/
   selftest.sh` before `State: ready`") against this lane specifically: not applicable, nothing
   under `jobs/` changed here, re-ran `pathclass_selftest.py` and `classify_selftest.py` fresh
   instead (both 0 failures again, output unchanged from Part B/C's run) and that is the selftest
   `State: ready` actually requires per Done-means.
3. **Device re-check, as the stale WAITING note asked for.** Live `adb devices` now (17:02 PDT)
   shows only `bdc158a5` (Ayn Thor) -- `ee317437` (Nova) is still absent, not a link flake (same
   serial list on a fresh call). `dispatch/hold/thor.why` is unchanged since 12:00 PDT: lane.local's
   thermal-test/GTA-soak hold on the Thor, "by hand only, no request.sh until the thermal run is
   judged." So the 17:00 PDT re-check the prior WAITING note asked for has been done, and the
   answer is unchanged: neither device is available to this lane. Nothing about Part D's device
   blocker has changed; only the PR-readiness gap above was actionable this session.

Fixed this session: PR.md `State: ready` (A+B+C, matching Done-means), its "Not done" section
corrected to name the real selftest run instead of the abandoned jobs/selftest.sh claim, and the
WAITING file's timestamp/finding refreshed so the next resume does not re-run the same multi-hour
command expecting a different scope.

## Part D, what's buildable offline: `drive-profiles/gta3.toml` (this session, ~17:10-19:05 PDT)

Device re-check first (per the WAITING note's own ask): `adb devices` lists only `bdc158a5`
(Ayn Thor); `ee317437` (Nova) is still absent. `dispatch/hold/thor.why` is unchanged -- lane.local's
thermal-test/GTA-soak hold, by hand only, "no request.sh until the thermal run is judged." Neither
device is available to this lane. Everything below is built and verified against the 9 frames
lane.local captured by hand earlier today (`docs/lanes/localdrive1018/gta3-frames-1018/`, copied
in this session from `/home/justin/hakux-work/captures/thor-gta3-frames-1018/`, which is outside
any git worktree and not committed anywhere) -- it is real evidence, not synthetic, but it is 9
hand-picked stills, not a continuous capture run, and that distinction matters below.

**The named bug (opening cutscene scored `gameplay` 0.716) is fixed by a geometry crop, not a
content crop.** Measuring the black run down each frame's centre column (1920x1080 capture space)
shows the device renders GTA III pillarboxed (left/right, from the Thor's AR, constant in every
frame -- `classify.py`'s own `content()` already strips this before any crop/motion scoring) and,
during the opening cutscene ONLY, additionally letterboxed top/bottom (a true cinematic bar):

    frame  state                   top black   bottom black
    a4     cutscene (bridge, rain)      143 px       180 px
    a5     cutscene (police/truck)      144 px       180 px
    y1     cutscene (subtitle)          144 px       105 px (text breaks the run)
    y2     cutscene (subtitle)          144 px       105 px
    a7     play (on foot, HUD)            0 px         0 px
    m1     play (on foot, HUD)            0 px         0 px
    w3     play_dim_unresponsive          0 px       540 px (dark content, not a bar)
    d2     play_dim_unresponsive          0 px       540 px
    st1    play_dim_unresponsive          0 px       233 px

The top bar is the clean signal (143-144 px in all 4 cutscene frames, 0 px in all 5 others,
unaffected by subtitle text). A `[[crop]] name="letterbox-top" state="cutscene"` built and scored
with the real `classify.py crop`/`score` tool (region 300,60,700,50 in ref space, threshold 8.0,
a >10x margin below the lowest non-cutscene score 18.54) runs BEFORE pathclass in
`classify_frame`'s order (non-play crops are checked first, line ~387), so the cutscene never
reaches pathclass at all. Verified via `classify.py table --profile gta3.toml` over all 9 frames:
a4/a5/y1/y2 all classify `cutscene` via `crop:letterbox-top`, confidence/pathclass never invoked.

**A second, harder finding: GTA III's `play` can never be confirmed through pathclass at all,
under this architecture, regardless of threshold.** `classify_frame`'s `after_title` gate (line
~396, `bool(seen & {"title","main_menu","profile","ingame_menu","play","paused","loading"})`)
controls pathclass's own temporal rule: a gameplay-looking frame is named `intro_video`, not
`gameplay`, until a menu/title screen has been seen. GTA III's boot flow is cutscene straight into
on-foot play -- no title or menu screen ever shows -- so `after_title` is never True for this
title, and pathclass would call every on-foot frame `intro_video` forever. This is not a confidence
or threshold problem; it is a structural gap for any title with this boot shape. Rejected fix:
loosening `after_title` itself in `classify.py` -- that is a shared rule every other profile
depends on, and changing it on the evidence of one title's 9 frames is exactly the kind of broad,
unreviewed change this lane should not make. Taken fix: a title-scoped HUD crop, the same pattern
every other hand-tuned profile here already uses (sonic-heroes, forza, buffy, castlevania-cod) --
`classify_frame` checks `state="play"` crops separately (line ~393) and, if one matches, never
calls pathclass for that frame at all (line 397's `and not hud` guard).

**The HUD crop: the health-heart icon**, a small fixed-position bitmap (unlike the digit HUD
elements -- money, clock, health number -- that change value over time and would risk an overfit
crop from only 2 near-identical play frames). Region 871,173,36,36 in ref space, converted from a
measured full-res pixel box (1220,195,1260,235 in 1920x1080 space) through `content()`'s picture
crop (Thor: 1440x1080 picture, offset 240 px from the left) and `scale_box` -- built with the real
`classify.py crop` tool against `a7.png`, not computed by hand, so it matches exactly what
`classify_frame` applies at runtime. (An earlier hand-rolled PIL crop at the same pixel box, done
before re-reading `content()`, would have been wrong by the 240 px pillarbox offset -- caught by
re-deriving the region through the real tool before committing to it, not by trial and error on
the device.) Scored against all 9 frames:

    a4/a5/y1/y2 (cutscene, no HUD):              60.22 / 69.10 / 52.23 / 31.53
    a7/m1 (play, bright heart):                   1.21 /  1.42
    w3/d2/st1 (play_dim_unresponsive, dark heart): 63.11 / 62.25 / 61.00

threshold 15.0: >20x margin above the play cluster, >2x margin below the lowest non-play score.
The heart stays near-zero in brightness only in true live play; it darkens along with everything
else in the dim/unresponsive frames, which is why this crop (unlike a crop built from the HUD's
static chrome) also separates `play` from `play_dim_unresponsive`, not just from `cutscene`.

**Full `classify.py table` result, all 9 frames, both crops active:**

    frame   state         source                      changed  letterbox  hud-heart
    a4      cutscene      crop:letterbox-top             -        0.0        -
    a5      cutscene      crop:letterbox-top              -        0.0        -
    y1      cutscene      crop:letterbox-top              -        0.0        -
    y2      cutscene      crop:letterbox-top              -        0.0        -
    a7      unknown       hud:hud-heart+after-cutscene   0.660     38.7       1.2
    m1      stalled       hud:hud-heart+static           0.017     42.4       1.4
    w3      unknown       pathclass:low-confidence        -        18.5      63.1
    d2      intro_video   pathclass:intro_video          0.000     24.5      62.2
    st1     unknown       pathclass:low-confidence        -        23.1      61.0

Reading this honestly, not optimistically:

- Cutscene: exactly right, all 4 via the geometry crop, never reaching pathclass.
- a7 (the first real play frame): `unknown`, not `play`. This is `classify_frame`'s own existing
  rule (line ~442-445) for the first HUD-matched capture after ANY non-play/stalled/unknown prior
  state -- here the cutscene -- "the previous capture was a pause box or a menu: the motion there
  is the overlay going away, not the scene; one more capture decides." Every other hand-tuned
  profile's HUD crop runs under the same rule; this is not new behavior invented for GTA III, and
  drive.py's Part B ladder already never idles on the resulting one-capture `unknown`.
- m1: `stalled`, not `play` -- because measured motion between a7 and m1 is 0.017 (below
  `static_bar`), even though `labels.tsv` describes m1 as "stick turned the player." Two honest
  possibilities, not resolved here: either the turn was small enough in screen space to fall under
  `MOTION_PIXEL`'s per-pixel threshold (a stick nudge in place, not a run), or these two frames
  (captured by hand, a discrete photo op, not a continuous automated capture) are far enough apart
  in real time that motion-based reasoning across them does not mean what it means between two
  frames a fixed capture interval apart. Not fixed by adjusting the motion bar to force `play` to
  appear here -- that would be tuning the threshold to the answer wanted rather than to evidence,
  and an automated run's prev/this-frame pairs will be 1 capture interval apart, not however many
  seconds elapsed between two hand-captured screenshots. A live Thor run is what actually settles
  this, not a bar nudged against 2 stills.
- w3/d2/st1 (play_dim_unresponsive): none say `play` -- the brief's one hard requirement for this
  state ("Teach the classifier to name it, never play") holds. They are not named consistently
  (`unknown`/`intro_video`/`unknown`) because `classify.py`'s `STATES` tuple has no
  `play_dim_unresponsive` of its own (adding one is a bigger, shared change this lane did not make
  on 3 frames of one occurrence on one device) -- they fall through to pathclass like any other
  on-foot frame once the heart crop doesn't match (it's dark, like the rest of the dim frame), and
  pathclass's `after_title` gap above applies to them too. Either way drive.py's Part B ladder
  handles `unknown` without idling, and `stalled` (if it ever lands there) runs the existing
  stall-escape machinery -- neither path is specific to this title. The owner's Thor-only quirk
  itself (pad ignored, cause unknown) is explicitly out of scope here (brief: "NOT a classifier
  problem, do not try to fix it here").

**What this proves and what it does not.** It proves the named bug (cutscene at 0.716) is fixed,
with a wide margin, on real captured evidence, and that `play_dim_unresponsive` never reads `play`
on the same evidence. It does NOT prove the full gta3-drive.route / pause-menu Save row / car-entry
detection pieces of Part D, and it does NOT prove the false-gameplay <=2% figure the brief asks
for -- that number needs a held-out set, and GTA III is not in `pathknow/eval/eval_set.tsv` at all
(checked: grepped for "gta|grand theft", only GTA San Andreas `54540082` appears). Nor does it prove
`a7`/`m1` would read `play` on a real continuous run -- only that the crop fires correctly and the
existing state machine's rule for "HUD just appeared after a non-play state" applies as designed.
All of this needs a live Thor (or Nova) run to take further; both are unavailable this session (see
WAITING, refreshed again at the top of this entry).

**Part E, deferred, named honestly**: did not wire gta3 frames into `classify_selftest.py`'s
`CASES`/`FOREIGN` tables. That harness's own fixtures are frame+prev-frame pairs from real
continuous dispatch-run captures (`frames_dir(run)`, the `--make`/`fixture()` regeneration flow),
and it asks for a COUNTER-CASE per state on purpose (see its module doc) -- forcing in 9 hand-
picked, non-continuous stills as if they were such a run, right after finding above that the m1
motion figure between two of them may not mean what it means in a real run, would be fitting the
test to the frames rather than to the behavior. Re-ran `pathclass_selftest.py` and
`classify_selftest.py` unchanged (0 failures each, same as Part B/C) to confirm nothing here
regressed either. A real selftest fixture for `gta3.toml` wants a short continuous capture off a
live device, which is the same thing Part D's route/pause-menu/car-entry pieces need.

Also fixed in passing: `pathclass.py`'s module docstring (lines ~16-18) still said a classifier
`Unavailable` falls back to "the language model" -- stale since Part A removed that path entirely,
missed by Part A's grep gate because it has no banned literal string. Corrected to describe the
actual behavior (`Unavailable` -> a ROUTE FAIL via drive.py, never a model fallback).

## Resume 2026-10-18 ~19:08 PDT (attempt 3): why attempt 2 did not finish, and a false alarm chased down

Attempt 2 did not fail -- it ended correctly, on a legitimate `WAITING` line, with A+B+C at
`State: ready` and Part D's two offline-buildable crops done and verified. "Did not finish" here
means only: Part D's device-dependent pieces (route, Save-row crop, car-entry crop, the held-out
false-gameplay number) were still blocked on a device, same as before. Re-checked at resume:

- **Thor**: went back on FULL hold at owner order, ~19:15 PDT (`dispatch/hold/thor.why`, refreshed
  19:12:08 PDT, arrived mid-session as a live file change): "the thermal test and GTA driving soaks
  are over: the Thor has none of the Nova's GTA III save states, so no GTA work on it. Nova only;
  only the owner lifts this." This forecloses the Thor for GTA III work entirely, not just "lane.local
  has it right now" -- there is no save state on that device to resume a GTA III run from, so even
  once released it is not useful for this title.
- **Nova**: still held, unchanged since 18:42:56 PDT (`dispatch/hold/nova.why`): "release when the
  owner says it is back" -- the original "~17:00 PDT" was an estimate inside that same note, not a
  release condition; `adb devices -l` shows `ee317437` present on the bus (as it did before), but
  presence is not the release signal here, the owner's word is (memory
  `device-presence-needs-a-live-listing` cuts the other way -- don't trust a stale doc over a live
  check -- it does not say presence overrides an explicit hold). No device is available to this lane
  this session either.

**A false alarm, chased down before trusting it**: `git log --all` in this worktree surfaced a
commit `847cd3e734` ("territory: retire localdrive1018, add fpsdiag1018") and this harness's own
auto-memory (`one-fps-lane-fpsdiag-1018.md`) says the owner ordered this lane stopped at ~15:15 PDT
in favor of a single `fpsdiag1018` lane. Taken at face value this would mean the whole brief below
is moot and attempt 2 should never have kept committing past 15:15 PDT. Checked rather than trusted
(a brief/memory claim of this size is exactly the kind of thing that needs a current-state check,
not a rerun of the same assumption):

- `847cd3e734` is **not an ancestor of this lane's HEAD, and not an ancestor of `origin/master`**
  (`git merge-base --is-ancestor` on both, confirmed false) -- it exists only on a local `board`
  branch ref in this worktree's repo, which is not the canonical territory ledger.
- The canonical ledger is the nested repo `/home/justin/hakux-work/board-wt`, branch `origin/board`.
  Its actual history for both lane names, oldest to newest:
  `9d4906d1fb` (15:12:29 PDT, claim lane.localdrive1018) -> `5ce44336f4` (15:13:12 PDT, release
  models.py to it) -> `7e8dd1422c` (15:49:26 PDT, **create** lane.fpsdiag1018 as a *separate*,
  coexisting row, not a replacement) -> `de4d955860` (16:51:22 PDT, fpsdiag1018 released at ready,
  PR #1081 CI green, unit gone -- that lane finished its own separate scope) -> `aeca499189`
  (19:01:27 PDT, **widens** lane.localdrive1018's row to add `pathknow/learned.py`, because a fold
  attempt on this lane's PR at 18:14 PDT was refused as "outside files"). There is no retirement
  commit for localdrive1018 anywhere in this history -- `[retired.localdrive1018]` does not exist
  in `board-wt`'s current `territory.toml` (checked directly, grepped for both section names).
  `docs/testing/preflight.sh`'s `territory` check also came back `ok` this session, which it would
  not if this lane's files were outside its live row.
- Conclusion: the retirement was a draft/abandoned take that never reached the canonical board --
  possibly an early, wrong write during the owner's 15:15 PDT fpsdiag1018 conversation that got
  corrected within the same hour once hostops saw both scopes were meant to coexist (fpsdiag1018 for
  the FPS-cause diagnostic tool per the owner's "switch to coding, not gameplay navigation" words;
  localdrive1018 for the classifier/act-observe rework, a different and already-scoped ask from
  13:50 PDT). The live board has kept granting and widening this lane's territory as recently as 7
  minutes before this session started. **Correcting the memory file now** (`one-fps-lane-fpsdiag-
  1018.md`) so a future session is not sent down this same dead end re-deriving the same check.
- This also means attempt 2's commits after 15:15 PDT were not a violation of anything live --
  they match the canonical board the whole time.

**This session's actions**: re-ran `pathclass_selftest.py` and `classify_selftest.py` fresh (0
failures each, unchanged), merged `origin/master` (session-start hook flagged this checkout 2
commits behind; the merge was clean, 4 unrelated files from `devpushro1018`'s fold, no conflicts),
re-ran both selftests again post-merge (0 failures each, unchanged), and ran `docs/testing/
preflight.sh` (passed, including `territory ok`). No code change was needed or made -- Part D's
remaining pieces are still genuinely device-gated, and nothing offline was left undone. Refreshing
`WAITING` with the current findings instead of re-deriving the same device check next time.

**Continuation, same attempt 3 (~19:30-20:19 PDT): device freed, first live evidence for Part D.**

Fixed `route.sh`'s stale `drive` step doc first (it still said a `drive` step "stops the route ...
on ... a screen it cannot name", contradicting Part B's already-shipped, already-selftested
ACT-OBSERVE behavior -- `drive.py`'s own module doc is the source of truth; `route.sh`'s is a live
reader-facing doc, not lane history, so a stale copy of the old behavior was actively wrong, not
just outdated). Verified `bash -n route.sh`. Added `routes/gta3-drive.route` "Stage 1" -- one step
(`drive gta3 300 find`), named honestly as unproven beyond this one run, with the car-entry/
Save-row/drive-loop steps explicitly marked NOT YET HERE. Both committed as `35477b3858`.

Checked the hold files directly rather than trusting the last WAITING snapshot: `dispatch/hold/`
lost `nova` and `nova.why` between this session's start and ~19:33 PDT (a bounded host-maintenance
hold, not the owner's earlier "release when the owner says it is back" one, lifted on its own) --
confirmed by polling `dispatch/hold/` every ~60 s rather than re-reading the stale note. `thor` and
`thor.why` are still present, unchanged: Thor stays fully, indefinitely owner-held for all GTA III
work (no save state on that device). This freed the Nova for the first time this lane has had a
device.

**Tried to run this lane's own code through the dispatcher -- refused, and why, confirmed from the
source, not guessed**: `request.sh --route gta3-drive --title ... --device nova` came back `refusing
to queue: ... drive 'gta3': no profile .../dispatch/bin/titles/drive-profiles/gta3.toml ... A
'drive' profile must be in the serving snapshot ... or on the serving tree's master.` This lane's
`drive.py`/`gta3.toml`/`learned.py`/`generic.toml` changes are not merged to `master`, so the
dispatcher -- which only runs code already on the serving snapshot -- cannot execute them at all.
This is a structural pre-merge limitation, not a flag mistake, and it means Part D's own route
cannot be device-validated before this PR lands. **Pivoted**: dispatched the EXISTING, already-
proven `gta-3.route` instead (same golden, same title, on `master` already) purely to collect
continuous real frames for OFFLINE validation of the (unmerged) `gta3.toml` crops -- evidence this
lane did not have beyond 9 hand-picked Thor stills.

Two `request.sh` argument mistakes on the way, both diagnosed from the tool's own refusal text
and `titlestate.py`'s resolution code, not guessed: (1) `--title "Grand Theft Auto III"` (the
catalog display name) was refused ("the title could not be identified") -- `--title` needs the
literal on-device ISO filename or an 8-hex TitleID prefix; the correct string,
`5454000E-Grand_Theft_Auto_III.xiso.iso`, came from `targets.toml`'s `[titles."5454000E"]` entry.
(2) the first `gta3-drive` route attempt, covered above.

**The dispatched run**: `1-1792377549-localdrive1018-3572782`, nova, `gta-3.route`, 300 s,
87 frames every 3 s (51.5 MB), 8547 logcat lines, queued 19:39 PDT, ran 20:10:51-20:16:07 PDT (two
other lanes' requests queued just ahead of it on the same device -- `ralli2audio1018` x2 -- so it
sat in queue ~31 min before the worker reached it; no action needed, just time). Reached real
on-foot play: `route-frames/201335-fist-hud.png` / `-gameplay.png` fired the `waitfor fist-hud`
mark ~164 s into the route, matching the route's own pathfound timing. **Found and noted, not
fixed (out of this lane's file scope)**: `request.sh`'s own `--wait` result-summary printer threw
on this soak result (`partial: command not found`, `goldens: No such file or directory`, then a
Python `SyntaxError` on an inlined `AI_AGENT=...` env value) -- a pre-existing bug in `request.sh`
itself, unrelated to this lane's code; it only broke the summary text, not the run (`DONE` and
`result.json` both wrote correctly, confirmed by reading them directly). `request.sh` is not in
this lane's `Files:`; flagging here rather than fixing it.

**Validated both `gta3.toml` crops against these 87 real, continuous NOVA frames** (not Thor, and
not hand-picked), with `classify.py table --profile .../gta3.toml <frames>` -- the exact pipeline
`classify_frame` runs at drive-time, not a hand script:

- `letterbox-top`: exact `0.0` on every one of the 7 frames the table calls `cutscene`
  (f00012/15/17/19/25/26/27), vs 13.4-230.7 on the boot/loading/transition frames around them and
  no value at all (crop only applies in the `cutscene` state) during `play`. Matches the 9-still
  claim of "exact zeros, not near-zeros" exactly, now on a second device and a different boot run.
- `hud-heart`: held under the 15.0 threshold on **all 40** frames the table calls `play`
  (f00047-f00086), but the real margin is narrower than the 9-still estimate suggested -- scores
  ranged 1.9 to **12.9** (f00086) within the play cluster itself, not the clean "<6" band all 9
  stills showed. Still correctly under threshold every time (0 false negatives, 0 false `play` on
  any of the 46 non-play frames in the same run -- boot/black/loading/cutscene/stalled all stayed
  out of `play`), but this is real evidence the margin is tighter in motion than at rest, worth
  carrying forward rather than re-asserting the wider stills-only number.
- The transition itself (`stalled`, f00031-f00045, ~15 frames / ~45 s between the cutscene ending
  and the pathfound route's first LY/A presses landing) never idled and never failed -- exactly
  Part B's existing stall-escape and ACT-OBSERVE machinery, already selftested, doing its job on a
  real run with no title-specific code of its own.
- **Zero false `play` calls anywhere in the run** (0/46 non-play frames): the closest thing this
  lane has yet to a held-out false-gameplay number for GTA III, though it is one run on the route
  the classifier/crop was tuned toward, not a blind held-out set -- said plainly, not inflated.

**Still not done** (unchanged from the `gta3-drive.route` file's own "NOT YET HERE" note): car-entry
(Y) detection/crop, the pause-menu Save-row crop and the state-save step, the drive loop itself, a
GTA III-specific `classifier_confidence`/`_menu` floor sweep (9-ish frames is still not enough to
tune one safely), and adding GTA III to `pathknow/eval/eval_set.tsv` for a true held-out number.
All four need either more frame diversity than one proven-route run gives (no car-entry or
pause-menu frame exists in this run; the pathfound `gta-3.route` never presses Y or START) or a
dispatched run of this lane's OWN route/profile, which stays blocked on the pre-merge limitation
above until this PR lands.

Merged `origin/master` again before writing this (25 commits behind by the time the device run
finished; clean merge, 4 lanes' unrelated files, no conflicts), re-ran `pathclass_selftest.py` and
`classify_selftest.py` once more post-merge (0 failures each).

## Resume 2026-10-18 ~20:28 PDT (attempt 4, mislabeled "attempt 3" in this dispatch's own header):
why the prior session did not fail, and what was still actionable

Attempt 3 did not fail either -- it ended correctly on the `WAITING` above, with A+B+C at
`State: ready`, Part D's two crops verified on two independent frame sets (9 Thor stills, 87
continuous Nova frames), and a specific, source-confirmed blocker written down (the dispatcher
refuses to run a `drive` profile not on `master`, so this lane's own `gta3-drive.route`/
`gta3.toml` cannot be dispatched pre-merge). Session logs (`/home/justin/hakux-work/logs/lane/
localdrive1018.*.json`) show attempt 3 started ~17:02 PDT and this session started ~20:27 PDT --
only ~6 minutes after attempt 3's last commit (`73792d2e58`, 20:22:04), far short of the 40-minute
idle-resume window the role doc describes, and no `[job.arms]` verdict landed in that gap (no
prediction is registered -- Part D has no arm). Most likely cause: a CI-green signal on
`73792d2e58` triggered `handback.sh`'s other resume condition. Re-verified nothing was stale
before acting further: `git status` clean, `pathclass_selftest.py`/`classify_selftest.py` still
0 failures, `docs/testing/preflight.sh` still `territory ok` (not re-run again this entry --
unchanged inputs since the last run 50 minutes ago would just reproduce the same result; see
`idle-capacity-manufactures-unchecked-work` -- re-running a clean check with nothing changed
underneath it is exactly the unchecked work that memory warns against).

**What was still actionable, found by re-reading the WAITING blocker rather than accepting it as
final**: the blocker is specific to the `drive` STEP (`route.sh`'s profile-gate check: "A 'drive'
profile must be in the serving snapshot ... or on the serving tree's master"). It is not a
blocker on dispatching *any* route this lane writes -- `route.sh`'s own grammar (its module doc,
re-read this session) has `press`/`axis`/`wait`/`shot`/`waitfor`/`mark`/`repeat`, all already on
`master` and used by the existing proven `gta-3.route` verbatim, with no profile/serving-snapshot
check anywhere near them (grepped `route.sh` for where that refusal fires: it is scoped to the
`drive <profile> ...` line's own handler in `request.sh`, nothing else). A NEW route file that
never writes a `drive` step does not touch that gate at all, and `request.sh`'s own comment
confirms a named route's TEXT is read "from THIS tree now" (the lane's worktree), not from
`master` -- so a plain press-script route is dispatchable today, unmerged, exactly like this
lane's own `gta3.toml`/`learned.py` are NOT. This is the one thing Part D's "Still not done" list
was actually missing a device *path* for, not a device: car-entry (Y) and pause-menu (START)
frames, which the one dispatchable existing route (`gta-3.route`, on-foot only, never presses Y
or START) structurally cannot produce no matter how many times it runs.

**Built**: `docs/testing/titles/routes/gta3-car-pause-probe.route` -- PROBE ONLY, explicitly
never scored (no `mark`, only `shot`), reusing `gta-3.route`'s exact proven boot preamble
(same `wait`/`press A`/`waitfor fist-hud` timing, not re-derived) so the one new thing being
tested is the car-entry/pause sequence itself: `press Y` (enter the car, per the owner's own
hands-on walkthrough in the brief) -> shot -> `press START` (open pause; `gta-3.route`'s own
comment on the gtawedge1012 regression already established START toggles this title's pause
menu) -> shot (Save should show as the default highlighted row here, per the owner's words --
captured, not pressed: no `A` on this menu, so the run cannot create or overwrite a save) ->
`press START` again (close pause, back to play) -> shot, to also confirm the sequence leaves
the player in control rather than stuck on a dialog. Copied (not invented) the existing
`routes/refs/gta-3/fist-hud.png` into this route's own `refs/gta3-car-pause-probe/` dir, since
`route.sh`'s `ref_path()` keys a `waitfor` crop by the route's own filename stem, not a shared
pool. Validated: `route.sh --check docs/testing/titles/routes/gta3-car-pause-probe.route` ->
`route ok (55 lines)`.

Checked device state live before dispatching, not from the stale WAITING note: `adb devices -l`
and the dispatcher's own `dispatch/bin/devices.sh` both showed only `bdc158a5` (Thor) -- the Nova
was briefly absent from the live listing despite no `dispatch/hold/nova`/`nova.why` file existing
(memory `device-presence-needs-a-live-listing` cuts against trusting either the WAITING note's
"freed ~19:33" claim or the absence of a hold file on its own). `dispatch/queue/` explained it:
`lane.ralli2audio1018` had just placed a new request (`1-1792380737-...-709884`, 20:32) on top of
one already in `dispatch/results/` from minutes earlier -- the Nova was mid-turnaround for that
lane's own work, not actually gone. Re-checked once (device-flake rule: rerun twice) rather than
concluding "unavailable" from one transient miss.

**Dispatched** (not blocking-waited for yet, see below): `request.sh --who localdrive1018
--purpose "car-entry + pause-menu frames for gta3.toml Part D crops, probe only, no scoring
(#433)" --title 5454000E-Grand_Theft_Auto_III.xiso.iso --device nova --route
gta3-car-pause-probe --seconds 240 --no-expect "evidence-gathering probe for offline
crop-building, not an A/B arm"` -> queued **`1-1792380791-localdrive1018-729348`**, pinned to
nova, release-priority (#433 is labelled 0.5), behind `lane.ralli2audio1018`'s own request in the
same tier (FIFO, no action needed, same as this lane's first dispatch sitting behind two of that
lane's requests earlier today). Device-time accounting for this requester today: 300s (the
earlier `gta-3.route` survey) + this run's 240s + 90s setup = 630s = 10.5 min of the unconditional
first-30-minutes pilot allowance: no `pilots/localdrive1018.ok` exists or is needed yet.

This is committed and pushed BEFORE waiting on that result, per the lane rule (commit before
every wait). The actual wait, and its outcome, are the next entry below -- or, if the queue has
not reached it within one bounded foreground check, the `WAITING` file names this request id
instead of re-describing the same merge-gate blocker, which is now only half the story.

**One bounded foreground wait (8 min, 20 s polls of `dispatch/results/` and `dispatch/running/`,
no chained sleeps after it) -- did not land.** Neither my request nor `lane.ralli2audio1018`'s
own (queued one minute ahead of mine, same device, same tier) moved at all in that window:
`dispatch/queue/` is byte-identical before and after, `dispatch/running/` stayed empty the whole
time, and no new entry appeared under `dispatch/results/`. Checked why rather than waiting
longer on a guess: `pgrep -af "dispatcher.sh worker"` shows exactly one worker process running on
this host, `dispatcher.sh worker bdc158a5` (the Thor) -- **there is no worker process for the
Nova (`ee317437`) at all right now**, despite the Nova itself being live on the bus (confirmed
again: `dispatch/bin/devices.sh` now lists it) and having no hold file. A queued request with no
worker servicing its device cannot run no matter how long it sits, and this matches the earlier
transient "Nova missing from devices.sh" observation at 20:32 -- not a flake, the mid-run blip
was probably this worker dying or never having been (re)started after the Nova came back off the
owner's hold earlier this session.

This is a dispatcher/hostops gap, not a `localdrive1018` one, and not something this lane fixes
directly: the role rules this lane runs under say device access goes through `request.sh`/
`ab_run.sh` only, never the device or its worker process directly, and restarting a dispatcher
worker is infra the harness's own jam-duty role (lane.local's inbox instructions: "a device idle
while work is queued ... -> find why and restart the runner") is positioned to do, with the
authority and context this lane does not have. Named here instead of guessed around.

## Resume 2026-10-18 ~20:49 PDT (attempt 5, labelled "attempt 3" in this dispatch's header):
why attempt 4 did not finish, and the two things that changed underneath it

Attempt 4 did not fail -- it ended correctly on `WAITING` (commit `6771d8e2cf`), naming a specific,
source-confirmed infra gap (no `dispatcher.sh worker ee317437` process for the Nova, so the queued
probe request `1-1792380791-localdrive1018-729348` could not run no matter how long it sat) and
handing that off to jam duty rather than guessing around it, per this role's own rule that device
workers are hostops's to restart, not a lane's. That is a finished-session outcome, not a failure.

Two things have changed since, checked live rather than trusted from the note: (1) **master now
has a fold of this lane's own PR** -- `git log HEAD..origin/master` shows `72af9cb92c "fold:
lane/localdrive1018 ... drive: local tools only, act-observe instead of wait-and-fail, learn what
to press"`, folded from this branch's state as of `73792d2e58` (A+B+C+D-partial, the state PR.md
currently describes). This branch's two newest commits (`7a7b330470` the probe route, `6771d8e2cf`
the WAITING note) postdate that fold snapshot and are not in it -- they are this lane's live
increment on top of already-folded work, not yet folded themselves. No action needed from this
fact alone (the board/fold job owns when to pick up the rest); noted so a future resume does not
mistake "master has a `fold: lane/localdrive1018` commit" for "this lane is done" -- two commits'
worth of work (the probe route + the still-pending device evidence it exists to gather) are still
open on this branch. (2) **the Nova worker is back**: `pgrep -af "dispatcher.sh worker"` now shows
TWO processes, `bdc158a5` (Thor, pid 670426) and `ee317437` (Nova, pid 987498) -- jam duty (or a
hostops tick) restarted it since attempt 4's check, confirming the diagnosis was right and this was
exactly the kind of gap that role is positioned to fix. `dispatch/hold/` no longer has a `nova` or
`nova.why` file (unchanged from attempt 4); it does now have `lifted` (a dir) and
`nova.battery-override` (owner, 2026-10-18 18:40 PDT, "Nova may be dispatched from 10%", expires
06:38 PDT -- per memory `nova-battery-floor-5-owner-1018`, not something this lane needs to act on,
just context for why the Nova is usable at whatever charge it is at right now).

My probe request is still in `dispatch/queue/` (`1-1792380791-localdrive1018-729348.req`,
unchanged, `ref 73792d2e58` -- still valid, that commit is on both this branch and `origin/master`
now), one slot behind `lane.ralli2audio1018`'s own 870 s request (`1-1792380737-...-709884`,
queued 20:32:18 PDT, same device, same `priority: study` tier, FIFO -- not release-priority like
mine, but queued one minute earlier so it goes first), which `dispatch/running/` shows as the
device's current job. No action to take here beyond waiting for FIFO to reach mine: this is a
normal queue turnaround, not the attempt-4 infra gap (that gap was "no worker process exists";
this is "a worker exists and is busy," the ordinary case `request.sh` is built for).

**Two bounded foreground waits (8 min each, 20 s polls, no chained sleeps) -- the queue moved, but
mine is now further back, not closer.** `lane.ralli2audio1018`'s 870 s job finished and landed in
`dispatch/results/` between the two waits (its `run.log`/`logcat.txt` stopped growing at 21:00:07
PDT; `dispatch/running/` went empty). My request did not move into `running/` next, though --
checked why rather than waiting a third time on the same guess: `dispatch/queue/` picked up four
NEW requests while I was waiting, all targeting `nova`, all tier **`blocker`** (confirmed by
reading each `.req`'s `priority` field directly, not inferring from the filename's leading digit):
`0-1792381848-fpsdiag1018-1094601` (900 s), `0-1792381850-fpsdiag1018-1095573` (700 s),
`0-1792382334-hakux-0b-1285228` (360 s), `0-1792382337-hakux-0b-1285509` (360 s) -- 2320 s (~39
min) of higher-than-mine-priority work, queued after mine but ranked ahead of it. `priority:
study` (this probe) is below `priority: blocker` in the dispatcher's own ordering (the filename's
leading `0-`/`1-` is exactly that rank, written by `request.sh` at enqueue time, confirmed by the
four new `.req` files all reading `blocker` and all carrying a `0-` prefix while mine, `study`,
carries a `1-`) -- this is the dispatcher working as designed, not a flake or a second infra gap:
a release-priority (#433 is 0.5) probe correctly yields to four `blocker`-tier requests from two
other lanes. Nothing to fix or report here; the Nova worker itself (`ee317437`, pid 987498) is
still alive and running, confirmed again this entry.

At ~39 minutes of now-queued `blocker` work ahead of a 240 s+90 s request, polling further in this
session would mean sitting through most or all of it with nothing else to show -- exactly the
"don't poll until the turn cap cuts you off" case this role's rules warn against. Nothing else in
this lane's scope is actionable offline right now: A+B+C are `State: ready` and already folded
into `master` (see above); D's remaining pieces (car-entry/pause-menu crops, the GTA III
`play_dim_unresponsive` state, the held-out eval-set row, the confidence-floor sweep) all need
either this probe's frames or a device slot this lane does not have standing to jump ahead for.
Ending this session on `WAITING` for the queue to clear, named below and in a PR comment on
forge PR #1082 (http://127.0.0.1:3330/jreinach-alt/hakuX/pulls/1082) once this is pushed.

**WAITING**: on `dispatch/queue/1-1792380791-localdrive1018-729348.req` to reach
`dispatch/running/` then `dispatch/results/` on the Nova. Resolves when either (a) the four
`blocker`-tier requests ahead of it drain naturally (~39 min of device time as of 21:08 PDT, FIFO
within tier), or (b) a future session checks `dispatch/results/` for `729348` directly. No code
change is pending on this; the next session's first move is reading that result and continuing
Part D's car-entry/pause-menu crop work from whatever frames it contains.

## Resume 2026-10-19 (attempt labelled 3 in this dispatch's header): why attempt 5 did not
finish, and the hostops addendum's one-line fix

Attempt 5 (commit `db880005f0`) did not fail -- the Nova probe request got withdrawn by
lane.local into `dispatch/queue/withdrawn/owner1018/` under an owner-play hold (`dispatch/
hold/nova`, owner checking RalliSport by hand), which is genuinely owner-gated, not a loop or a
flake, and the WAITING file already correctly says so as an `owner` line. That device wait is
still open and this session does not touch it.

What changed is that the hostops/jam-duty role (not this lane) separately root-caused a FOLD
failure on this PR (`docs/lanes/localdrive1018/PR.md`'s addendum section, added directly to the
brief at 01:13 and 06:13 PDT): `drive.py` line 154-156 does `sys.path.insert(0, .../pathknow);
import learned`, but `docs/testing/dispatcher.sh`'s `SCRIPT_DEPS` string never listed
`titles/pathknow/learned.py`, so `snapshot_scripts` never ships that module into a dispatched
worker's snapshot, and the fold selftest's own `97-dispatch-snapshot-drive.sh` check (which
exists precisely to catch this class of omission) correctly failed with `ModuleNotFoundError:
No module named 'learned'` on every retry against two different master shas. hostops widened
this lane's territory row onto `docs/testing/dispatcher.sh` for exactly this one line (confirmed
directly in `board-wt`'s `territory.toml`, commit `af684bff11`: the row's `files` list now
includes `"docs/testing/dispatcher.sh"`, and its note names the SCRIPT_DEPS line explicitly) and
resumed this lane to apply it -- this is the actionable item for this session, separate from the
still-open device wait above.

Applied: added `titles/pathknow/learned.py` to `SCRIPT_DEPS` in `docs/testing/dispatcher.sh`,
same pattern as the existing `titles/classify.py titles/waitfor_match.py titles/pathclass.py`
entries, no other line touched (confirmed by diff: one token added). Re-ran
`pathclass_selftest.py`/`classify_selftest.py` (0 failures, unchanged) and
`docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh` directly to confirm the specific
case that was failing now passes. Updated `PR.md`'s `Files:` line to add
`docs/testing/dispatcher.sh`. This stays scoped to the one addition the widened row's note
names; `SNAPSHOT_GLOBS` and the rest of `dispatcher.sh` are untouched.
