# savestate-req1019: load a save state through request.sh -- no hand-driving to reach a scene (#433)

State: draft

Lane: savestate-req1019          Issue: #433
Base: master @ 656bcd1fe9
Files: docs/testing/request.sh, docs/testing/dispatcher.sh, docs/testing/scenes.tsv, docs/testing/jobs/selftest.d/99-load-state.sh, docs/testing/jobs/roles/lane.md, AGENTS.md, docs/lanes/savestate-req1019/**
Prediction: none: no arm (mechanical feature work with a falsifier fragment, not a pixel/perf claim)
Needs device: yes (one proof run)    Needs NDK: no (mechanism (a): no APK change)

Mechanism (a) built, no APK change: `request.sh --scene <name>` (sugar for `--load-state` +
`--hold-trigger`, from `docs/testing/scenes.tsv`) and `--load-state <slot-or-file>` isolate the target
slot (park every competing file, since `hxs_newest_loadable()` picks by the state's own `saved_at`, not
mtime), set `savestate_auto_load=1` for the run, launch, and wait on `[savestate] op=load ... ok=1` in
logcat; `--hold-trigger rt:<seconds>` holds a pad axis after the load and logs device-clock down/up times
for score2.py. Any `op=save`, a load timeout, or a refused load -> VOID with a reason, never a silent run.
The parked file and the pref are restored after every run, pass or VOID. `docs/lanes/savestate-req1019/
NOTES.md` has the full design writeup.

Falsifier `jobs/selftest.d/99-load-state.sh` passes: 32 checks, 0 failed, including a mutant that drops
the restore step and correctly fails case (d). Docs added: AGENTS.md ("Loading a scene without driving
the device", beside "Working with a device") and `jobs/roles/lane.md`.

**Device proof: blocked on this PR's own fold, not written yet.** `hakux-dispatcher.service` execs
`/home/justin/hakuX/docs/testing/dispatcher.sh` -- a separate, pre-fold tree with none of this code -- so
a real `--scene gta3-incar` request today is served by a dispatcher that has never heard of
`load_slot`/`hold_trigger`/`scene`. Tried it for real (tier `1-`, `--device nova`, id
`1-1792450834-savestate-req1019-3775536`): it silently ran an ordinary 60 s soak and filed the result as
the scene, with every new field null and no `op=load` line -- no error, no VOID. That is the exact
failure mode request.sh's existing `--skip-tests`/`--audio-capture`/`--only-tests` guards exist to catch
(request.sh:660-684 etc.), and `--load-state`/`--scene` was missing the same guard. Added it (checks
`scene_verdict` in both the `DISPATCH_TREE` and the `DISPATCH_DIR/bin` snapshot); the same real attempt
now correctly refuses at queue time instead of running. Selftest case (f) (3 checks) covers the new guard
directly. `NOTES.md` has the full incident writeup and the exact command to re-run once folded.

State stays `draft` until that device proof is run and recorded here, per the brief.

Board request filed (`$DISPATCH_DIR/board-requests/savestate-req1019.md`) for the files above -- several
show as held in territory.toml by rows whose own notes say RELEASED/FOLDED and that have no live
`$DISPATCH_DIR/fleet/*.json` entry; flagged there for the board to resolve, proceeded on the brief's own
Files: line in the meantime. Mechanism (b) (android/app/src/main/cpp/xemu_android.cpp) was not needed.
