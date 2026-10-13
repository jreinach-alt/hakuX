# lane.pathrules1013 -- pathfind: no-answer steps never become a path, a hold that can no longer pass ends, a perflog run never banks (#433, 0.5)

Brief: `/home/justin/hakux-work/briefs/pathrules1013.md`. Three fixes to `docs/testing/titles/pathfind.py` plus
one to `docs/testing/title_verdict.py`, done in order, one lane because they share the file.

## Part A -- a step the model never answered is not a path

`write_path` already drops a `no_answer_step` (`state: "unknown"`, `why: "model gave no answer"`) going forward
via `break`, but a `complete: false` path written *before* this fix still has one on disk, and a path *loaded*
from such a file was never re-filtered. Fixed both directions:

- `write_path`'s loop now `break`s on the first `no_answer_step` before appending it, with `if not keep: return`
  guarding the case where every recorded step is cut (an empty path is not written at all).
- `load_paths` now runs every loaded step through a new `cut_no_answer`, matching on `state == "unknown"` and
  `why == "model gave no answer"` only -- a loaded/recorded step carries no `src` field (that's a live-step-only
  attribute of the walk, not something `write_path` serializes), so matching on `src` the way a live check might
  would silently never fire on disk.

**Verified** against the two fixtures named in the brief, both read-only in `/home/justin/hakux-work/wt/pathfind/`
(lane.pathfind's run folders, not this lane's):
- `docs/lanes/pathfind/runs/n-4541005F-1011/pathknow/paths/4541005F.json` (LotR: The Third Age) -- the
  `diverged`-at-step-0 path -- reduced from 1 to 0 steps.
- `docs/lanes/pathfind/runs/n-544D0011-1011/pathknow/paths/544D0011.json` (Gene Troopers) -- no-answer steps at
  0, 17, 18 -- reduced to 0 steps (step 0 is itself a no-answer step, so `cut_no_answer`'s first cut already
  empties the path; steps 17/18 would also have been cut had anything survived to reach them).

Both paths-under-test used in the brief's literal filenames (`paths-void-1012/544D0008.json`,
`.../56550018.json`) were themselves fixtures built by the parked lane.pathvoid1012 for exactly this bug, also
under `/home/justin/hakux-work/wt/pathfind/docs/testing/titles/pathknow/`; both likewise reduce to 0 steps.

## Part B -- a hold that can no longer mathematically pass ends early

**The rule.** `hold_bar_unreachable(play_s, window_s, budget_left_s, bar=0.10)`: `off = window_s - play_s`
(seconds of the scored window that were NOT play); unreachable when `off > bar * (window_s + budget_left_s)` --
i.e. even if every remaining second of budget were perfect play, off-play share still could not fall to the bar.
Pure function, reads only the verdict's own timeline (`play_s`, `scored_s` from `provisional_verdict`'s
`title_verdict.py` call), genre-agnostic: it is arithmetic over play-share alone, so it applies to every hold
(`attack`, `shooter`, whatever `genre` names) without special-casing -- the genre only ever chose *how* a hold
measures "played", never whether this check fires.

**Why not `hold_shortfall`.** `hold_shortfall(v, need_s)` has its own duration gate: `gameplay_s < need_s` returns
`('duration', need_s - gameplay_s)` *before* reaching share arithmetic, so a hold that is failing on share but
hasn't yet reached `need_s` of recorded gameplay reports "needs more duration" -- true, but useless for "is this
hold salvageable", since more duration is exactly what it has plenty of and exactly what won't help. Confirmed
on real data below: at PoP's cut=400s, `hold_shortfall`-style reasoning is still `"duration: 400 s of gameplay <
600 s confirmation"`, the wrong diagnosis 11s before the real crossover.

