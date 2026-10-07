# dispatchgate1006: dispatch admission control

Owner order 2026-10-06 ~16:50 (#433 / 0.5): "We need bulletproof controls on what gets
dispatched." Offline lane, no device, nothing queued.

## 0. Attempt 2 (10-06 ~18:15 PDT): why attempt 1 did not finish

Attempt 1 marked the PR ready (6348049107) with a defect its own fixtures could not see. lane.local's
read-only review (18:10) found:
1. **Blocking.** `_answering_fix` counted any commit newer than the latest verdict as a fix.
   `fix:6cef37f426` (the waitread1006 fold, lane docs only) admitted DOA3, Hulk Ultimate Destruction
   and LOTR ROTK for a Playable attempt. That reopens today's DOA3 incident. Every fixture fix commit
   was one *meant* to answer its title, and every mutant switched a whole rule off. No leg cited an
   unrelated newer commit, and no mutant put back the weaker rule.
2. `title_registry.py` called `gh` with no guard (no GitHub contact since 09-29).
3. `plan-check`, `99-dispatch-gate.sh`, `verify_patches.py` and `live_incidents.py` were not re-run by
   the reviewer, and `live_incidents.py` rewrote the host's real registry.

All three are fixed in attempt 2 (sections 2, 4 and 7).

## 1. What exists now

| file | what it is |
|---|---|
| `docs/testing/title_registry.py` | builds `pm/title-registry.tsv`: one generated row per canonical title id, with status, the latest scored verdict, every gate value **recomputed from the verdict's values** (`failing_all`), owner holds, fix commit, last run, runs today, staging and the recorded input sequence |
| `docs/testing/dispatch_gate.py` | `admit(request) -> allow/deny + reasons + token`; `plan_check`; `admit-request` (request.sh's entry); `hold-check` (hold.sh take's entry); `verify`; `skip`; `mode` |
| `docs/testing/dispatch_audit.py` | the daily review: ungated title runs, refusals, Nova minutes on flagged titles |
| `docs/testing/dispatch_gate_selftest.py` | 59 legs, each the incident or rule with a mutant that must flip it |
| `docs/lanes/dispatchgate1006/title-fixes.template.tsv` | the header and rules of `pm/title-fixes.tsv` (lane.local creates and owns it; absent = no recorded fix) |
| `docs/testing/jobs/selftest.d/99-dispatch-gate.sh` | runs the selftest in the CI selftest harness |
| `docs/lanes/dispatchgate1006/owner-holds.seed.tsv` | the seed of `pm/owner-holds.tsv` (installed on the host 10-06 ~17:05 PDT) |
| `docs/lanes/dispatchgate1006/patches/*.patch` | the call sites in files this lane may not edit (section 5) |
| `docs/lanes/dispatchgate1006/tools/` | `live_incidents.py` (today's requests against the real records), `make_patches.py`, `verify_patches.py` |

Host files this lane created: `pm/owner-holds.tsv` (from the seed), `pm/title-registry.tsv`
(generated), `pm/.dispatch-gate.key` (HMAC key, 0600). `pm/dispatch-gate.mode` does not
exist, so the gate is in **shadow mode**: it refuses nothing.

## 2. Why we dispatch, and why we do not: each reason and the rule that checks it

Every dispatch names exactly one class and cites evidence ids (`verdict:` `fix:` `issue:`
`order:` `plan:` `condition:` `run:`). An unknown class, no evidence, or an evidence id that
does not resolve (a path that does not exist, a sha that is not a commit) denies.

**The class x status matrix** (`rule_class_status`). Default is DENY; only these pass:

| class | allowed when | denied otherwise, e.g. |
|---|---|---|
| PLAYABLE_ATTEMPT | status FAILED_HARNESS (perf clear, a non-perf gate failed) or VOID, **and every failed gate answered** by a fix (below) | in the ledger; EXCLUDED; PENDING_OWNER; CRASH_OR_HANG; **BELOW_BAR, with or without a fix**; UNSCREENED (that is a SCREEN); a harness PASS not in the ledger (owed a frame review, not a run); a commit that is only newer; a fix older than the verdict (same inputs again) |
| SCREEN | UNSCREENED with zero runs on record | any title with a run |
| TELEMETRY | BELOW_BAR or CRASH_OR_HANG; valid end `capture:<N>s` / `condition:` | `valid-verdict` (a telemetry run is never a confirmation, owner 10-03) |
| VALIDATION | names the condition it exercises (`condition:<text>`) | no condition |
| OWNER_DIAGNOSTIC | an unreleased `order` row in `pm/owner-holds.tsv` for this title | no order, a spent order, an env var |

**What counts as a fix** (`_answering_fix`, `_fix_answers`; attempt 2). A commit answers a failed
gate of a title only by one of two records. Being newer than the verdict is never enough:
- (a) a row of **`pm/title-fixes.tsv`**, which lane.local owns (template
  `docs/lanes/dispatchgate1006/title-fixes.template.tsv`): `title_id, gate, fix_commit, set_by, date,
  why`. `set_by` must be `lane.local` or `owner`, `why` must be filled, and `gate` names the gate(s)
  (`+`-joined, or `route` for menu_time+reached_gameplay+duration+static+position);
- (b) the commit's changed paths (first parent, so a fold counts its whole lane) match **`GATE_PATHS`**.
  Only the route gates have entries: `^docs/testing/titles/pathknow/paths/{TID}\.json$`, where
  `{TID}` is the title's id or an alias. The map is narrow on purpose. A harness-wide change
  (pathfind.py) or an emulator change may answer every title or none, so it answers nothing by its
  paths and needs an (a) row.

The fix must also be newer than the latest verdict (or the last run when there is no verdict) and
answer **every** failed gate. When the fix changes anything outside `docs/` it must be in the
requested build (`git merge-base --is-ancestor`). A `docs/`-only fix acts from the tool tree, not from
the APK. **A perf gate (fps/hitch/audio) is never answered for a Playable attempt.** The fix allows
TELEMETRY or VALIDATION. A verdict after it that clears the bar moves the title out of BELOW_BAR, and
only then is a Playable attempt possible.

**Title-level reasons not to dispatch:**

| reason | rule | source read |
|---|---|---|
| already Playable | matrix: status PLAYABLE | `pm/playable-accepted.tsv`, title id or exact-name resolved |
| below the fps bar | matrix BELOW_BAR: a Playable attempt always denies | latest scored verdict, gates recomputed |
| owner-excluded (RalliSport, football, Galleon, Tron/NGB/Amped 2/Spider-Man 2, NHL 2K3) | `rule_holds` + status | `pm/owner-holds.tsv`, `host-tools/blocked-titles.txt` |
| open hang/crash, no fix | matrix CRASH_OR_HANG | latest judged run's crash/hang; `crash` holds (#859, #835/#837, released when the forge closes them); failure-intake crash/hang rows newer than any verdict |
| pending owner ruling (#851 Marvel) | `pending` hold | `pm/owner-holds.tsv` |
| no committed fix *that answers* the last failure | `_answering_fix` | `pm/title-fixes.tsv` or `GATE_PATHS` (paths from the host bare repo), commit time > `verdict_utc`, ancestry of the build |
| open hang/crash issue state | `hold_active` at build time | the local forge's open issues over HTTP (127.0.0.1:3330, `forge/tokens/jobs.token`), never `gh`; unreadable = `forge=unreadable` in the header and the hold stays active |
| identical inputs already run | `rule_identical` | an ALLOW in `pm/dispatch-log.tsv` with the same class/build/input sequence and a verdict since |
| ISO not staged | `rule_staged` | device listings, `pm/*-100?.done`, and runs that found the ISO on that device |
| "fix folded" in a plan row | `plan_check` | the row must name a commit that exists **and** a verdict after it |
| out of plan order | `rule_plan` | every earlier eligible row has run (registry `last_run_utc`), been admitted, or has a SKIP row since the plan's mtime |
| request `title_id` is not its ISO's | `rule_request_shape` (`_id_conflict`) | catalog resolution of the ISO name |

**Run-level reasons** (`rule_build`, `rule_device`, `rule_window`, `rule_input_and_end`, `rule_env`):
installed APK read back (`pm path` + `sha256sum`, first 12 hex) must equal
`dispatch/builds/<build>.apk`'s sha256[:12] on a direct hold; the build must contain the
libfolders floor `10f14d301d` (Forza: `10fe2f59a7`, #583); Thor: no Playable attempt, <= 480 s,
queued only (`thor-fan-dead` row); a direct hold on a device another tag holds denies; the
Playable window (`playable-window-1006`: last start 21:15 PT on 10-06); an input sequence that is
the title's recorded complete path (`path:<TID>@<sha12>`, the sha of the file today), a route file,
or `discovery` for a SCREEN only; a valid end of `valid-verdict | capture:<N>s | condition:<text>`
(a Playable attempt only `valid-verdict`); request env keys must be declared.

**Stale registry.** admit() denies when the registry is over 15 min old or the digest of its
448 source files (path, size, mtime) has moved. The CLI and the audit rebuild it first; admit()
itself never consumes a stale one.

**No override but an owner order.** Nothing reads the process environment. The selftest sets
`DISPATCH_GATE_OVERRIDE`, `PATHFIND_FOOTBALL`, `HAKUX_GATE_OFF`, `FORCE` and shows the DOA3
decision unchanged, and that a mutant rule which honours the variable flips it.

## 3. Not machine-checkable (who checks by hand, and where the answer is written)

| rule | why the gate cannot read it | who | where it is written |
|---|---|---|---|
| the fix *answers* the failure, for a fix outside the title's own path file | whether a commit fixes a failure seen in frames is judgement. The gate reads the judgement once it is recorded | lane.local | a row of `pm/title-fixes.tsv` (title, gate, sha, set_by, why). The gate refuses without one |
| a `docs/`-only fix is in the tool tree that runs the title | the gate does not know which worktree (pathfind's, the dispatcher's) will run the request | the caller (pathfind) | pathfind's NOTES; a future `tools_ref` in the request |
| flicker cleared | the owner checks flicker by eye (owner 10-04) | owner | lane.local fills `released` on `ralli-flicker-804` with the date and the owner's words |
| sports: longest period / slowest clock set | lives in the input sequence and hold frames | pathfind / lane.local frame review | the path file's steps; the ledger row's evidence |
| a recorded path is *verified* (replayed to gameplay), not only recorded complete | path files record `complete` and `result`, not a later replay's outcome | pathfind | a future `replayed_ok` field in `pathknow/paths/<TID>.json` |
| thermal / battery admission | already enforced at claim by `battery_admit.py` in the dispatcher; not duplicated | dispatcher | `.battery_refused.<dev>` |
| a run in flight / never fast-forward the tree | `hold.sh wait-idle` owns it | the taker | `running/*.owner` |
| usage mode, lane attempt caps | no per-dispatch record the gate can tie a request to | lane.local / handback.sh | `limits.env`, `attempts/` |
| request env outliving a run | the leak is on the device prefs after the run; the gate sees only the request | dispatcher | `.prefs.<dev>.xml` |
| the build a pathfind **held run** used | held runs record no `ref`/`apk_sha` (registry `last_run_build` = `unrecorded`) | harnessfix1006's receipt (PM replan action 5) | pathfind `result.json` once it records ref/apk |
| one copy per title | enforced by `titlepush/onhand.py` at copy time, not at dispatch | lane.xbox | `queue-investigation.txt` |

## 4. Verified by running, and not

Attempt 2 (10-06 ~18:20-18:50 PDT), all run in this session:
- `python3 docs/testing/dispatch_gate_selftest.py` -> `59 legs, 59 green, 0 red`. The new legs:
  `GREEN DOA3 PLAYABLE_ATTEMPT citing fix:6cef37f426 (an unrelated fold) -> deny DENY | mutant[newer
  commit = fix] -> ALLOW`, and the same for MK Armageddon and for a harness-wide commit. Also: a
  path-file fix allows (mutant: GATE_PATHS empty -> DENY); a lane.local title-fixes row allows (mutant:
  set_by lane.pathfind -> DENY); a row naming another gate, or with no why, denies; DOA3 with a
  recorded fps fix denies a Playable attempt (mutant: the reviewed rule -> ALLOW) and allows TELEMETRY;
  an emulator fix not in the build denies; a docs-only fix not in the APK build allows. The four
  owner-held below-bar titles now rest on a post-fix verdict that clears perf, so only the hold denies
  (mutant: holds dropped -> ALLOW).
- Forge legs: `GREEN no `gh` invocation in title_registry.py, dispatch_gate.py, dispatch_audit.py`
  (mutant: the reviewed line restored is flagged). `GREEN registry build reads the forge over HTTP with
  the jobs token, never runs gh 4 HTTP request(s), 0 gh call(s) | mutant[gh reader] -> 2 gh call(s)`.
  Against a fake local forge: #835 open keeps AMF's hold, closed releases it. Unreachable or no token
  -> `forge=unreadable` and the hold stays active (mutant: unreadable read as nothing open -> released).
- `env SELFTEST_ONLY=99-dispatch-gate.sh bash docs/testing/jobs/selftest.sh` -> `4 passed, 0 failed`
  (two new greps: the 6cef37f426 leg and the gh leg ran).
- `tools/live_incidents.py` now builds into a scratch file and prints `host registry
  /home/justin/hakux-work/pm/title-registry.tsv untouched: True`. Against the real records, DOA3
  (4D53002D), Hulk UD (56550039) and LOTR ROTK (4541003E) with `fix:6cef37f426` all DENY (BELOW_BAR).
  Fight Club 5655002F is `PLAYABLE flicker=UNCHECKED`; RalliSport 4D53000F is
  `EXCLUDED flicker=HOLD:ralli-flicker-804`.
- `dispatch_gate.py plan-check pm/plan-2026-10-06-evening.md` -> rc 2, 7 rows, 7 rejected;
  `plan-2026-10-06-replan.md` -> rc 2, 14 rows, 14 rejected (rows that do not resolve, below-bar, no
  recorded fix, "first run" of titles that ran).
- `tools/verify_patches.py` -> `verify_patches: all pass`.
- `Ctx().commit_paths` against the host bare repo: `6cef37f426` -> 11 paths, all under
  `docs/lanes/waitread1006/`.
- `python3 docs/testing/title_registry.py build` regenerated the host registry (it now has a `flicker`
  column; the forge was read over HTTP, `forge=ok`): 951 rows, PLAYABLE 33, EXCLUDED 27, PENDING_OWNER 1,
  CRASH_OR_HANG 13, BELOW_BAR 35, FAILED_HARNESS 23, VOID 0, UNSCREENED 819.
- `dispatch_audit.py --no-refresh` runs: 90 ungated title runs in 24 h, 457.2 Nova min on titles now
  flagged.
- `preflight.sh --allow-tracker` -> `preflight passed`.

Not verified in attempt 2: the real `Ctx.is_ancestor` with a lane-branch fix (only fixtures); the
title-fixes path on the host (`pm/title-fixes.tsv` does not exist; lane.local creates it from the
template).

Attempt 1 ran (quoted output in OUTBOX and below):
- `python3 docs/testing/dispatch_gate_selftest.py` -> `45 legs, 45 green, 0 red`; every leg's mutant flips it.
- `env SELFTEST_ONLY=99-dispatch-gate.sh bash docs/testing/jobs/selftest.sh` -> `2 passed, 0 failed`.
- `tools/live_incidents.py` against the host's real records (no log rows written): DOA3, Dino Crisis 3,
  RalliSport, Strike Force (plan), Tron, NG Black, Amped 2, Spider-Man 2, NFL Blitz Pro, NBA 2K3,
  AMF Xtreme and Marvel all DENY with the right rule; Blowout VALIDATION ALLOW.
- `tools/verify_patches.py`: all six patches apply; patched `hold.sh take` takes and logs in shadow,
  refuses with exit 3 in enforce, exempts a `hostupd-*` tag; patched `pathfind_selftest.py` passes
  with its new `dispatchgate` leg and writes nothing to the host log.
- `docs/testing/preflight.sh --allow-tracker` -> `preflight passed`.

Not verified: no patch is applied to a live file (they are not this lane's files); `--readback`
was never run against a handheld (no device in this lane); enforce mode has never run on the
host; the hourly section has not run inside `hourly_report.sh`.

## 5. Call sites

One admit(), every path:
- (a) `request.sh` -> `patches/request.sh.patch`: `--gate-class/--gate-because/--gate-input-seq/
  --gate-valid-end/--gate-order/--gate-plan/--gate-declare`, then `dispatch_gate.py admit-request` on
  the request before it is queued; ALLOW writes `gate_token` into the request. Shadow: never refuses.
- (b) pathfind's intake -> `patches/pathfind.py.patch` + `patches/pathfind_selftest.py.patch`:
  `--dispatch-class/--because/--build/--order/--valid-end`, `admit --via hold --readback` before the
  blocked/football checks; a dry run never asks the gate.
- (c) `hold.sh take` and `wait` -> `patches/hold.sh.patch`: `dispatch_gate.py hold-check`; shadow logs
  `SHADOW-HOLD-UNGATED`; enforce refuses with 3 except tags matching
  `^(hostupd-|lanelocal-fanwait$|lanelocal-topup|charge-|playtest)` (**lane.local confirms this
  list before enforce**).
- (d) scripts that call hold.sh directly, measured by grep (10-06 ~17:30 PDT, `.bak` copies and
  prose excluded). Every one reaches the gate through (c) once it is applied:
  - repo: `docs/testing/burst_capture.py`, `docs/testing/jobs/ops/ops_tick.py`; lane scripts
    `docs/lanes/{accuracy804/session804e.sh, doa413c/capture_stall.sh, fanduty507/modeprobe.sh,
    flicker801/session.sh, flicker801/session2.sh, flicker801/session3.sh,
    frametrace/capture_simpsons_frametrace.sh, gta482/capture_gta.sh, hitchcause/capture_mtv_ide425.sh,
    savestate433/proof_tron.sh, slowdown462/capture_profile.sh, sustain507/fan_custom_probe.sh,
    vcpusleep/capture_simpsons_offcpu.sh, vcpuwait433/capture_offcpu.sh}`, and pathfind's
    `docs/lanes/pathfind/runs/{halo-2-hold, halo-2-hold2, nba-live-2005-hold}/run.sh`.
  - host-tools (lane.local's): `coldslot.sh, devwatch.py, doa_cache_pull.sh, lanelocal_after_restart.sh,
    overnight1004_push.sh, owner1004_push.sh, playtest_ready.sh, sports1005_push.sh, sweep_pull.sh,
    sweep_push.sh, sweep_push_each.sh, thor_coldconfirm.sh, thor_copy_playables.sh, thor_fanwait_hold.sh,
    thor_suite_runner.sh, topup_release.sh, voidstorm_release.sh`, `coldcap/{capture_gta_r1.sh,
    cold_memfast.sh, cold_r1.sh, cold_r1b.sh, nova_topup_release.sh, updwin_after_run.sh}`;
    `lanelocal-scratch/{nova_done_watch.sh, nova_handoff_watch.sh, nova_release_watch.sh, sh_master.py}`.
  - `pathfind.py` itself takes no hold: a held run's hold is taken by the session or a `run.sh`, so
    its intake patch (b) is where pathfind meets the gate.
  - `scratchpad/ralli1006.sh` (the memory note's RalliSport diagnostic) is in a session scratchpad,
    not on disk under the work dir; not found.
  - Many of these are not runs (ISO pushes, top-ups, cache pulls) and most pass their tag in a
    variable, so the enforce-mode exemption list cannot be read from the scripts. Set it from a day of
    shadow rows: `dispatch_audit.py`'s REFUSED section prints every ungated hold's tag and why.
- The verdict writer -> `patches/title_verdict.py.patch`: `failing_all` (every failed gate by name)
  and `fps_ok_share` always present.
- The hourly report -> `patches/hourly_report.sh.patch` (host-tools, lane.local's): a DISPATCH GATE
  section after PLAYABLE.

The PM write path for plans: none in code. `pm/plan-*.md` are written by the PM session by hand
(host-tools/pm-role.md). `plan_check` is a CLI (`dispatch_gate.py plan-check PLAN.md`) the PM
runs before publishing, and admit() runs it again for any request that names `--plan`.

**Enforcement order** (lane.local): apply (a)-(c) in shadow, read `dispatch_audit.py` for a day,
confirm the hold exemptions, then `echo enforce > pm/dispatch-gate.mode`. hold.sh/dispatcher.sh
are lane.harnessfix1006's until it folds after 22:00.

## 6. Findings

1. **`failures` already lists every gate; `failing` is the first.** retro-doa3's verdict.json
   carries `failures: [menu time, fps 43.9%, hitches 653 ms]`. The fps miss was on disk; the plan
   read `failing`. The registry recomputes the gates from the values anyway (and adds
   `window_unmeasured`, which older verdicts predate).
2. **A request's `title_id` can be another title's.** The 10-05 hostops measured runs
   `1791267037-hostops-measured-tron` and `1791267038-hostops-measured-starwars3` carry
   `title_id` 54540082 (GTA SA) on Tron's and Star Wars III's ISOs, and so does their `hdd.title_id`.
   The registry and audit resolve the booted ISO; admit-request denies a disagreement.
3. **"AMF Xtreme in ledger=True"**: not found in any record or script on disk (pm/, briefs/,
   pathfind lane, scratch dirs). By title id it is false: AMF Xtreme Bowling is 42530014 (Thor
   listing `42530014-AMF_Xtreme_Bowling.xiso.iso`, owner-library `ok 42530014`); the ledger's only AMF
   row is "AMF Bowling 2004" (42530009, title_id `-`). A word test ("amf" and "bowling" in a ledger
   title) gives True; that is the likely mechanism.
4. **pathfind's football regex also excludes soccer**: Club Football, Club Football 2005, England
   International Football 2004 Edition and FIFA Football 2004 match `\bfootball\b`. The gate mirrors
   pathfind (e383da4992) so the two never disagree; whether soccer is "football" is lane.local's call.
5. **The real 13:35 replan, through plan_check**: rows 1, 6, 7, 8 name short titles ("MK Armageddon",
   "Marvel Nemesis", "LEGO Star Wars", "Guilty Gear XX Reload") that resolve to no title id; rows 3-5
   cite fixes (ab8788c38b, 314ef06f72) older than those titles' own later verdicts (the fix was
   already tried); rows 9, 12, 13 call Tecmo, Fight Club and Batman Begins "first run" though each has
   an overnight sweep run; row 2 says "folded" with no commit; row 10 names NAME_SEQ with no sha.
   Plans should carry the title id and the fix sha in the row.
6. **Nova minutes, last 24 h** (dispatch_audit, 17:26 PDT): 462.2 min on titles now flagged, 152.7 of
   them on titles already flagged before the run. That 152.7 includes gpunonrender's telemetry runs on
   NG Black and DOA3 which a gated TELEMETRY dispatch would exempt; pre-gate runs carry no class.
7. **Identity sources**: `listing-nova.txt` is dated 10-04 and misses later pushes; the gate also
   counts a run that found the ISO on a device as staged.

## 7. For the next lane: do not repeat

- **Never run a patched pathfind selftest with the gate on the host root.** My first patched
  `pathfind_selftest.py` run let `main()` in dry mode call the gate with the default root, and it wrote
  32 `SHADOW-DENY 00000000` rows into the host's `pm/dispatch-log.tsv`. I removed them (the file
  held nothing else) and the patch now skips the gate on a dry run; `verify_patches.py` checks the
  host log is untouched.
- A selftest fixture needs one rule standing between the request and ALLOW, or its mutant cannot
  flip it: the RalliSport leg cites a newer fix so only the owner hold denies.
- The shell tool here rejects heredocs with quoted braces: generators live in `tools/*.py`.
- **A mutant that switches a rule off is not enough.** Attempt 1's legs each disabled a whole rule,
  and every fixture fix was a commit meant to answer. A rule weakened to "any newer commit" passed
  every leg. Write the mutant that brings the defect back (`_pre_review_rule` in the selftest), and give
  the fixture the input that tells the two apart: an unrelated commit that is newer.
- A tool that replays requests against the host must build its registry in a scratch file
  (`G.Ctx(registry=scratch)`), never the host's `pm/title-registry.tsv`.
