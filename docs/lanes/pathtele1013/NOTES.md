# lane.pathtele1013 -- KOTOR II and Splinter Cell Double Agent, and `pathfind.py --perflog` (#433, 0.5)

Brief: `/home/justin/hakux-work/briefs/pathtele1013.md`. Owner's question (2026-10-13 ~08:05 PDT):
"On the FPS failures, did we capture telemetry for analysis to see what the slowdowns were? If
not, let's queue that up so we have it banked."

## 1. KOTOR II (4C410014, Europe): the guest, locked at 30 and dropping frames -- no lever of this lane's

**The held run.** `/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs/n-4C410014-1011/`, lane.pathfind's,
not perflog. verdict.json: reached gameplay by route, 606.5 s of play (play_share 0.8473 of 715.9 s scored),
fps_ok_share 0.6595, window median 29.88, min 18.63. FAILS both menu time (84.7% of play, bar 90%) and fps (66.0%
of gameplay at >= 30 fps, bar 90%). Its logcat (7833 lines) carries only the always-on lines: `hakuX-perf`,
`hakuX-pace`, `[rdc]`, `[rr425w]`/`[rr425]`/`[rr425pc]`, `[tlb68]`, `[shd413]`, `[idlehalt]`. No `[sdcall]`, no
`hakuX-phase` split -- those are perflog-only.

Read the way fpsbelow1012 NOTES.md section 17 reads Mission: Impossible, over the scored play window (719.4 s of
`[rr425w]` coverage):

| | read |
|---|---|
| vCPU busy / idle (`[rr425w]`, kernel idle loop at 0x8001b02e) | **84.6%** / 15.4% of wall |
| busy after wakes keyed `30.00` | **79.3%** of wall (93.7% of busy): 135,138 wakes, avg 4,219.2 us/wake |
| busy after wakes keyed `33.44` (the nv2a IRQ / NV097_NO_OPERATION software callback, M:I's and SC's class) | 3.5% of wall only |
| render thread (`[rdc]` tcpu) | **14.3%** of wall, 5.19 ms of each frame |
| `[shd413]` pipeline lookups | miss rate ~0.000%: not shader compiles |
| `[tlb68]` full-flush rate | 5.90/s: low, not a TLB/MMU-flush class |
| `[idlehalt]` run share | 98.5% (`on=0`: the feature is off; uninformative) |
| `hakuX-perf` main line, G (guest) vs D (device/GPU) mean | G 36.39 ms, D 16.70 ms: D tight and stable, G sets the frame |
| `hakuX-pace` histogram (v0..v4 share of flips, aggregated over 330 lines) | v0 0.003, v1 0.084, **v2 0.661**, v3 0.235, v4 0.017 |

**Reading.**
- The vCPU is busy 84.6% of wall, almost all of it (93.7%) after wakes keyed `30.00`, not `33.44`. KOTOR II's
  dominant wake is NOT the nv2a-ERROR-callback class M:I and SC (below) both show; it reads as general CPU
  compute the guest does on essentially every wake, not a wait on one specific PGRAPH callback.
- The render thread is a minor share (14.3% of wall, 5.19 ms/frame) and D (16.70 ms mean) is tight -- the GPU is
  not the wait. G >> D, so the guest sets the frame time, the same conclusion M:I's reading reached by the same
  method.
- **Locked at 30 that drops frames, confirmed quantitatively, not just by the median.** The brief asks whether
  29.88-median/66%-share reads that way. `hakuX-pace`'s v2 share (flips that took exactly the nominal 2 VBLANKs,
  i.e. a clean 30 fps) is 0.661 -- within 0.0015 of fps_ok_share (0.6595) measured completely independently by
  title_verdict.py from the perf-line frame times. Two instruments computing the same number from different raw
  data is as close to a quantitative confirmation as the always-on lines give: two thirds of frames land
  exactly on the 30 fps vblank; the rest (v3, 23.5%) drop to the next one down (20 fps), not a general jitter
  around 30. M:I had no pacing line to do this with at all.
- `[shd413]` and `[tlb68]` rule out a shader-pipeline-miss or TLB-thrash class.

