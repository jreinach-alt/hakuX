# profileddefault1008: TU_AUTOTUNE_ALGO=profiled behind an autotune override; fleet A/B in progress
State: draft

Lane: profileddefault1008          Issue: #433, #474
Base: master @ 7960e78e20
Files: android/app/src/main/cpp/xemu_android.cpp, docs/lanes/profileddefault1008/NOTES.md, docs/lanes/profileddefault1008/PR.md, docs/lanes/profileddefault1008/pgraph_register.py, docs/testing/predictions/profileddefault1008-pgraph.json, docs/testing/predictions/profileddefault1008-*.json
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

Pilot queued (`lane.profileddefault1008`'s first requests, no `pilots/*.ok`
yet): Top Spin bandwidth arm (`1-1791521412-lane.profileddefault1008-3730973`)
and Fuzion Frenzy bandwidth arm (`1-1791521422-lane.profileddefault1008-3732463`),
both `--device nova --seconds 600 --perflog --frames-every 30`.

<!-- updated once the pilot and the full A/B read -->

## Checks

| check | result |
|---|---|
| `docs/testing/preflight.sh --allow-tracker` | passed |
