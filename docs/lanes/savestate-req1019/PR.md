# savestate-req1019: load a save state through request.sh -- no hand-driving to reach a scene (#433)

State: draft

Lane: savestate-req1019          Issue: #433
Base: master @ 656bcd1fe9
Files: docs/testing/request.sh, docs/testing/dispatcher.sh, docs/testing/scenes.tsv, docs/testing/jobs/selftest.d/99-load-state.sh, docs/testing/jobs/roles/lane.md, AGENTS.md, docs/lanes/savestate-req1019/**
Prediction: none: no arm (mechanical feature work with a falsifier fragment, not a pixel/perf claim)
Needs device: yes (one proof run)    Needs NDK: no (mechanism (a): no APK change)

Starting work: investigating `savestate_auto_load` (SettingsActivity.kt, xemu_android.cpp) and how
`request.sh`/`dispatcher.sh` already carry per-run prefs, to build `request.sh --scene <name>` /
`--load-state <slot-or-file>` that loads a named save state on the device without anyone driving the
pause menu by hand. Board request filed (`$DISPATCH_DIR/board-requests/savestate-req1019.md`) for the
files above -- several show as held in territory.toml by rows whose own notes say RELEASED/FOLDED and
that have no live `$DISPATCH_DIR/fleet/*.json` entry; flagged there for the board to resolve, proceeding
on the brief's own Files: line in the meantime. Not claiming `android/app/src/main/cpp/xemu_android.cpp`
yet -- aiming for mechanism (a) (dispatcher-side pref + file swap, no APK change); will re-request only if
that turns out to be insufficient, and will say why first.