**Against the lever table (fpsbelow1012 NOTES.md sections 6/12).** None of L1/L4a/L4b apply: L1 acts on the
GPU's GMEM replay, and L4a/L4b act on render-thread/surface-download waits -- all three need the render thread
or the GPU to be the bottleneck, and here the render thread is 14.3% of wall against the vCPU's 84.6%. The class
is **L5, guest vCPU**, same bucket M:I landed in, owned by vcpuplan/vCPU-JIT-direction lanes, not a lever this
lane can pull. Unlike M:I, KOTOR II's busy is NOT keyed to the nv2a-ERROR-callback wake class L5's own prior
notes describe as "small" -- it is wake-key `30.00` instead, at a scale (93.7% of busy) M:I's reading never saw.
Whether that is a materially different L5 sub-case or the same bucket read from a different angle is a question
for vcpuplan, not an answer the always-on lines give (see section 3).

**What a perflog run would add.** The `hakuX-phase` split (ph_Draw/ph_Fin/ph_Tot) and `[sdcall]` would show
whether any of the render thread's 14.3%/5.19 ms is itself stalled on a surface download the main-line G/D split
can't separate out, and the pfifo.c:743 kick-to-callback latency split would show whether any of the `30.00`-keyed
busy time is itself downstream of a PFIFO interrupt latency rather than pure guest compute. Both would refine
L5's share of this title's time, not displace it: G (36.39 ms) already says the guest sets the frame, with D
(16.70 ms) tight underneath it.

## 2. Splinter Cell Double Agent (5553005E, USA): the guest, nv2a-callback class, oscillating 30/20 -- no lever of this lane's

**The held run.** `/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs/n-5553005E-1011/`, lane.pathfind's,
not perflog. verdict.json: reached gameplay by route, 308.5 s of play (play_share 0.999 of 308.8 s scored, almost
all play), fps_ok_share 0.0334, window median 23.47, min 16.54. FAILS duration (309 s of gameplay < 600 s
confirmation) and fps (3.3% of gameplay at >= 30 fps, bar 90%). Its logcat (3358 lines) carries the same
always-on lines, plus one tag the brief's list does not name: `fifoskew` (I/hakuX-perf) -- flagged, not decoded
(section 3).

Read the same way, over 312.4 s of `[rr425w]` coverage:

