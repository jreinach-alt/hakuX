# lane.glchannel -- connecting the desktop GL channel to the queue

Brief: harness defect, no tracker issue. `lane.desktopchannel` built a working
desktop GL execution channel and folded it (PR #149, `f7be6e68cb`), and it was
connected to nothing: no serve mode, no unit, no `lanes/desktop`, so the only
route onto it -- an explicit `--device desktop`, by `affinity.py`'s OFFPOOL --
led to a request that sat in the queue unclaimed forever with nothing saying
so.

## What was verified before writing anything

Re-checked against the tree at `732b97e2df`, because a brief that asserts an
absence is a claim:

| claim | how it was checked | result |
|---|---|---|
| `desktop_channel.sh` has only `build` and `run` | read the `case` at the foot of the file | true: `deps build smoke run env`, no worker mode |
| no `hakux-desktop` unit | `ls docs/testing/systemd/` | true: arms, board, cloud, dispatcher, fold, nightly, status |
| `affinity.py` has OFFPOOL and it names `desktop` | read `affinity.py:58-88` | true, and the reasoning at `:50-88` is sound; NOT changed |
| `devices.sh` enumerates `desktop` off-pool | `device_offpool_labels()` | true |
| `request.sh --device desktop` passes its gate | `55-affinity-offpool.sh:115-124` already checks it | true |
| the six files are free on `origin/board` | parsed `territory.toml` in memory, exact-match over every `files` list | true -- only `retired.desktopchannel` named three of them and it is retired |

One thing the brief's file list did **not** cover and the defect needs:
`docs/testing/jobs/install-host.sh`. It copies `systemd/*.service` in a loop
and then `enable --now`s a **named list** that did not include this unit. A
unit file that is installed and never started is the same kind of invisible as
no unit at all, which is the whole subject of this lane. That file was
unclaimed on the board; the change to it is one line plus its comment, and it
is declared on the PR's `Files:` line.

## What was built

**1. `desktop_channel.sh serve`** -- the worker. Registers `$DISPATCH_DIR/lanes/desktop`
holding its own pid, re-asserts it every tick, releases only a file that still
holds that pid. That is the handheld protocol exactly, because `affinity.py`'s
`serving()` tests liveness with `kill -0` on that pid and nothing else.

Four deliberate differences from `dispatcher.sh`'s worker, each of which is a
decision rather than an omission:

- **It claims only an explicit desktop pin.** `dispatcher.sh:539` takes a
  request when affinity answers its own label *or answers nothing* -- `""`
  means "free, anyone may take it". This must not. A free request is one
  nobody asked to run on OpenGL/llvmpipe, and serving it here would score an
  Adreno-Vulkan golden against a different renderer, driver and rasteriser:
  the failure with no symptom that OFFPOOL exists to prevent, reintroduced one
  layer below where OFFPOOL can see it. `affinity.py` is still the single
  authority (rule 2 may legitimately answer `desktop` for an arm whose sibling
  ran here, and that is correct); the worker only refuses to read `""` as yes.
- **It scores nothing.** No `score_sweep.py`, no `/home/justin/goldens/results`.
  The result carries `runs: []` and `ab_compare.py` **refuses** it, which is
  the correct outcome and is left exactly as it is. What it does carry is a
  per-capture sha256 per repeat (`repeat_agreement`), which is a
  desktop-against-desktop instrument and the only sound one this channel has.
- **It runs named tests, not suites.** See the limitation below.
- **It does not re-exec itself on a source change.** `dispatcher.sh` re-execs
  a snapshot; it can, because the scripts it depends on are copied wholesale.
  This one resolves `$REPO`, `$DC_TESTING` and its sibling Python tools from
  its own path, so a snapshot outside the repo breaks `ensure_tree`'s
  `git -C "$REPO" worktree add` and the disc builder. Instead **the sha256 of
  the file that actually ran is written into every result** (`worker_sha256`).
  A stale worker is then visible in the artifact rather than silent -- the same
  trade `scorer_sha256` makes in `dispatcher.sh`, where the hash is the fact
  and the git revision is the guess.

**2. `docs/testing/systemd/hakux-desktop.service`**, modelled on
`hakux-dispatcher.service`, with the explicit `Environment=PATH=` including
`/home/justin/.local/bin` **and** the Android SDK's cmake directory (where the
only `ninja` on this host lives). `TimeoutStopSec=600`, because a tick can be
inside a qemu run with `DC_TIMEOUT` 420s plus a disc build, and SIGKILL at the
default 90s leaves a multi-GB `hdd.img` copy and a half-extracted result.

