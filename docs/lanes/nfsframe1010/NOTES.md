# lane.nfsframe1010 — NFS Most Wanted race start: where the rest of the frame goes

Issue: #433 umbrella, no own issue (dispatched directly by lane.local). Nova
only, measurement only, no fix.

## 1. What this lane answers

lane.local's "Why" (briefs/nfsframe1010.md) reads perdrawon1010's race-start
runs and leaves three gaps open:

1. ~12 ms per frame between `Tot` and the real period.
2. The ~10 ms post-flip idle (`Fr`): game code or an emulator debt?
3. The other ~5-6 ms of `Sub`: which finishes, ms per reason.

## 2. Instruments: what each one actually measures (checked against source,
not assumed)

- **`hakuX-phase`/`hakuX-pace`** (always on, `profile.c`): per-~1s-window
  averaged phase ms and vblank histogram. `Fr`/`St` in `Idle` are
  `p->fifo_idle_frame_ms`/`p->fifo_idle_starve_ms` — PFIFO-thread idle split
  by "waiting for the guest to push more work" vs "starved" — a PFIFO-side
  measurement, not a vCPU-side one. Correlated with what the guest is doing,
  not proof of it.
- **`hakuX-perf` `gfps=`** (profile.c:794-799, same `% 60 == 0` tick as
  `hakuX-pace`): carries `nv2a_profile_get_pacing_str` — display frame time
  vs the limiter's interval, game-frame-time (flip-to-flip) histogram. This
  is the line `armread.py`'s row-keying (`"hakuX-perf" in ln and "gfps=" in
  ln`) actually opens a row on. **Checked against the real captured logcat**
  (`dispatch/results/1-1791644405-perdrawon1010-365120/logcat.txt`): 309
  `hakuX-perf ... gfps=` lines present, matching the 309 `hakuX-pace` lines
  1:1 (same tick). The copied `startread.py`/`armread.py`/`togread.py` chain
  parses this build's logs correctly as-is; no tag mismatch, despite the
  surface read of `hakuX-pace`'s own line format (`f=.. v0=.. vb=.. ms=..`,
  no `gfps=` substring) looking at first grep like a different line than
  what `armread.py` opens on. They are two lines from the same tick, and
  `armread.py` wants the first one.
- **`hakuX-stall`** (`draw.c` `opt_stats_log_and_reset()`, gated
  `++frame_counter % 60 == 0`): `g_opt_stats` **is memset to zero right
  after each log** (draw.c:1179 and :1183, both branches of the `#ifdef`).
  So every `Finish:`/`sd[...]`/`dif[...]`/`pipe[...]` count on a hakuX-stall
  line is a **60-guest-frame-window delta**, not cumulative-since-boot.
  Dividing by 60 gives the per-frame rate the brief's own numbers are stated
  in ("1.5 `sd`", "1.2 `stl`"). No diffing needed, unlike `[jc425]`'s
  `prev[]` pattern in cpu-exec.c, which is a different counter family.
- **`hakuX-rr425w`** (tag `hakuX`, level WARN, always on, `cpu-exec.c`):
  books the Xbox kernel idle loop (`sti;nop;nop;cli`, guest pc
  `0x8001b02e`) vs busy, keyed by the waking interrupt vector and the NV2A
  units pending at wake (`hakux_nv2a_irq_units()`). This is the Q2
  instrument: it is vCPU-side, and it answers "is the vCPU idle-looping or
  doing real guest work" directly, unlike `Fr`/`St` above. 253 occurrences
  already in the captured logcat — no new env var, no new run needed for
  this question.
- **`HAKUX_FRAMETRACE=1`**: Vulkan fence/submit wait attribution by call
  site. Candidate for closing Q1 (the PFIFO-thread-outside-every-phase
  possibility) and Q3 (ms-per-Sub-reason, if `hakuX-stall`'s raw counts need
  a per-call-site ms cost to turn counts into ms) if the baseline runs
  below do not already close them.
- **`HAKUX_PMU`**: on-CPU attribution (IPC/stalls at the TB level). Not
  off-CPU attribution; ruled out for Q2 for that reason (pmucounters'
  own PR.md reaches the same "waits, not slower code" conclusion from a
  different angle — on-CPU counters are flat between fast and slow slices).