| | read |
|---|---|
| vCPU busy / idle | **56.8%** / 43.2% of wall |
| busy after wakes keyed `33.44` (nv2a IRQ / NV097_NO_OPERATION callback, M:I's class) | **51.6%** of wall (90.9% of busy): 13,100 wakes, avg 12,302.9 us/wake |
| render thread (`[rdc]` tcpu) | **20.1%** of wall, 8.58 ms of each frame |
| `[shd413]` pipeline lookups | miss rate ~0.000% |
| `[tlb68]` full-flush rate | 0.01/s: not a TLB class |
| `[idlehalt]` run share | 98.6% (`on=0`: uninformative) |
| `hakuX-perf` main line, G vs D mean | G 42.86 ms, D 16.72 ms: D tight, G sets the frame |
| `hakuX-pace` histogram | v0 0.000, v1 0.006, **v2 0.451**, **v3 0.520**, v4 0.023 |

**Reading.**
- The vCPU's busy time IS dominated by wake key `33.44` (51.6% of wall, 90.9% of busy) -- the same
  nv2a-ERROR/NV097_NO_OPERATION-callback-driven class M:I's reading used (M:I: 52.1% of wall). SC Double Agent is
  a clean second example of that class, unlike KOTOR II above.
- The vCPU is markedly more idle overall than M:I (43.2% here vs M:I's 27.9%) -- the callback-driven busy spells
  are real but the guest spends nearly half of wall idle between them.
- G (42.86 ms) >> D (16.72 ms): the GPU is not the wait, same conclusion as KOTOR II and M:I.
- The pace histogram splits almost evenly between v2 (30 fps, 45.1%) and v3 (20 fps, 52.0%) -- not locked at one
  rate like KOTOR II; it oscillates frame to frame between the two, matching the much lower median (23.47 vs
  29.88) and the near-total fps_ok_share miss (3.3%).
- `[shd413]`/`[tlb68]` again rule out shader-miss and TLB classes.

**Against the lever table.** Same conclusion as KOTOR II: render thread at 20.1% of wall against the vCPU's
56.8% rules out L1 (GPU GMEM replay) and L4a/L4b (render-thread/surface-download waits). This is **L5, guest
vCPU** again, and -- unlike KOTOR II -- it is the SAME wake-key signature (`33.44`) M:I itself showed, so it is
the stronger of the two examples for vcpuplan's lanes to use: a clean nv2a-ERROR-callback-driven busy pattern,
with more idle time around it than M:I had.

**What a perflog run would add.** Same two instruments as KOTOR II: the `hakuX-phase`/`[sdcall]` split (does any
of the render thread's 20.1%/8.58 ms stall on a surface download) and the pfifo.c:743 kick-to-callback latency
split (how much of the 90.9%-of-busy `33.44`-keyed time is PFIFO latency vs guest compute after the callback
fires) -- this is the more informative of the two titles for that second question, since SC's `33.44` share is
the dominant one, not KOTOR II's `30.00`.

## 3. What the always-on lines cannot determine (findings, not guesses)

- **The exact semantic decode of `[rr425w]`'s wake-key field** (`30.00`, `33.44`, `33.02`, ...) is read from
  fpsbelow1012's own M:I reading, which decodes `33.44` (nv2a IRQ, PGRAPH ERROR bit, pgraph.c:2567) and `33.02`
  (vblank) but not `30.00`. M:I's own table labels `30.00` "idle ended by the 1 kHz timer" when counting IDLE
  time, not busy time -- so whether KOTOR II's `30.00`-keyed BUSY share (93.7% of busy) is the same wake reason
  in a different role (the guest doing real work on every periodic tick, not just returning to idle) or a
  distinct code this lane has not seen used as a BUSY key before is not something the always-on lines or any
  committed decode table answers. I read the numbers as "general CPU compute, not one specific nv2a callback"
  because the share is too broad and too even to be one blocking call, but that is an inference from the shape
  of the data, not a decode of the key itself -- the next lane that needs to split L5 further should ask
  vcpuplan/vCPU-JIT whether `30.00`-as-busy-key has a known meaning before trusting this reading's framing of it.
- **`fifoskew` (SC Double Agent's logcat only).** Not in the brief's always-on list, not decoded here (no time
  budget allocated to a tag the brief didn't name, and it does not change either title's class: vCPU-bound by
  either reading). Worth a line for whoever next reads SC's logcat for PFIFO-skew specifically.
- **Whether KOTOR II's and SC's two different wake-key signatures (`30.00`-dominant vs `33.44`-dominant) are two
  different L5 sub-causes or one cause read two ways** is not resolvable from the always-on lines; it needs
  either the perflog pfifo.c:743 split (section 1/2's "what a perflog run would add") or someone who owns the
  vCPU/JIT code reading `[rr425pc]`'s return-PC histogram the way M:I's reading did ("SSE float loads in game
  code... I did not decode that instrument further" -- same limit here, not resolved by this lane either).

## 4. Part B: `pathfind.py --perflog`

Implemented in `docs/testing/titles/pathfind.py` (mine, inherited from the parked lane.pathfindhold1012):

- `--perflog` (store_true) and `--env K=V` (repeatable, requires `--perflog`).
- `build_apk(dev, ref, variant)` / `set_env_pref(dev, env_kvs)`: reuse dispatcher.sh's own `build_ref` and
  `apply_env_pref` by sourcing `dispatcher.sh` in a `bash -c` subprocess (`_dispatcher_call`). Bash's `source`
  takes its own positional parameters only for the sourced script's own execution, so this never reaches
  dispatcher.sh's `case "$1" in serve|worker|status|*)` dispatch at the bottom of the file -- no second build
  path, no new CLI subcommand added to a file outside this lane's territory. `build_ref`'s cache key already
  includes the variant (`<sha>-perflog.apk` vs `<sha>.apk`), per dispatcher.sh's own comment on why that must be
  true; this lane relies on that, does not reimplement it.
- `Device.install_apk`: `adb install -r` only -- never uninstall, never clear data (debug/perflog share a signing
  key, same as dispatcher.sh's own install). `Device.installed_version_name`: `dumpsys package ... versionName`.
- `_is_perflog_version`: version_stamp.sh's `<base>-<MMDD>-<sha>[-perflog][-dirty]` convention, dirty or not.
- `perflog_start(dev, allow_perflog)`: the guard. Runs before `resolve()` on every real-device invocation. Without
  `--perflog`, refuses to start if the installed build already reads as perflog -- the safety net for "a crash
  between an earlier --perflog's install and its restore poisoned the next scored run", since a pathfind run is
  not a dispatcher result and the dispatcher's own restore never sees it.
- `perflog_setup(dev, env_kvs)`: build (perflog variant) -> install -> verify the installed versionName reads as
  perflog -> `--env` through `set_env_pref`, in that order; exits on any failure rather than running on the wrong
  binary or silently dropping an env var.
- `restore_master(dev)`: called in `main()`'s existing `finally` (alongside `titlestate.release`), so it runs even
  if the hold raised. Rebuilds/installs plain master and verifies the versionName no longer reads as perflog. If
  restore itself fails, it prints and does not raise (the guard above is the real backstop for the NEXT run, not
  this one) -- raising here would mask whatever exception `agent.run()` raised, which matters more.
- `agent.result["build"] = "perflog"` and `agent.result["env"] = [...]` recorded in `result.json` whenever
  `--perflog` is used -- unconditionally, before `agent.run()`, so even a run that never reaches `finish()`
  cleanly still has a chance of being caught by a downstream reader if `result.json` is ever written partially.

**WAITING: a grant for `docs/testing/title_verdict.py` (and possibly `docs/testing/title_registry.py`), not in
this lane's territory.** The "never banked" requirement needs title_verdict.py to read `result.json`'s new
`"build"`/`"env"` keys and void any run with `"build": "perflog"` (the same `void` mechanism it already uses for
`display-black`/`thermal-pause`/etc., which `title_registry.py` already treats generically as never a Playable
candidate -- confirmed by reading `title_registry.py` lines 623/660-661, so a single `void` string in
title_verdict.py is very likely sufficient for both "the registry" and -- as far as I can find -- "the sweep
list" the brief names (I could not locate a third file with that literal role: `score_sweep.py` is the
isolation-golden sweep, unrelated to title verdicts; `title_registry.py`'s own VOID-aware status computation
appears to BE the thing a title-readiness sweep would read). The exact patch, for whoever has the grant:
  - in `judge()`'s VOID block (after the existing `elif rframes and all(...)` check, before `held = re.search(...)`):
    `elif res.get("build") == "perflog": void = "build: perflog APK (~1.2 ms/frame render-thread overhead) -- a telemetry hold, never a Playable candidate"`
  - in the `v = dict(...)` construction a few lines down: add `build=res.get("build"), env=res.get("env")`.
I did not make this edit myself (reverted it once already, see git history on this branch) -- `title_verdict.py`
is outside `docs/lanes/pathtele1013/**` and `docs/testing/titles/{pathfind.py,pathfind_selftest.py}`, and the
brief's territory rule is explicit: any other file needs a grant, named here, then stop. Until the grant lands
(or lane.local makes the edit), `pathfind.py`'s own side is complete and safe on its own: `result.json` always
carries `"build": "perflog"`, so whoever reads it (today: a human; after the grant: title_verdict.py too) has
what they need to exclude it by hand.

## 5. Offline tests (`pathfind_selftest.py`)

Added, no device: `_is_perflog_version` (plain/dirty/unread), `perflog_start` (the leftover-perflog-APK refusal,
and that `--perflog` itself is never refused by it), `perflog_setup`'s install order (`build_ref` -> install ->
verify -> `apply_env_pref`, asserted from a fake device's call log) and its `--env` pass-through (the exact
`{"env": [...]}` JSON `apply_env_pref` would read), a setup failure exiting rather than running silently, and
`restore_master` running (and succeeding) inside a `finally` even when the guarded block raised, with the
original exception still propagating. All against a `_FakeDevice` plus `pathfind._dispatcher_call` monkeypatched
to stand in for dispatcher.sh (no adb, no shell-out) -- `build_apk`/`set_env_pref`'s own Python logic (stdout
parsing, the request-JSON temp file) runs for real; only the shell-out at the bottom is faked.

## 6. Part C

Not this lane's: lane.local runs the three telemetry holds (KOTOR II, SC Double Agent, M:I Surma) on the Nova
after this branch folds. Exact command lines are in PR.md.
