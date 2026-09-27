# lane.flip474: Turnip's sysmem render mode (#474, Addenda 7 and 8)

This file is #516's notes. `NOTES.md` belongs to the lane's
earlier PRs and #504 is still editing it, so this PR does not touch it.

## Why the last session did not finish, and this one (resumed 2026-09-27 22:38Z)

The last session ended on a wait, correctly: #504 (the timestamp period)
had every device leg judged and waited on the arms job's pgraph pair
(`1-1790547698-arms-flip474-base-1028880` done on the Thor, `-fix-1029105`
still queued at 22:40Z). Addendum 7 (15:12 PDT) reached that session after
it had started and was not acted on. This session starts Addendum 7 on a new
branch, `lane/flip474-sysmem`, from master `09fdca3ba1`; #504 stays as it is.

## What decides the render mode (read in lane.turnipfork's Mesa tree, `4c18636110`)

That tree is the series the bundled driver ("PurpleVK", Mesa 26.3.0-devel
git-62ac221a33) is built from, not the binary itself.

- `TU_DEBUG` is parsed once, in `tu_env_init` (`tu_util.cc:130-176`, a
  `call_once`), which `tu_CreateInstance` calls (`tu_device.cc:1971`).
- The `sysmem` flag is read in one place: `use_sysmem_rendering`
  (`tu_cmd_buffer.cc:1419`). It picks the render mode and nothing else.
- Without it, the autotuner decides per pass (`tu_autotune.cc`). Its default
  for a pass it cannot tune is SYSMEM (`:1831`, "an incorrect decision
  towards SYSMEM tends to be far less impactful than an incorrect decision
  towards GMEM"). DOA's heavy pass is tuned, and gets GMEM.
- The driver's own driconf already sets `tu_autotune_algorithm=prefer_sysmem`
  for DXVK and vkd3d, "DX games almost always tend to prefer SYSMEM"
  (`00-turnip-defaults.conf:36-40`). It matches on the engine name, and the
  other options on that engine entry change rounding and alpha-to-coverage,
  so borrowing it is not an option.
- `TU_AUTOTUNE_ALGO=prefer_sysmem` is the supported spelling in this tree.
  Whether the bundled binary has it is not known; `TU_DEBUG=sysmem` is the
  one measured on the device (NOTES.md section 16), so that is the one used.

hakuX has one `vkCreateInstance` (`instance.c`, `create_instance`), and the
`env_vars` pref is applied before it (`xemu_android.cpp:796-806`). So a
`setenv` just before the instance is created reaches the driver, and a
`TU_DEBUG` the user or a request set wins.

## Policy

Per title is not open to hakuX: the flag is read once per process, at
instance creation, before a disc is read. Per pass is the autotuner's job,
and it is the thing getting DOA wrong. So the choice is global sysmem or the
driver's default, and the breadth soaks decide it. The change is written for
global sysmem and is only right if no title loses (the KILL legs below).

## Registered before any arm ran

| file | what | arms |
|---|---|---|
| `flip474-sysmem-pgraph.json` | 27 pgraph suites, no env against `TU_DEBUG=sysmem`, ref `09fdca3ba1`, the Nova. Every capture byte-identical (75%) | `1-1790549038-flip474-1817562` (A), `1-1790549039-flip474-1817704` (B) |
| `flip474-sysmem-auf.json` | AUF, X/R 1.01: GPU <= 0.75 x, gfps +2 (55%) | the next two in `.queue_sysmem.log` order: base, sysmem |
| `flip474-sysmem-blinx.json` | Blinx, X/R 0.13: GPU 0.80-1.15 x, no loss | base, sysmem |
| `flip474-sysmem-forza.json` | Forza, X/R 0.25: GPU 0.70-1.10 x, no loss | base, sysmem |
| `flip474-sysmem-crimson.json` | Crimson on the Thor, capped at 30: gfps within 1 | base, sysmem |
| `flip474-sysmemfix-pgraph.json` | the change itself, master `09fdca3ba1` against `1a8f16ef16`, the same 27 suites | the arms job |
| `flip474-sysmemfix-doa.json` | the change on DOA, no env: the `init: TU_DEBUG=sysmem (default` line, X/R <= 0.25 | `1-1790549110-flip474-1833747` |

The ten env requests, in queue order: `1-1790549038-flip474-1817562`,
`1-1790549039-flip474-1817704` (pgraph A, B), `-1817992`, `-1818193` (AUF
base, sysmem), `-1818394`, `-1818597` (Blinx), `-1818830`, `-1819047`
(Forza), `-1819312`, `-1819530` (Crimson, Thor). Each id's prefix is
`1-17905490NN-flip474-`.

The judge scripts (`phaseread.py`, `lockread.py`, `gfpsseries.py`,
`crashcheck.py`, `tailcheck.py`) are in `docs/lanes/flip474/`; the ones not
on master are on #504's branch.

## Results

Not yet run. The change is Android-only (`#ifdef __ANDROID__`), so the
desktop pgraph suites cannot see it; its pixel check is the Nova pair
above and the arms job's pair for `flip474-sysmemfix-pgraph.json`.

## Waiting (from 2026-09-27 22:46Z)

At 22:46Z the Nova was under hostops' battery hold (13%, lifted at 80% on
a 500 mA port, hours), so the Nova requests wait for that.

