# lane.dispatchguard

## The defect

`selftest.d/50-arms-requeue.sh` and `51-dispatch-hardening.sh` empty
`$DISPATCH_DIR/queue`, `$DISPATCH_DIR/results` and `$HAKUX_WORK/arms/*`
(50: `rm -f queue/*.req` and `clear_markers`; 51: `mv results/*` away and
`rm -rf results/* queue/*.req` twice in part E2), and they run `arms.sh`,
which queues requests into `$DISPATCH_DIR`. They were safe only because
`selftest.sh` exports `DISPATCH_DIR=$T/work/dispatch` and `HAKUX_WORK=$T/work`
under a fresh `mktemp -d` before sourcing any fragment. A one-off script that
sources a fragment directly inherits the caller's exports; in a lane session
those are the live `/home/justin/hakux-work` and its `dispatch/`.

On 2026-09-29 16:23-16:29 PDT the live queue and results were emptied twice,
leaving exactly what line 298 of 51 leaves (dotfiles in results/ and the
`withdrawn/` subdir survive). The lead is a scratch harness in another lane's
worktree that sourced `selftest.d/$FRAGS` with `T` set and `DISPATCH_DIR`
not. This lane did not try to confirm that, nor recover anything; it closes
the gap for any such script.

## The fix

One guard block, identical in both fragments, before any code. It refuses --
message on stderr, `fail` incremented, `return 1` (or `exit 1` when the file
is executed rather than sourced), nothing removed -- unless all of:

1. `DISPATCH_DIR` and `HAKUX_WORK` are exactly `$T/work/dispatch` and
   `$T/work` (realpaths): the layout `selftest.sh` builds, and nothing else;
2. `$T` is strictly below a tmp root (`${TMPDIR:-/tmp}` or `/tmp`) -- the
   positive check, so a production dispatch dir under any other name fails;
3. none of `T`, `HAKUX_WORK`, `DISPATCH_DIR` is inside, equal to, or an
   ancestor of `$HOME/hakux-work`.

51 asks again before part E (the destructive block, 180 lines later), in
case a later edit moves `DISPATCH_DIR` in the main shell. Nothing in the
fragments does today: the two `export DISPATCH_DIR=` lines in 51 are in
`drive.sh` and a `$( ( ... ) )` subshell.

A shared `selftest.d/_dispatch_guard.sh` was not possible: `selftest.sh`
refuses any name under `selftest.d/` that is not `NN-*.sh`, and a helper
elsewhere is outside this lane's files. Instead part J diffs the two copies.

## Proof (51, part J)

Each case sources a fragment in a subshell with a fake `HOME` whose
`hakux-work/` holds a canary request, result and judged marker:

| case | expected | result |
|---|---|---|
| selftest.sh's own tree | guard passes | ok |
| 50, T=mktemp, DISPATCH_DIR=live (the incident) | refused, rc=1, canaries intact | ok |
| 51, same | refused, rc=1, canaries intact | ok |
| scratch-shaped tree at `/dg-not-a-tmp/x` | refused: not below a tmp root | ok |
| scratch-shaped tree below /tmp but = `$HOME/hakux-work` | refused: inside live | ok |
| 50 executed with `bash`, not sourced | exit 1, canaries intact | ok |
| the two guard blocks | byte-identical | ok |
| MUTANT: 50 with the guard deleted, incident shape | canary request removed | ok (J can go red) |

`SELFTEST_ONLY="10-arms-list 20-arms-queue 30-arms-error 40-arms-refusal
50-arms-requeue 51-dispatch-hardening" bash docs/testing/jobs/selftest.sh`:
97 passed, 0 failed. Every pre-existing 50 and 51 leg passes under the guard.

## For the next lane

- `dhmut` must not be used to mutate a file under `jobs/selftest.d/`: its
  tree symlinks `jobs/*` entries, including the `selftest.d` directory, so its
  `rm -f "$dir/$rel"` would delete the real fragment. J builds its mutant with
  a plain `sed` into `$DG`.
- Other fragments (10..40, 55+, ...) also write `$DISPATCH_DIR`. They were out
  of this brief's files; 50 and 51 are the ones with `rm -rf results/*`. A
  fragment that empties the dispatch dir should copy this guard block.
- 51 prints a negative "took" time: it sets `SECONDS=0` itself (lines ~207,
  ~403). Pre-existing, cosmetic, not touched.