**3. `selftest.d/56-desktop-worker.sh`** -- five invariants, four mutants and a
control, described below.

## The renderer selector, which is why this is more than plumbing

`undersized-pitch-swizzle-layout.json` (lane/cloud-109, registered 04:12Z) has
two arms differing in **nothing but the renderer**, and its `a_ref` is
therefore the prose string `"4129a349e6 with xemu.toml [display] renderer =
OpenGL, [display.quality] surface_scale = 1"` -- which resolves as no git ref,
which is why `$WORK/arms/skipped/` holds two markers for it. Its own text names
the blocker: "request.sh has no renderer selector ... CHEAPEST UNBLOCK, ONE
LINE: a renderer override the dispatcher can set."

`request.sh` is `lane.toolsmith`'s and was not this lane's to touch. It does
not need to be: `request.sh --env KEY=VALUE` already carries an env list
through to the request, so the worker reads **`HAKUX_RENDERER`** out of it
(`OPENGL` | `VULKAN`, default `OPENGL`, anything else **refused** rather than
falling back to a renderer nobody asked for) and hands it to `cmd_run`, which
already verifies the renderer it got against the one it asked for -- that check
is #29 and it cost a whole set of results believed to be Vulkan.

The same prediction's other requirement is now pinned in `cmd_run`'s
`xemu.toml`: `[display.quality] surface_scale = 1`. `surface_download_to_buffer()`
branches three ways for a swizzled download and the third --
`surface_scale_factor != 1` -- is `assert(pitch >= width * bpp)`, which aborts
on the undersized condition that *is* the prediction's subject, and it is
reachable **only from a scaled desktop GL run** (the Android path returns
earlier through the RGBA8 transfer branch). `config_spec.yml:237` defaults it
to 1 today, so writing it changes nothing about what runs now; it stops a
future default change from turning every GL run here into an abort whose cause
is three files away.

**This does not by itself make that prediction runnable** -- see below.

## Limitations, stated rather than discovered later

1. **`only_tests` is required.** `cmd_run` builds a one-test isolation disc
   (`make_isolation_discs.py --build-one`). A request naming only `suites` is
   **refused with an ERROR**, not served with one test and not served with
   none: a desktop result covering 1 capture where 236 were asked for is
   exactly the plausible-wrong-answer shape this tree keeps paying for. The
   next lane's job if a multi-suite desktop disc is wanted is to wire
   `make_test_iso.py` into `cmd_run` the way `dispatcher.sh:871` does -- the
   same `--suite/--skip-test/--only-test/--progress-log/--shutdown-on-completion/--output-dir`
   argument set, against `$DC_BASE_ISO`.
2. **So `undersized-pitch-swizzle-layout.json` is still not queueable**, and
   deleting its skip markers now would only rewrite them. Its disc is eight
   suites, and its `a_ref`/`b_ref` are prose rather than shas. What it needs,
   in order: (a) limitation 1 lifted, or the prediction re-registered with
   `only_tests`; (b) `a_ref`/`b_ref` re-registered as the bare sha `4129a349e6`
   with the renderer moved into `--env HAKUX_RENDERER=...`; (c) the arms-side
   routing patch below. **Do not delete the markers before all three.**
3. **A desktop result is not scored and `ab_compare` refuses it.** That is
   correct and must stay. `ab_compare.py`'s refusal message names "a soak or
   perf request", which will read oddly for a desktop arm; the one-line
   improvement belongs to whoever holds `ab_compare.py` and is written out in
   the PR body rather than applied here.
4. **A fold to `desktop_channel.sh` needs
   `systemctl --user restart hakux-desktop`** to take effect. See the
   no-re-exec decision above; `worker_sha256` in the result is what makes a
   stale worker visible.
5. **Singleton by convention, not by enforcement.** Two `serve` processes
   would both register under one label and the second's claim would overwrite
   the first's pid. They could not double-serve one request -- the claim is an
   atomic rename -- but the lane file would name the wrong process. Following
   the dispatcher's protocol exactly (claim every tick, release only if mine)
   was chosen over a startup refusal because the dispatcher's own history says
   a *permanent* registration failure costs five hours and a transient one
   costs a tick. Worth revisiting only if a second desktop target ever exists.

## The self-test, and what each mutant buys

`selftest.d/56-desktop-worker.sh`. `55-affinity-offpool.sh` next door proves
the *scheduler* never chooses the desktop, against three lane files written by
hand. This fragment is about the *claim* side, against the real `serve`:

