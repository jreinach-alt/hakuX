# Audit pass 1: PR #530, lane/rendermode474 (#474)

Head audited: `f95b6a2729`. I read the whole diff:
`android/app/src/main/cpp/xemu_android.cpp` (`ReadLe32`, `PreadFully`, `ReadDiscTitleId`,
`kTitleRenderModes`, `HasCsvToken`, `ApplyRenderMode` and its call in `SyncSetupFiles`),
`PerGameSettingsManager.kt`, `docs/lanes/rendermode474/{NOTES.md,register_pgraph.py,titleid_test.sh}`
and the six `rendermode474-*.json` predictions.

**Verdict: no HIGH and no MEDIUM findings, four LOWs.** The change sets `TU_DEBUG=sysmem` for
exactly two title IDs read from the disc. The arms show it engages on those two discs and stays
off elsewhere: the one-device pgraph pair PASSES 1059/1059, and the Blinx and pgraph runs log
`auto (default)`.

## Checked, no finding

- **XDVDFS / XBE layout.** The volume descriptor is at sector 32 of the partition. The magic is
  at 0x000 and 0x7EC, the root sector at 0x14 and the root size at 0x18. A directory entry is
  left u16, right u16, sector u32, size u32, attr u8, name_len u8, name; left/right are dword
  offsets from the directory start, and 0xFFFF is padding. In the XBE header, the base address
  is at 0x104 and the certificate address at 0x118, and the title ID is at certificate +8. All of
  these match the code. The partition starts `0x18300000 / 0xFD90000 / 0x2080000` are the
  XGD1/2/3 redump offsets.
- **Bounds on a hostile or corrupt image.** Every read of `dir` is guarded: `off + 14 > root_size`
  comes before the header read, and `off + 14 + name_len <= root_size` before the name compare.
  `off` is at most 0xFFFF*4, so it cannot overflow a u32. The root size is capped at 1 MiB. The
  walk is capped at 4096 visits, so a cyclic tree terminates. Sector offsets are computed in u64
  (`kSector` is `uint64_t`). A pread past EOF returns 0, and `PreadFully` treats that as failure.
  Every failure path returns 0, which means `auto`: the driver's default, i.e. today's behaviour.
- **The fd path.** `pread` does not move the file offset, so reading the `/dev/fdset/0` fd before
  `qemu_init` takes it over leaves QEMU's view unchanged. A non-seekable fd fails the pread and
  falls back to `auto`.
- **Timing of `setenv`.** `ApplyRenderMode` runs in `SyncSetupFiles`, before `qemu_init`, so it
  runs before the renderer creates the Vulkan instance. The device evidence confirms this: DOA
  and AUF B arms go from X/R 1.00 to 0.02, and the line reads `TU_DEBUG=sysmem`.
- **Env persistence across launches.** The emulator runs in `:xemu` (`AndroidManifest.xml`), and
  exit kills the process (`MainActivity.kt:339`). A `TU_DEBUG` set for one title therefore cannot
  leak into the next launch.
- **Precedence.** The `env_vars` pref is applied earlier in the same function
  (`setenv(... , 1)`). A table `sysmem` yields to an env that names `sysmem` or `gmem`. A per-game
  `sysmem` is appended, and Turnip's `TU_DEBUG(SYSMEM)` check comes before its GMEM check, so the
  per-game value wins, as the comment says.
- **Per-game key.** `render_mode` is added to the same key list that `applyRuntimeOverridesToEditor`
  writes and removes. This is the path every other per-game key takes.
- **Title IDs.** They are confirmed on device, not only from the manifest: B's lines read
  `title=54430006` (DOA) and `title=4541000D` (AUF).
- **Host test.** I ran `titleid_test.sh` on this head, and all five synthetic cases print `ok`
  (xiso, redump offset, right-child only, no default.xbe, second magic missing).
- **pgraph prediction.** `ZPass_pixel_count` is a true discriminator: it reads 40960 under GMEM
  and 65536 under sysmem (#527). The one-device verdict supersedes the thor/nova FAIL by the
  arms job's own rule.

## Findings

### LOW-1: a space-separated `TU_DEBUG` hides a user's `gmem` from the table check

Mesa splits `TU_DEBUG` on comma **and** space (`parse_debug_string`, delimiters `", "`).
`HasCsvToken` splits on comma only. Failure scenario: the `env_vars` pref holds
`TU_DEBUG=gmem flushall` and the disc is DOA. `HasCsvToken` sees one token, `gmem flushall`, so
`env_names_mode` is false. The table then appends `,sysmem`, and Turnip runs sysmem, overriding
the mode the user named. The blast radius is two titles and a debug env var written with spaces.
Fix: split on `", "` to match Mesa.

### LOW-2: per-game `gmem` does not force GMEM

The key accepts `gmem` beside `sysmem`, which reads as "force GMEM". In the code it means "skip
the table": nothing is written. With `TU_DEBUG=sysmem` in `env_vars`, a per-game `gmem` still runs
sysmem, and the line logs `render_mode: gmem (per-game) TU_DEBUG=sysmem`. Without the env var,
Turnip's autotuner keeps its per-pass choice. There is no UI for the key yet, so no user can set
it today. Either write `TU_DEBUG` `gmem` (Turnip has the flag) or name the value for what it does,
before a settings control exposes it.

### LOW-3: certificate bound wraps on a corrupt XBE

`cert_addr - base_addr + 12 > xbe_size` is computed in u32. If `cert_addr - base_addr` is
0xFFFFFFF4 or more, the sum wraps to a small number and the check passes. The pread then lands
about 4 GiB past the XBE. That read either fails (0, `auto`) or returns bytes from elsewhere on the
disc. Only a corrupt image reaches this, and it selects sysmem only if those bytes happen to equal
one of two IDs. Fix: compare `cert_addr - base_addr > xbe_size - 12`, or widen the sum to u64.

### LOW-4: DOA's occlusion-query frames are two-thirds unread

DOA issues occlusion queries in three pairs of lines inside the window. Sysmem changes the value
those queries return, from 40960 to 65536 (#527; both are the wrong constant). NOTES reads the
first pair against a GMEM scene and finds no difference. It records the other two as VOID,
because the GMEM arm aborted at 164 s. This is the lane's own stated limit. It is not a defect in
the diff: both constants are non-zero, so a visible/not-visible test decides the same way in
either mode. It is listed so that a DOA visual report goes to #527, not to this change. No action
is required for the fold.

## Not checked

- On-device behaviour beyond the lane's recorded runs. I have no device.
- J/frame. No arm has a `power` field; NOTES says so.
