# profileddefault1008: TU_AUTOTUNE_ALGO=profiled behind an autotune override; fleet A/B read, default does not flip
State: ready

Lane: profileddefault1008          Issue: #433, #474
Base: master @ 7960e78e20
Files: android/app/src/main/cpp/xemu_android.cpp, docs/lanes/profileddefault1008/NOTES.md, docs/lanes/profileddefault1008/PR.md, docs/lanes/profileddefault1008/pgraph_register.py, docs/lanes/profileddefault1008/soak_register.py, docs/testing/predictions/profileddefault1008-pgraph.json, docs/testing/predictions/profileddefault1008-*.json, docs/testing/titles/routes/fps786-topspin.route
Prediction: docs/testing/predictions/profileddefault1008-pgraph.json (registered, a_ref == b_ref == 54f8fb48ea); per-title soak predictions follow the pilot
Needs device: yes    Needs NDK: yes
Release note (none): the compiled default stays bandwidth (kAutotuneProfiledDefault = false); nothing a player sees changes unless the fleet A/B below flips it.

## Change

`ApplyRenderMode` (xemu_android.cpp, the grant) now carries `TU_AUTOTUNE_ALGO`
behind a per-game `autotune` runtime override (same channel as `render_mode`),
a guard list (Blinx #527, Kabuki Warriors gmem474), and a compiled default
that is `false` until this lane's fleet A/B clears its win rule. A request's
`--env TU_AUTOTUNE_ALGO=...` always wins, which is how the A/B sets its arms.
Full rationale and the rule (written before any run) are in NOTES.md.

## Status

Build: `BUILD SUCCESSFUL in 4m 53s`, apk sha256
`f1d28bf29ae68a3645fd020a0a7255e71530ac35be6d61e4ae80f6b864a006eb` at
`cd557f569e`.

Checked every brief candidate against actual Nova inventory (dispatch
history + targets.toml, not assumed) before queuing anything: Crash
Twinsanity, Black and Otogi have no Nova copy on record and are dropped;
RalliSport stays excluded per the brief and the owner hold. Kept: Halo 2
(blocked separately -- pathfind's own two sessions never reached confirmed
gameplay, "Armory camera does not respond"; dropped from this A/B, not a
route-generation gap), Top Spin, Tron 2.0 (has a usable pathfind steps.jsonl
but reaching its gameplay window needs replicating a ~530 s intro/cutscene
sequence faithfully -- deferred, not attempted blind), Fuzion Frenzy (pilot
first, CRASH_OR_HANG last run), Crimson Skies (guard), Kabuki Warriors
(stall guard), Forza (control; #583's fix is present on this branch, so its
owner-hold floor should not apply, but `invalid=` is watched per the fix's
own memory note).

Pilot DONE, both clean: Top Spin bandwidth arm
(`1-1791521412-lane.profileddefault1008-3730973`, gfps 47.1/41.4 all/last-2/3)
and Fuzion Frenzy bandwidth arm
(`1-1791521422-lane.profileddefault1008-3732463`, gfps 42.6/44.4) -- no
crash/hang/thermal pause on either; the 09-27 Fuzion Frenzy `CRASH_OR_HANG`
does not reproduce. Both ran at `--ref e85e55450d`, one ref behind the five
registered predictions' `a_ref`/`b_ref` (`7e51edfe98`) -- informational
only, not the scored A-arm; see NOTES.md Attempt 3 for the ref-gate math.

Wrote `pilots/lane.profileddefault1008.ok` and queued the full scored batch:
10 requests, 5 titles x 2 arms (bandwidth then profiled), all
`--ref 7e51edfe98 --device nova --seconds 600 --perflog --frames-every 30`:
Top Spin, Fuzion Frenzy (candidates), Crimson Skies (guard), Kabuki Warriors
(stall-guard), Forza Motorsport (control). Request ids in NOTES.md.

**Scored batch read (full results table and rule application in NOTES.md
Attempt 4).** 8 of 10 requests landed DONE; Kabuki Warriors' two arms
ERRORed (title not on the Nova's SD card at run time -- a device-inventory
gap outside this lane's grant, not a measurement). Verdicts under the rule
written before any run:

- **Top Spin (candidate): HOLDS** -- gfps within +/-1 (32.57 vs 32.66
  median), J/frame 0.97x bandwidth's. Fewer/smaller hitches and lower
  J/frame on profiled, but not past the WINS bar.
- **Fuzion Frenzy (candidate): WINS** -- gfps 58.03 vs 38.71 median (1.50x,
  past the 1.08x bar), J/frame 0.79x bandwidth's. Confirms the pilot's
  informational read and gpunonrender's DOA3/NG Black findings.
- **Crimson Skies (guard): HOLDS** -- identical gfps, J/frame 1.01x. No
  regression on the already-Playable title.
- **Forza (control): LOSES** -- windowed gfps 26.61 vs bandwidth's 28.92
  (steady across first/second half, not transient; no thermal pause,
  no climbing `invalid=`). This contradicts the Xfr/T=0.13 premise this
  lane queued Forza as a control under. No named cause found this lane, so
  per the rule it is **not** added to the guard list -- flagged for
  follow-up instead.
- **Kabuki Warriors (stall-guard): VOID** -- title absent from the Nova at
  run time.

**Default does not flip** (`kAutotuneProfiledDefault` stays `false`,
confirmed unchanged at the current tree): only 2 of the brief's candidates
actually ran (Halo 2 and Tron 2.0 were dropped/deferred before any run, see
Status above), short of the rule's >=3-candidate-WINS bar regardless of
score; and Forza's unresolved regression is reason on its own to hold the
flip open even had the count been met. Full reasoning, the guard-list
decision, and what the next lane should not repeat are in NOTES.md.

## Checks

| check | result |
|---|---|
| `docs/testing/preflight.sh --allow-tracker` | passed |