| check | what it asserts | mutant that trips it |
|---|---|---|
| A | registers `lanes/desktop` with its **own live pid**; `serving()` and `--serving-pooled` agree; removed on SIGTERM | M2: registration write removed -- observed **while the worker is alive**, because after exit the file is gone either way and a one-tick observation would prove nothing |
| B | with the **real** worker serving, rule 3 sends 0 of 60 unpinned pairs to the desktop, and all 60 did go to a handheld | M4: `OFFPOOL = frozenset()` -- unpinned pairs start landing there |
| C | a `device: desktop` request is claimed: queue emptied, result dir, `request.json`, `DONE`, no stray owner file, and the ERROR text proves *this* worker answered | -- |
| D | an unpinned request is **not** claimed, checked on a second tick with only that request in the queue | M1: claim rule relaxed to `[ -z "$want" ] \|\| [ "$want" = desktop ]`, i.e. the dispatcher's |
| E | `dispatcher.sh`'s **own** `serve_one`, sourced in a subshell, declines a desktop-pinned request and leaves it in the queue | -- |
| -- | `dc_lane_release` only removes a file holding its own pid | M3 + a **control** on the same fixture with the real file, so the mutant shows the *pid check* is what stops the deletion rather than that something was deleted |
| unit | the unit exists, carries `Environment=PATH=` including `~/.local/bin`, starts `serve`, and `install-host.sh` **enables** it | -- |

Three things about the fragment that are load-bearing and easy to undo:

- **Mutants are built in a symlink tree** (`$T/desktopw/mut`), one entry
  replaced. The real `docs/testing` is never written to or renamed.
- **`dwmut` returns nothing if the sed changed nothing**, and the caller calls
  `bad` on that. A pattern that has drifted out of the file produces a
  byte-identical "mutant", the falsification behaves exactly like the real
  code, and the check stays green -- which reads as "enforced" and means "the
  experiment did not happen".
- **The substring assertions are functions called by `check`**, never
  `bash -c '[[ ... ]]'`. A child shell does not inherit the locals, so a
  negative written that way is green against absolutely anything.

**Selftest baseline.** `bash docs/testing/jobs/selftest.sh` on master
(`732b97e2df`, my branch point, before any of my changes) is **RED**:
`516 passed, 10 failed`, all ten in `selftest.d/86-fold-regressed.sh`, which
fails because `fold.sh`'s `prune_branch()` deletes the `lane/foldreg` branch
its fixture reuses. That is `lane.selftest86`'s and is not caused by anything
here.

**With this branch: `544 passed, 10 failed`** -- byte-for-byte the same ten.
516 + 28 = 544, so the 28 new checks are the entire delta and all 28 pass.
`docs/testing/preflight.sh` passes with no flags; the territory gate is green
as it stands.

## What is deliberately NOT done

- `docs/testing/jobs/arms.sh` -- `lane.laneshape`'s, 124 changed lines in
  flight. The routing rule (a prediction whose config names
  `renderer = OpenGL` gets `--device desktop` on **both** arms) is real and
  needed; it is written out as a concrete patch with line numbers in the PR
  body for coordination at fold, and not applied. Two things the next reader
  should not have to rediscover:
  - The patch keys on a **`device` field**, not on a grep of the prose in
    `a_ref`. I drafted the grep form the brief describes and it is the worse of
    the two: the prose it would match is exactly what makes `a_ref`
    unresolvable, so `arms.sh:511` skips that prediction before ever reaching
    the routing code.
  - **Nothing can write that field today.** `ab_compare.py`'s `register()`
    (`:1238`) builds a prediction from a fixed key set with no `--device` or
    `--renderer-a/-b` flag, so the arms.sh patch alone is half a change: its
    other half is three `add_argument` lines and three `exp[...]` assignments
    in `ab_compare.py`, a third lane's file. Applying only the arms half gives
    a rule keyed on a field nothing produces -- inert, and inert in a way that
    reads as done.
- `affinity.py`'s OFFPOOL semantics -- unchanged. `affinity.py` is on the
  `Files:` line because the lane claimed it and read it, not because it
  changed: `git diff` shows no edit to that file.
- `ab_compare.py`'s comparability refusal -- unchanged, and strengthened
  indirectly: a desktop `disc_id` is prefixed `desktop/`, so it can never
  compare equal to a handheld one and check (2) refuses a mixed pair before the
  device check is even reached. The **renderer is deliberately kept out of
  `disc_id`**, on `ab_compare.py`'s own argument about `env`: folding an
  independent variable into the comparability key makes the tool refuse the
  one comparison the feature exists to enable.
- `$WORK/arms/skipped/` markers -- not deleted. See limitation 2.
