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

## Open questions (not blocking; keep working)
- Whether pathclass.py already exposes the embedding vector for an arbitrary frame as a reusable function,
  or only as an internal step of classify_frame -- checking next.
- Exact schema for the learned JSONL -- drafting in the next NOTES.md update before writing any code that
  writes one.
