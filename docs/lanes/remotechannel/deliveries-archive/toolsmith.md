<!-- Archived verbatim from $DISPATCH_DIR/deliveries/toolsmith.md by lane.remotechannel
     on 2026-09-19. Host mtime at the time of copying: 2026-09-14T11:53:57Z.
     Nothing reads this copy; it is the RECORD of routing decisions that were
     really made, kept because the channel it was written on was retired and a
     record on one host's disk is not a record. The live channel is a
     [job.deliver] comment -- see docs/testing/jobs/deliver.sh. -->

# Deliveries to lane.toolsmith

APPEND-ONLY. The orchestrator writes here when it routes work. Read at session
start and after every message. See AGENTS.md, "Routing on paper is not routing".

## 2026-09-14 — the nv2a index gate punishes lanes for the previous fold

`lane.lows` arrived to a `preflight.sh` `nv2a index` failure of **396 entries,
all `vk/draw.c`, none of them its own** — measured by comparing the committed
index's recorded site text against its base and tip, not assumed.

The index is derived from the **whole tree**, so a lane that regenerates it
necessarily commits other lanes' churn, and three concurrent lanes produce
three conflicting 829 KB JSONs at the next fold.

**Decision recorded in `docs/audits/2026-09-14-decisions.md`:** fold-time
regeneration is the rule and the orchestrator owns it. That was already the
practice — `c58ce95249` is my own "my own merge moved 68 sites" — but practice
is not policy, so nobody could rely on it and every lane paid.

**What you own:** `preflight.sh`'s `nv2a index` gate should compare against the
**fold base** rather than the tip, so a lane fails only on drift it introduced.
`papercuts.toml` carries it as `index-gate-punishes-lanes`.

## 2026-09-14 — `nv2a_index.py` HEDGE false positive

It scores "may not be" as a hedge and fired on a **precise** sentence — "a
surface that may not be the current target". The lane reworded correct prose to
satisfy it: right in the moment, wrong as a pattern, because the false-positive
rate is paid by whoever reads the gap list next, and the daily DX pass reads it.
`papercuts.toml` carries it as `hedge-gap-false-positive`. Note `nv2a_index.py`
is not in your claim — flag it if you want it.

## 2026-09-14 — `[skip ci]` near-miss: FOUR occurrences, promote it

`papercuts.toml` `skip-ci-typo` is now `bit = 4`. The fourth landed minutes
after I logged the third, in a commit whose body discusses false-positive rates
in gap lists. It is not a git-behaviour problem — it happens in a plain heredoc
subject too — so it is a typing slip, and four occurrences is enough evidence
that knowing about it does not fix it.

**The gate is one line from catching it.** `preflight.sh`'s `commit subject`
step checks HEAD for the marker's PRESENCE and passes anything containing it. It
must also FAIL a near-miss: a bracketed token within edit distance 1 of
`skip ci` that is not `skip ci`. You hold `preflight.sh`.

This is the clearest case on the board for the DX pass's own premise — the cuts
worth fixing are the ones that recur, and this one recurs against an orchestrator
who has written it down twice.

## 2026-09-14 — `.lastbrief` should derive from the delivery file, not a separate stamp

`check_coverage.py`'s UNBRIEFED warning fired on `lane.remote` at 3.1h when I
had briefed it **twice** in that window. The warning was not wrong about the
file — I had not stamped `$DISPATCH_DIR/lanes/remote.lastbrief`, because that
stamp is a second thing to remember and I forgot it both times.

A check that depends on the orchestrator remembering to update it will read
wrong exactly when the orchestrator is busy, which is when it matters.

**Now that `$DISPATCH_DIR/deliveries/<lane>.md` exists, the stamp is
redundant**: routing writes to that file, so its mtime is the last-brief time
and cannot drift from reality. Derive it from there, and fall back to
`lanes/<lane>.lastbrief` only if no delivery file exists.

Same family as the `[skip ci]` near-miss: a step that depends on discipline,
where a derived value is available for free.

## 2026-09-14 — A RUN CAN BE SILENTLY TRUNCATED BY ANDROID MINIMISING THE APP