**Wiring.** `Agent.hold_unsalvageable(play_s, budget_left_s, log)` calls `self.provisional_verdict()` (the same
helper `hold_check` already uses -- builds a `provisional/` folder from a logcat snapshot, invokes
`title_verdict.py` via subprocess, 120s timeout), reads `timeline.play_s`/`timeline.scored_s` off the result, and
confirms `hold_bar_unreachable` against them (not against the hold loop's own running tallies) -- the verdict is
the referee here, this function just asks it a sharper question. Any of: no verdict yet (subprocess
timeout/`OSError`/`ValueError`, matching `provisional_verdict`'s existing contract), `timeline` not a dict,
or no `play_s`/`scored_s` -- returns `None` (unknown, not a failure; the hold keeps going). Wired as a new
`elif` branch in the hold loop, parallel to (not reusing) the existing `hold_check` branch; reason strings name
the off-play seconds, the window, and the budget left, e.g.: `"off play 360 s of a 400 s scored window cannot
drop to 10% with 2000 s of budget left: no amount of further play can pass"`.

**Does NOT touch the step cap / ladder.** The 10-06 owner order ("no cap ends a hold while budget remains") is
untouched -- this is a new, independent exit a hold can take when the arithmetic says no amount of *remaining*
budget can rescue it; a hold that is merely slow still runs its full ladder.

**Evidence (all read-only, `/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs/`):**

- **PoP: Sands of Time, `n-5553001D-1013d/`** (`hold.ok: false`, `play_s: 197.1`, `need_s: 600.0`,
  `hold_s: 2013.4`, `reason: "budget 40 min with 197 s of play"`). Cut the real logcat.txt at successive
  `hold_el` points (mark gameplay `10-13 08:21:57.901` to soak end `08:55:32.359`, 2014.46s), re-ran the real
  `title_verdict.py` on each cut, computed `hold_bar_unreachable` against the verdict's own timeline (budget_left
  = 2013.4 - cut):

  | cut (s) | verdict pass | play_share (verdict's own timeline) | `hold_bar_unreachable` |
  |---|---|---|---|
  | 350 | FAIL | low, play_s flat at 209.9 from here on | False |
  | 400 | FAIL (`"duration: 400 s of gameplay < 600 s confirmation"`) | -- | False |
  | 410 | FAIL | -- | False |
  | 412 | FAIL | -- | **True** |
  | 2013.4 (full exhaustion) | FAIL (`"menu time: 10.4%..."`) | -- | True |

  Crossover is between hold_el 410s and 412s -- about 1601s (26.7 min) before the hold's actual give-up at
  2013.4s. At cut=400 the verdict is still in the duration regime (`hold_shortfall` would report "needs more
  duration", not "already unreachable") -- exactly the case the rule exists for: the failure visible at full
  exhaustion (menu time) was already mathematically locked in roughly two cuts earlier, at a point where
  `hold_shortfall`'s own reasoning pointed the wrong way.

- **25 to Life, `n-45530018-1013r/`** (`hold.ok: false`, but `play_s: 607.7 >= need_s: 600.0`,
  `hold_s: 609.1`, ends on fps -- NOT a share failure): cut at 60/150/300/450/600/609s, `hold_bar_unreachable`
  False at every cut (play_share 0.9959 to 0.9996 throughout), confirmed even under the strictest assumption
  (`budget_left_s = 0`, i.e. pretending no budget remained at all). The rule never fires on a hold that is
  passing on share.

- **"Recovered and passed" (a hold whose share dips, then climbs back over the bar before the budget runs out):**
  searched every run folder with a `ladder_round` entry in `hold.jsonl` -- all 16 (`crashwoc-1006`,
  `crashwoc-1007`, `doaultimate-1006b`, `marvel-1006`, `n-43430008-1007`, `n-434D0029-1007`, `n-46530005-1011`,
  `n-53430006-1013`, `n-5343000C-1013`, `n-53450004-1013`, `n-55530009-1007`, `n-58500001-1007`,
  `rehold2-4D570034`, `rehold2b-4D570034`, `strike-force-1006` (no result.json)) -- every one has `hold.ok: false`.
  No real example exists; per the brief's own fallback, built a synthetic fixture instead
  (`pathfind_selftest.py`'s `'unsalvageable'` leg, `RECOVERED = [(60, 10), (120, 20), (180, 35), (240, 130),
  (600, 550)]`, share climbing from 0.167 to 0.917 across checkpoints, 3600s budget) and confirmed
  `hold_bar_unreachable` never fires at any checkpoint, with the final checkpoint's 0.9167 share confirmed a
  real pass via `hold_shortfall`.

## Part C -- a perflog run never reads as a Playable candidate

Applied pathtele1013's suggested VOID-elif to `title_verdict.py`'s `judge()`:
```
elif res.get("build") == "perflog" or req.get("build") == "perflog":
    void = "build: perflog APK (~1.2 ms/frame render-thread overhead) -- a telemetry hold, never a Playable candidate"
```
plus `build=res.get("build") or req.get("build"), env=res.get("env") or req.get("env")` on the `v = dict(...)`
construction, so the field is visible on every verdict, voided or not.

**The deeper problem pathtele1013's author flagged but couldn't fix** (outside their territory,
`title_verdict.py` is this lane's): `res.get("build")` alone is `None` for every *provisional* (mid-hold) verdict
-- `result.json` doesn't exist until `finish()` writes it, so a perflog hold's own in-progress judging never saw
its own build. The `req.get("build")` fallback above covers `title_verdict.py`'s read side, but needed a write
side too: `hold_verdict` (the FINAL judge on the hold's own logcat, called at the end of `hold()`) was writing a
`request.json` with no `build`/`env` at all. Fixed by carrying them from `self.result` (same dict `finish()`
later persists to `result.json`, already populated with `"build": "perflog"`/`"env": [...]` by `perflog_start`
before the hold ever begins):
```
json.dump({"title": self.name, "title_id": self.tid, "device": self.dev.label,
           "iso": os.path.basename(self.iso or ""),
           "build": self.result.get("build"), "env": self.result.get("env")}, f)
```
`hold_check`'s own provisional folder already goes through the same `self.result`-sourced path (confirmed, not
touched by this lane). Net effect: a perflog hold now voids at every judge point in its life -- provisional,
hold-final, and the eventual `result.json` final -- not just the last one.

**Tests.** New `docs/testing/jobs/selftest.d/89-verdict-perflog.sh` (modeled on the read-only
`89-title-verdict.sh`, fixtures + a mutant per check so a vacuously-green check is caught): three fixtures
(`result.json`'s build voids; `request.json`-only build voids with no `result.json` on disk yet; a plain folder
with neither voids nothing) plus three `tv_mutant` checks (drop the void check entirely; read only
`res.get("build")`, reinstating the pre-finish() blind spot; void unconditionally regardless of build). Plus a
`pathfind_selftest.py` fragment (`perflog-holdverdict`) that calls `hold_verdict` directly on a fake agent
carrying `result = {"build": "perflog", "env": [...]}` and confirms the request.json it writes -- before any
result.json exists -- already carries both fields, and that running the real `title_verdict.py` against that
folder prints a VERDICT line that is itself voided.

**A bug in the new fragment, found and fixed in this session, not in `title_verdict.py` itself:** a mutant copy
of `title_verdict.py` written to `$T/tv-perflog-mutant.py` (outside `docs/testing/`) crashed with
`ModuleNotFoundError: No module named 'thermal_state'` on every invocation, mutated or not -- `title_verdict.py`
computes `HERE = dirname(__file__)` and inserts only *that* onto `sys.path` before `import thermal_state`, so a
copy run from anywhere but its own directory can't find its sibling `thermal_state.py`/`hitch_report.py`. Fixed
by exporting `PYTHONPATH="$TESTING"` around every invocation in the fragment's `verdict_void()` (real script and
mutant copies alike) and by making a non-zero exit report a readable `"$f: title_verdict exited non-zero"` line
rather than letting the verdict-reading one-liner crash on a missing file. The three direct fixture checks
(against the real, unpatched script) had already been passing throughout -- this bug only ever affected the
`tv_mutant` legs, which is also why it was caught: a mutant that can't run can't be "caught", so all three
mutant checks failed loudly (`FAIL mutant SURVIVED`) rather than silently passing for the wrong reason.
**This same latent issue likely also affects `89-title-verdict.sh`'s own `tv_mutant`** (same `$T/tv-mutant.py`
pattern, no `PYTHONPATH`) -- out of this lane's territory (read-only reference file), flagged here rather than
touched.

**Verified:** standalone (minimal `T`/`ok`/`bad`/`check` harness sourcing just the new fragment, avoiding
`selftest.sh`'s full gh/systemd/dispatch shim weight) -- `pass=6 fail=0`. Full
`python3 docs/testing/titles/pathfind_selftest.py` -- `pathfind_selftest: all ok` (824 lines of ok/FAIL output,
zero FAIL).

## Next lane should not repeat

- Don't reuse `hold_shortfall` for an early-exit decision -- its duration gate answers a different question
  ("how much more do you need") than "can you still pass" and will mislead exactly when it matters (see the PoP
  cut=400 evidence above).
- A mutant copy of `title_verdict.py` run from outside `docs/testing/` needs `PYTHONPATH` (or a copied
  `thermal_state.py`/`hitch_report.py`) -- a silent-until-tested `ModuleNotFoundError` otherwise.
- `hold_verdict` and `hold_check`'s provisional folder are two separate `request.json` writers; a `build`/`env`
  fix to one without the other leaves a gap (this is exactly the gap Part C's "deeper problem" closed).
