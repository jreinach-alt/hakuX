# lane.fpsdiag1018 -- one lane for GTA III, Blinx 2, Fable (#433)

Owner, 2026-10-18 ~15:15 PDT: stop chasing each title separately. Review what is known, say what the
cause is NOT, list what it COULD be, build a diagnostic tool that tells the candidates apart -- no gameplay
navigation, capture only during a window someone else supplies (owner play, a save state, a parked menu).

## 0. Already-tried (read before proposing anything)

Everything below is read off the named lane's own branch (several are not yet folded into master; read with
`git show origin/lane/<name>:docs/lanes/<name>/<file>`) or off a committed memory note. A row that a candidate in
FINDINGS.md section 3 would repeat is marked **do not re-propose**.

| Lane / source | What it targeted | Result | Do not re-propose |
|---|---|---|---|
| gta3fps1017 | S2T copy census on foot; R1 (`HAKUX_S2T_DRAIN`, skip #474's PFIFO drain ahead of a plain colour copy) | On foot: 2.00 copies/flip, 100% `map`, dup 0 -- 36x below the driving burst. R1 folded (4a504d9aaa), removes ~11.6 ms/flip of PFIFO wait in pilot 343857 | R1 as an open lever (it's in); the on-foot census as a stand-in for driving |
| gta3fps1017b | R2 `HAKUX_S2T_WIDEN`, R3 `HAKUX_S2T_SHARE`; cross-title dip-signature table (GTA III/SA/Blinx 2) | R2/R3 written, off by default, pixel-safe. Section 5.2's signature: G up, Df up, Tq up, Ri down, tc (PGRAPH CPU) up, in all three titles' dips, different magnitudes | R2/R3 as a Blinx 2 or SA lever (no S2T copies measured there); re-deriving the signature table |
| gta3drive1017 | Six scripted drive-into-car routes; pilot 343857 (driving, perflog) | All six routes VOID (help-box gate, mission restart, car-flip). Pilot: #474 drain 71.9/flip = 11.6 ms/flip; vertex-hazard finishes ~0.3/flip flat; PFIFO-side pgraph.lock (`lw`) = 0; pipeline compile <=2 ms/flip; texture dirty walks in microseconds; GPU busy only 21.9 of 47 ms (idles half the frame) | **No seventh scripted drive.** Vertex hazards, PFIFO-side pgraph.lock, pipeline compile, texture-dirty-walk time, or "GPU-saturated" as GTA III's driving cause |
| lane gta3fps1017b's owner A/B (10-18 01:00-02:07, Nova) | R1/R2/R3 fps verdict, in-car, palindrome batches | R1: +1.9 / +2.7 fps parked (two batches). R2: removes all 70-133 copies/flip, fps -0.3 / -0.9 (no gain) -- **falsifies the copy theory for the parked in-car scene**. R3: inert (dup 0 in GTA III; Blinx 2 island has zero `[s2c]` copies at all, idle and moving) | The S2T copy/dup path as a lever for GTA III's remaining dip or for Blinx 2 at all; re-litigating R2/R3's fps verdict from any non-palindrome batch (see next row) |
| gta3dip1018 | Decompose the GTA III parked-car frame now that R2 shows 0 copies and no fps change | `b3` run is NOT a controlled arm comparison (A alone pays a ~50 s one-time cold-shader-compile tax before B/C warm up from A's own disk cache) -- do not use its cross-arm G means as an R2/R3 measurement. `hakuX-stall RPBreaks:/Finish:` is racy once the deferred-finish path is active (two threads print the same non-atomic global) -- not citable per-window in the park/dip regime. Owner capture's two multi-second stalls (1.46 s, 3.89 s) are both inside the one cold-compile window that ends by 07:38:23; the sustained 16-22 fps dip afterward (07:38:34-55, 07:39:14-30) runs with **no** active compile. Ranked lever 1: non-copy render-pass-break triggers (~53-55 passes/frame in a static parked scene, 2-4% not ~19x apart across copy counts) | b3's arm-to-arm comparison as an R2/R3 fps measurement; `hakuX-stall RPBreaks/Finish` numbers from any park/dip window at face value; cold shader/pipeline compile as the sustained-dip cause |
| gta3instr1018 | `[dipwin]`/`hakuX-rpbrk` line census, on foot (GTA III and an attempted Fable run) | On foot: 7.64 render-pass ends/flip (`bsnb` 4.02, `bnd` 1.99 [of which copy 1.12, deferred-download 0.81], `bclre` 1.01). **93% of `Fen:` is one memcpy**: the frame-slot rotation's stale vertex-RAM span copy, 2.19 of 2.36 ms/flip, 117-508x the bytes actually uploaded. In the car (from b3-B, older `hakuX-phase` line): 52.4 render passes/frame vs 7.7 on foot, GPU render 19.6 ms vs 8.4. Fable run never reached gameplay (route ended on the main menu at 147.8 s) | Re-running the on-foot-only census as if it answered the in-car question; "texture dirty walks," "pgraph.lock," or "pipeline compile" for GTA III (already ruled out above) |
| vtxstale1018 | Fix the stale-span copy: per-page bitmap instead of per-slot span | Selftest: 3000 random rotations, bytes copied 891,623,514 -> 118,468,608 (byte-identical result, 0 slots differ). **On-foot device number is "pending"** -- never run in the car | Claiming this fix's in-car effect without a device number; it is unmeasured there, not negative |
| fabledip1018 | Decompose Fable's and Blinx 2's gameplay dip | Both match gta3fps1017b's cross-title signature. **TLB re-arm walk time is ruled out as the direct cost in both** (131 us/frame of a 57.4 ms frame on Fable, 0.03%; Blinx 2's walk time stays a small fraction of render-thread CPU through its door-transition dip except one anomalous window at 2%). `redo/dirty` ratio is flat 2.0-2.8x in Fable (genuine dirty volume rising) but climbs 3.16->4.87 across Blinx 2's door (bookkeeping falling behind -- a different mechanism in the same subsystem). Fable's opening ~34 s stutter is **not** shown to be cold shader compile (no compile line logged before it resolves, renderer thread idle throughout, shares timing with an audio-ring-buffer warm-up instead); one later **isolated** 3.78 s spike at 07:01:43 **is** a cold pipeline-link compile, a separate single-frame event | TLB-walk-count reduction (`tlbmap.mbox`, widening the REDO budget) as a lever for either title -- walk time is already <2% of the frame, so even removing it all cannot close a 20-40 ms/frame gap; claiming Fable's sustained opening stutter is shader compile |
| drawrec1010 | `HAKUX_DRAWREC` (now default-on via fastpaths1010): defer TLB re-arm, stop re-triggering the full shader-bind path | Folded, default on (`fastpaths1010-screen.json` does not block GTA III/Blinx 2/Fable). NFS A/B: the **walk-count leg was REFUTED** (fell to 64-68/flip, not <=20, because each merged run still costs one full TLB scan) | Re-measuring whether DRAWREC is "on" for these three titles -- confirmed on by its absence from the fastpaths block list; a plain "cut the walk count further" lever without a grant on `accel/tcg/cputlb.c`/`system/physmem.c` |
| fpstel1018 | Decompose Forza's and Buffy's misses (different titles, same renderer) | #804 fence wait and #474 pgraph.lock wait (`lockw`) both measured ~0 for Forza and Buffy specifically. The S2T copy/bind path's own wall time (`bt`/`cp` in `hakuX-stall txw[...]`) is checked directly against both titles' telemetry and is 0.00-0.4 ms: **not exercised** by either. Forza's fps is flat whether racing or on a static results screen (a near-fixed per-frame guest/vCPU cost, not scaling with scene complexity). Buffy's steady-state gap (`F` minus the four measured phases) is 7-9 ms, unattributed, growing to ~19 ms in the slowest decile, outside GPU/Draw/Finish/Idle instrumentation entirely | #804 / pgraph.lock for GTA III/Blinx 2/Fable **without a measurement on those specific titles** -- this row rules them out for Forza and Buffy only, a different title and render pattern; carrying a cross-title refutation over without its own measurement is exactly the falsifier mistake the brief warns against |
| gpuclock | Is the GPU clock-limited (any title)? | Stock governor sits at its floor 78-88% of samples across every title sampled so far (Tron, Forza, Nightfire -- **not** GTA III/Blinx 2/Fable). The `[gpuclk433]` instrument (GPU ms/frame vs clock, CPU-core clock/thread-affinity `cseq`) exists only on this branch, **not folded into master** | Assuming the governor-floor finding transfers to these three titles without a `[gpuclk433]` run on them; assuming the instrument is available until this lane folds |
| gta3car1018 | `HAKUX_S2T_FB`: keep a slot's render-target-as-texture copy across a run of draws instead of copying per draw | In-car A/B (RT held 60 s): off 24.8 fps/57.11 passes, `=1` run1 26.8/20.15, `=1` run2 22.6/33.67 (run-to-run spread larger than the effect), `=2` run1 27.9/38.20. Both values cut passes and raise fps on a first reading; **neither reaches 30 fps while driving**; switch stays off by default (fence wait and stalled finishes still 10-15 ms/flip after the switch in heavy traffic) | Claiming `HAKUX_S2T_FB` as a finished fix; re-running a single in-car arm as if it settles the switch (one run per value did not settle `=1` vs `=2`) |
| gta3fps1017 / belowbar1005 methodology | "ruled out" standard | A theory is ruled out only by a measurement that could have shown it; a lever that moved nothing falsifies the theory only if the arm actually acted on the thing (memory `mutant-must-reinstate-the-weaker-rule`, `below-bar-means-telemetry-not-retest`) | Treating an untested theory as ruled out; treating a refutation on one title as covering another |
| `vcpuwait433/decompose.py` | Off-CPU-by-wake-vector decomposition (`[rr425w]`, `[idlehalt]`, `[rwait526]`, `[lock474]`, `[tlb68]`) | Needs a literal `ROUTE ... mark gameplay` line in `run.log`. Checked by grep (not assumed): `[rr425w]`/`[idlehalt]` **are** unconditional, always-on lines -- present in every capture this lane reads, including the owner-play host captures (265/269 matches in `owner-play-1018`'s logcat alone) that have no `run.log` at all. The blocker is only the mark-line requirement, same as fpstel1018 found for Forza's `drive`-script route | Running `decompose.py` directly against an attach-style host capture (no `run.log` to hold a mark line); re-deriving that the tags themselves are present -- they are, and fpsdiag.py's own analyzer reads them directly instead of requiring a mark line |

**Stop rule (carried forward):** the same analysis failure twice for one cause means stop and report. Not hit this
lane; each step below had a capture or a source file to read.

## 1. What this lane did (chronological)

1. Read every lane/memory source named in the brief plus `vcpuwait433/decompose.py`'s own field reference (none of
   this lane's branches are folded into master yet, so each was read with `git show origin/lane/<name>:<path>`).
2. Grepped the current (master) source for every perflog tag's print site (`hw/xbox/nv2a/pgraph/profile.c`,
   `vk/draw.c`, `vk/texture.c`, `vk/shaders.c`, `vk/compile_worker.c`, `vk/instance.c`, `system/physmem.c`,
   `system/cpus.c`, `accel/tcg/cputlb.c`, `accel/tcg/cpu-exec.c`) to fix the exact field names and which tags are
   unconditional vs perflog-only vs `NV2A_PERF_LOG`-only, so the tool's parser matches what a real capture can
   contain rather than what an older write-up's shorthand implied.
3. Wrote FINDINGS.md (Known / Not / Could be) -- done, this commit.
4. Building `docs/testing/perf/fpsdiag/fpsdiag.py` (`capture`/`analyze`/`gaps`) -- next.
5. Will run `analyze` against every capture on disk for these three titles (see FINDINGS.md section 4) and the
   synthetic selftest fixtures.
6. Will write `docs/testing/jobs/selftest.d/99-fpsdiag.sh` and `CAPTURE.md`.

## 2. What the next lane should not repeat

- Do not propose the S2T copy/dup path for GTA III's remaining in-car dip or for Blinx 2 at all (zero copies
  there); do not propose it for Fable without first running a census (none exists -- Fable's `[s2c]` state is
  genuinely unmeasured, unlike Blinx 2's).
- Do not propose TLB-walk-count reduction for Fable or Blinx 2; walk time is already <2% of the frame in both.
- Do not propose cold shader/pipeline compile for the sustained dip in any of the three titles; it is ruled out
  for GTA III's sustained dip and for Fable's sustained opening stutter specifically (both measured, not assumed).
- Do not read `hakuX-stall RPBreaks:/Finish:` from a park/dip-phase GTA III window as quantitative; it races.
- Do not carry the Forza/Buffy #804-and-pgraph.lock refutation over to these three titles without its own run.
- Do not run `vcpuwait433/decompose.py` directly on an owner-play host capture; it needs a `run.log` mark line
  this capture style does not produce. The tags it reads are present and fine to read directly instead.

## 3. Open questions for the owner (not blocking; keep working)

- `[gpuclk433]` (the GPU-clock-vs-fps instrument) lives on `origin/lane/gpuclock`, unfolded. Should this lane's
  "gaps" list wait for that fold, or should fpsdiag.py's `capture` read the clock via the raw sysfs nodes
  `gpuclock/NOTES.md` already names (`kgsl` `gpuclk`/`gpu_busy_percentage`) directly, independent of that lane's
  own instrument landing? Taken the second way below (section 2 of FINDINGS.md's tool spec), since it needs no
  code fold.