- **`capture_offcpu.sh`** (vcpuwait433/tron2, direct-adb simpleperf
  `--trace-offcpu`): the method other lanes used for vCPU off-CPU
  attribution, but it bypasses `request.sh`/`ab_run.sh`. Ruled out here —
  this lane's rules are explicit that those two scripts are the only way to
  a device. `hakuX-rr425w` is the compliant substitute; its question is the
  same.

## 3. Is perdrawon1010's existing pair "master's head build"?

`1-1791644405` (fix off) and `1-1791645060` (fix on) both ran at ref
`4ad1154e55` (perdraw1009's branch tip), which is **not** an ancestor of
`origin/master` (07937793af at the time of this lane). Checked the diff:

```
git diff --stat 4ad1154e55 origin/master -- hw/ accel/ ui/ target/
 hw/xbox/nv2a/pgraph/vk/renderer.h |  11 --
 hw/xbox/nv2a/pgraph/vk/shaders.c  | 234 ------------------------------------
```

and `git log --oneline origin/master..4ad1154e55 -- <those files>` shows
those lines are perdraw1009's own three commits adding
`HAKUX_UNI_BULK`/`_UBERCACHE`/`_FOGCACHE` (default OFF) and
`HAKUX_UNI_TOGGLE` — code `master` does not have, not code `master` removed.
Nothing else outside `docs/`/`briefs/`/predictions differs between the two
refs. So the "fix off" run's *compiled behaviour* (switches default off) is
identical to what `master`'s head build would produce; but it is not
literally a `master`-ref run, and it is perdrawon1010's data, gathered for a
different question (the per-draw switch A/B). The brief asks this lane to
run its own 2 runs on `master`'s head build and use only this lane's
numbers for the deliverable — queuing those now (§4), pinned to
`origin/master`'s exact sha so the ref is unambiguous, same route, no env.

## 4. Device runs

Queued via `request.sh` (never direct adb), `--who nfsframe1010`,
`--route nfs-mw-quickrace`, `--title 4541007B-Need_for_Speed_Most_Wanted.xiso.iso`,
`--seconds 500`, `--device nova`, `--ref 07937793af` (master's head at
queue time), no `--env` (master has no per-draw switch to flip),
`--no-expect "telemetry, not an A/B arm"`, `--priority study`. Two
separate requests (soak path ignores `--runs`; the replicate is the run,
not the window, per `request.sh`'s own comment):

- `1-1791649039-nfsframe1010-2037292` (run 1 of 2), queued 2026-10-10.
- `1-1791649724-nfsframe1010-2219502` (run 2 of 2), queued 2026-10-10.

The Nova was running texscan1010's `1-1791648919-texscan1010-2004607` at
queue time; both requests sit behind it. `docs/lanes/nfsframe1010/WAITING`
names both — lanewaker resumes this lane when they land. First `--wait`
attempt on run 1 was killed at the Bash tool's background-task boundary
(exit 143) after the request had already been written to the queue, which
is why run 1 was re-verified present in `dispatch/queue/` rather than
re-queued, and why run 2 was queued without `--wait`.

## 5. Next, on resume

Once both results land: verify from `route-frames/*.png` that the car is
moving in the windows judged (brief's explicit check), then write the
per-heavy-frame accounting table (named block / ms / instrument, summing
to the period) and the P×win ranking using `hakuX-phase`, `hakuX-pace`,
`hakuX-stall` (÷60 for per-frame reason rates, §2) and `hakuX-rr425w`
(vCPU idle-vs-busy by wake vector, §2) from these two runs — reusing
`armread.py`'s row/window extraction via the copied `startread.py`. Open
`HAKUX_FRAMETRACE=1` as a third run only if Q1 (the ~12ms Tot-vs-period
gap) or Q3 (ms per Sub reason, vs `hakuX-stall`'s raw counts) is still
unexplained after these two.

## 6. Why attempt 1 did not finish

Attempt 1 queued the two runs in §4, pushed `WAITING` naming both, and
correctly ended the session there — a run was outstanding and the lane
contract says to stop rather than poll. That is not what blocked the
lane: both runs landed DONE (`1-1791649039-nfsframe1010-2037292` at
09:42, `1-1791649724-nfsframe1010-2219502` at 10:09) and attempt 1 simply
ran out of turn before lanewaker resumed it to read them. Reading them in
attempt 2 (this session) surfaced a problem attempt 1 had no chance to
catch: **those two runs cannot answer the brief**, for a reason specific
to this build, not to the route or the reader.

## 7. The two baseline runs are telemetry-blind: `hakuX-phase` needs a perflog build

Checked both runs' logcats directly rather than trusting the copied
reader to say so:

```
hakuX-phase: run1=0 run2=0
hakuX-cpu:   run1=0 run2=0
xemu-vsync/xemu-surf/xemu-work/xemu-gpu: 0 in both
hakuX-stall: run1=16 run2=16, and every line is `ubo_ring_grow: n.. pools.. sets..`
             (draw.c's pool-growth log), not one `Finish:`/`sd[...]`/`dif[...]` line
```

Read `hw/xbox/nv2a/pgraph/profile.c:896` (`#if defined(__ANDROID__) &&
NV2A_PERF_LOG`): the entire phase/cpu/vsync/surf/work/gpu block this
brief's table is built from — `nv2a_profile_get_phase_timing_str`
(`Surf:/Tex:/Shd:/Draw:/Fin:(Sub:/Fen:)/Flip:/Idle:(Fr:/St:)/Tot:/GPU:`,
the exact fields the brief's "Why" table quotes) — is compiled out unless
`NV2A_PERF_LOG` is defined, and `android/app/src/main/cpp/CMakeLists.txt:973,1093`
only defines it when gradle is invoked with `-Pperflog=true`. That is not
a runtime env flag; `docs/testing/dispatcher.sh:1019-1040` (`build_ref`)
builds a **second APK variant**, cached under `$sha-perflog.apk` with a
different `apk_sha`, and only when the *request* carries `"perflog":
true` — which needs `request.sh --perflog` at queue time
(`docs/testing/request.sh:169`). Neither of attempt 1's two requests
passed it (`request.json` for both: `"perflog": ""`), so both built and
ran the plain APK, which — per dispatcher.sh's own comment at line
2076-2083 — "produced ZERO phase lines while the binary was correct,
which reads exactly like a soak that measured nothing." Exactly what
happened here. The `hakuX-stall` tag is NOT perflog-gated — it is
always-on — but draw.c's `g_opt_stats` `Finish:` line this lane's §2
describes is itself inside the same `#if NV2A_PERF_LOG` guard family
(checked: the `ubo_ring_grow` line is a *different*, always-on call under
the same tag; the `g_opt_stats` line never fires without the perflog
build). So §2's reading of `hakuX-stall` was right about the mechanism
and wrong about availability without a flag this lane had not yet found.

This is not a dead end for the brief's Q1-Q3, because the finding is
mechanical and the fix is a request flag, not a new instrument:
`hakuX-pace`/`hakuX-perf` (always-on, confirmed present and correct in
§2) still give frame period and vblank histogram from the two done runs,
but the Draw/Fin/Sub/Idle/Fr/GPU breakdown the deliverable table needs
only exists in a perflog build's log.

**Queued two replacement runs**, same ref/route/title/device, this time
with `--perflog`:

- `1-1791653167-nfsframe1010-3263852` (perflog run 1 of 2)
- `1-1791653177-nfsframe1010-3266390` (perflog run 2 of 2)

`docs/lanes/nfsframe1010/WAITING` now names these two (the prior two are
DONE and kept only as the always-on pacing cross-check — §8). This still
fits the brief's "run 2 runs on master's head build": the perflog binary
is the same source ref (`07937793af`), differently compiled; its
`apk_sha` will differ from the plain build's, which is deliberate
(dispatcher.sh's own reasoning: a mixed-variant table would be silently
wrong without that).

## 8. What the two non-perflog runs are still good for

Not wasted device time — `hakuX-pace`/`hakuX-perf` are unaffected by the
perflog flag (always-on), so these two runs are a same-ref, non-perflog
cross-check on frame pacing once the perflog pair lands: if the perflog
build's `hakuX-pace` numbers (period, vblank histogram) disagree with
these outside noise, that is itself a finding (the extra instrumentation
changing the measured frame rate — dispatcher.sh's own stated risk for
the *reverse* mix-up, worth checking even though this lane did not mix
APKs). Quick read of run 1's `hakuX-pace` tail (last line, closest to
whatever heavy frames logged near it) deferred to the next section, once
the perflog pair's phase lines are in hand and can be lined up against
the same wall-clock window.