## Attempt 2 (2026-10-04): the libfolders pref migration voids old-ref soaks

### Why attempt 1 did not finish this

Attempt 1 was the guard above, folded 09-30 as PR #624. The 10-04 hostops
addendum (lane.local's 14:58 harness item) came after it. This worktree
(`lane/toolsmith`) had no commit on that item, no WAITING file and no NOTES
entry for it, so the session that was handed the addendum ended without
starting it. No branch records why. Attempt 2 started from master @
10f14d301d.

### The defect

`GamesFolders.read()` (libfolders, 10f14d301d) moves `gamesFolderUri` into
the JSON array `gamesFolderUris` and deletes the old key, and every
`write()` deletes it again. A build from an older ref reads only
`gamesFolderUri`, finds nothing, opens the setup wizard, and the soak ends
"guest never appeared in Ns -- title did not boot".

### The fix (dispatcher.sh)

`ensure_legacy_folder_pref`, called in serve_one's soak branch before
`titles_disk_prepare`: force-stop, read `x1box_prefs.xml` through run-as,
and when `gamesFolderUris` has entries and `gamesFolderUri` is absent, add
`gamesFolderUri` = the first entry (JSON- and XML-unescaped: Android writes
`[&quot;content:\/\/...&quot;]`). Then write, and read back the way
`set_hdd_pref` does. Every other byte is kept. A libfolders build ignores
the old key while the array is there, so this does nothing to it.

- Unreadable or empty prefs, no array, an empty array, or an array that is
  not JSON: no write, the soak goes on, and the state is logged.
- A write that does not read back fails the request with an ERROR that names
  it. A run without the key would be the void this prevents, and a
  truncated `cat >` would put every later request into the wizard.
- `result.json` gets `folder_pref`: `added: ...`, `kept: ...` or `unread: ...`.
- Steady state costs two adb calls per soak (force-stop, cat). Disc runs
  make no calls.

### Proof (host only, as the addendum asked)

`selftest.d/99-folder-pref.sh` runs the dispatcher's own functions against a
fake adb that serves one prefs file:

| case | expected | result |
|---|---|---|
| migrated handheld (array, no old key) | old key = first URI; a stdlib XML parse reads it unescaped | ok |
| same | the array still parses to both URIs in order | ok |
| same | the diff is exactly one added line | ok |
| next soak | `kept: no change needed`, no write | ok |
| un-migrated handheld (old key only) | untouched | ok |
| no array / `[]` / not JSON | no write, rc 0 | ok |
| no prefs file | `unread`, no write, rc 0 | ok |
| read-back lost | rc 1 (request fails) | ok |
| serve_one order | ensure, titles_disk_prepare, soak_title.sh | ok |

Falsifier: against master's dispatcher.sh, 13 of 15 legs FAIL, including
"a pre-libfolders build now reads the first folder". The two that pass
there are the ones about what was not written.

### Runs this voided

Taken from the dispatch results dir, 10-03 00:00 to 10-04 14:55 PDT. The
question per run: does the ref's tree contain `GamesFolders.kt`? Fold
ancestry is the wrong test, because lane.libfolders' own branch commits
predate the fold commit.

- The Thor was migrated by lane.libfolders' own soak `1-1791142964`
  (ref dfa6d4c044, 12:43 PDT).
- After that, the Thor ran these pre-libfolders soaks:
  - `1791146938`, `1791146942` (fmv303c, cf328d86f7, 13:50): refused for the
    display cover before boot. These are not this defect.
  - **`1791149862` and `1791149866` (lane.fmv303c, cf328d86f7, 14:43 and
    14:45): "title did not boot". These ARE this defect.** fmv303c's later
    soaks on e2b045168a (a libfolders tree) booted.
- hostops `1-1791149836` (Blinx, 5f6c0268e7) booted, because 5f6c0268e7
  already contains GamesFolders.
- The Nova: no dispatch soak since 10-03 ran a libfolders tree, and none
  failed to boot. It is exposed the first time one does, and this fix covers
  that. An owner or playtest install of master can also migrate either
  handheld outside dispatch. The fix does not care how the pref was migrated.

### For the next lane

- `.debug2` holds its own prefs file. The fix edits `$PKG`'s, the package
  the request installs, so it covers whichever package runs.
- If a later build stops reading the array when the old key is present, this
  fix would pin it to one folder. Today `read()` checks the array first.