`lane.depthstall` found this while explaining #52's stall, and it is bigger
than #52. `depth52-A` rendered at 59.947 Hz, then logged `window minimized` /
`app entering background`, and **never restored for the remaining ~1,500 s of
its 1,800 s budget**. `ui/xemu.c:798-804` pauses the display path on
`SDL_WINDOWEVENT_MINIMIZED`.

The result: a run that looks complete, produces a partial capture set, and
whose missing captures read exactly like a defect. #52 spent its life believing
`DepthFmt_z24_Cy_FZn_Maaaaaf` stalls; it is simply whichever test was running
when Android took the window away. The old blocker proposed an `--only-tests`
arm on that test, which would have answered nothing.

**Nothing checks for this.** The string is right there in the logcat every run
already captures.

**Requested:** a gate that fails, or at minimum loudly flags, any result whose
logcat contains `window minimized` without a later `window restored`. It
belongs wherever a result is accepted — `score_sweep.py`, `collect_sweep.sh`,
or `ab_compare`'s provenance block, your call. Note `collect_sweep.sh` and
`score_sweep.py` are not in your claim; say if you want them.

Two facts to build against rather than assume: twelve runs on disk ran longer
(1147, 977, 956, 697, 471 s) and none was minimised, so this is not a screen
timeout or a run ceiling; and the logcat capture is filtered to the app and
carries no `ActivityManager` lines, so you cannot recover WHY, only THAT.

## 2026-09-14 — URGENT: the expect-key gate refuses every SOAK prediction

The queue-time gate I added to `request.sh` refuses `#68`'s registered arm
outright — 12 of 12 keys "match no capture in the goldens":

    G_xx_every_window, 73_1_ai_over_visits_armA_at_least,
    68_1_em_fall_factor_at_least, 68_4_stop_the_fold_above_factor, ...

**They are not capture names and were never meant to be.** A soak produces no
captures. Its prediction's legs are named rules judged by
`docs/testing/perf/tcg_pages.py` against the always-on `hakuX-pages` line. The
gate assumes every `expect` key is `Results_Directory/TestName`, which is true
for a disc request and false for a soak.

**This blocks every soak arm that carries a prediction** — i.e. every
performance or counter measurement that wants pre-registration. `#68`'s arm is
blocked on it right now, and the alternative is `--no-expect`, which throws
away the pre-registration that makes the measurement worth anything.

You already found this gate wrong in the other direction: 5 of 81 registered
predictions were **falsely refused** for legitimate glob keys that `judge()`
handles fine. This is the sixth false positive and the same root cause — the
gate models one request shape and there are two.

**Requested:** skip the capture-name check when the request is a soak (a
`--title` with no `--suites`), or better, make the check follow whatever
`judge()` will actually do with the key. A gate that refuses valid work is
worse than the inert legs it was written to catch, because those at least
failed loudly at judgement time.

Mine to own — I wrote it tonight and it is your file now. Sorry.

## 2026-09-14 — ITEM 6: the lane/fleet cross-check, both directions

A hand-run comparison of `territory.toml`'s lanes against
`$DISPATCH_DIR/fleet/*.json`'s running set found **two real inconsistencies in
one pass**:

- `lane.tcginval` CLAIMED BUT NOT RUNNING — its agent had reported and folded,
  so its `accel/tcg` claim was asserting coverage that did not exist.
- `lane.audit-tcg` RUNNING BUT NOT CLAIMED — dispatched with no row at all.

`fleet.py` already reports LANE-CLAIMED-WITH-NO-RUNNING-AGENT, so it catches
the first direction. **It does not catch the second**, and the second is the
worse one: a lane that is running and unclaimed is invisible to *every* guard,
because `check_territory.py` cannot see a lane that is not in the file.

That is now three occurrences of a running-but-unclaimed lane tonight, each a
different variant — no row, row written but not committed before dispatch, and
no row because an auditor claims no files. `papercuts.toml` has it at `bit = 3`
and AGENTS.md carries the general rule.

**Requested:** add RUNNING-BUT-NOT-CLAIMED to `fleet.py`, and make it non-zero
exit like the others. A lane with `files = []` still counts as claimed — the
row is what matters, not the territory.