On the eleven requests above, all outside this session, and the arms job's
pair. When they land: judge each file's legs, post the table on #474 and
#462, and take #516 to ready only if both pgraph pairs are byte-identical
and no breadth soak meets its KILL leg.

## Attempt 2 (resumed 2026-09-27 ~23:00Z)

Attempt 1 did not finish because it ended waiting on the device, which was
the right call. At 22:51Z the arms job then refused `flip474-sysmemfix-pgraph.json`.
Its skip was spelled `Texture render target::RenderTextureLoop`, with spaces,
because it was copied from the env pair. That pair was queued by hand with
spaced suite names. The arms job passes the prediction's underscored suites,
and `request.sh` matches the skip's suite against those literally.
Attempt 2 respells the skip `Texture_render_target::RenderTextureLoop`
(`make_test_iso.py` maps `_` to a space, so the disc is the same). The refs
stay the same and nothing was rebased. The arms job picks up the new sha on its next tick.

At 23:00Z none of the eleven requests had run. The Nova is still under the
battery hold, and the Thor is held for lane.xbox's title push. The wait below still holds.

## Attempt 3 (resumed 2026-09-27 23:03Z)

Attempt 2 did not finish because it ended waiting on the device again, and
that was the right call: none of its eleven requests had started. At 23:05Z
the Nova is running the first one, pgraph A `0-0-x-1790549038-flip474-1817562`
(the host moved the batch to the device head as `0-0-x-`). The other nine env
requests, DOA `1-1790549110-flip474-1833747`, and the arms job's pair for
`flip474-sysmemfix-pgraph.json` (`1-1790549941-arms-flip474-base-2298159`,
`-fix-2298254`) are queued. #516's CI is green on `eb473c8377`, and its
`Files:` line matches the diff.

Side items, and why none are this lane's:
- The texture-bind drain (lane.local's 15:46 addendum) went to its own lane,
  lane.drain474, which holds vk/texture.c (board, hostops 15:48 PDT).
- #504 waits on its fix arm `1-1790547698-arms-flip474-fix-1029105`,
  which is still queued. Hostops marks it ready when the arms job PASSes it.

The wait is the same one: judge the legs when the requests land.

## Do not repeat

- Do not copy a skip spec from a hand-queued request (spaced suite names)
  into a registered prediction (underscored): the arms job's `request.sh`
  gate compares them literally and refuses.

- Do not borrow a driconf engine entry to get one option: DXVK's entry in
  Turnip's defaults also changes texture-coordinate rounding and
  alpha-to-coverage.