## 2026-09-14 — `sweep_diff` cannot give a noise floor to any partial-coverage suite

`repeats_for()` excludes a run unless **every** suite in it is complete:

```python
proof = all(not c.get("partial") for c in cv.values()) if cv else False
if not proof: continue
```

The reasoning in its own docstring is sound — *"a truncated run leaves the
previous image in place and reads as a pass, so counting it as a repeat would
manufacture agreement."*

**But it conflates two different things.** `ZPass_pixel_count` scores **72 of
78 goldens** — not because the run truncated, but because **the disc does not
contain those six tests**. All three noise-floor runs I queued are identical to
the pixel (72 captures, 26 exact, 14,244 px, three times) and all three are
discarded, so the suite is **permanently unattributable**: no number of runs
can ever give it a floor.

Same for `Depth_buffer` at 144 of 784 — the scorer's own run log says a gap
that large usually means the tests were retired upstream and need the
2025-03-14 disc.

**The distinction the tool needs:** a run that stopped early (the progress log
has an unmatched `Starting`, or `window minimized` with no restore — your own
new check) is untrustworthy. A run that **completed normally** on a disc with
fewer tests than the goldens is *complete for what it contains*, and its
repeats are real repeats of that population.

`progress_log_proof` is already in `result.json` and already true for these
runs. The ZPass runs end `Testing completed normally, closing log.`

**Requested:** distinguish "partial because truncated" from "partial because
the disc has fewer tests", and let the second kind count as a repeat — with the
population it covers recorded, so a floor from 72 captures is never read as a
floor over 78.

Cost of not fixing it: 36 of the corpus's 42 movers are currently
unattributable and cannot be made attributable by any amount of device time.

## 2026-09-14 — ITEM 7: `hakuX-tier1:D` is silenced, and it blocks #81's only first step

#81 (tier-1 promotion requests multiply) has a first step that is a
**measurement, not a fix**: does the mechanism fire at all? `lane.tcginval`
raised that `tb_lookup` may keep finding the promoted block so
`tier1_consume_request` never runs.

**It is not measurable today.** `promote`/`consume` log under `hakuX-tier1:D`,
and `dispatcher.sh:673`'s default spec ends `*:S`. So the zero `[tier1]` lines
across every logcat on disk are **not evidence either way** — the tag was
silenced before the question was asked. That is the same shape as the
`hakuX-linewidth` tag that made a #13 log invisible in every dispatcher run.

`LOGCAT_SPEC_OVERRIDE` is a dispatcher-wide environment pin, not a per-request
option, so a soak cannot ask for one tag. The fix is one entry in that default
list — and `dispatcher.sh` is in `SCRIPT_DEPS`, so the worker re-execs and it
takes effect, which the file's own comment at `:653` explains at length.

**Requested:** add `hakuX-tier1:D`, or give `request.sh` a per-request way to
add a tag. I did not do it myself: `dispatcher.sh` is an instrument, and the
division of labour I set up this evening says instruments are yours. It is also
**unlisted in territory.toml** — neither claimed nor free — exactly like
`profile.c` was until wave 51. Say if you want it and I will grant it.

**The device is idle right now**, so this is the cheapest it will ever be to
answer.

## 2026-09-14 — ITEM 8: `tcg_pages.py`'s `discard_model()` still uses exact equality

`lane.tcgarm` found a residual of the defect `lane.tcgcount` just fixed:
`discard_model()` compares with **exact equality and no tolerance**, while the
population check beside it already carries `max(8, n*1e-4)`.

That matters because the same lane hit it: **C3 called one arm-A run `MIXED`**
on a `di − (ov + sp)` of **+1 in one window and −1 in the next**, with `pr` vs
`em` slipping the same ±1 in the same two windows — **one invalidation
straddling a window boundary**, which is the documented two-log-line slip the
population check already tolerates.

The lane resolved it correctly and expensively: it established build identity
with a *second* instrument (`apk_sha` per arm) rather than reinterpreting the
first. That is the right move and it should not have been necessary.

**Requested:** give `discard_model()` the same slack the population check has.
The file is yours as of wave 52.
