# lane.holdcap1018 -- #433: an owner-play hold starts a host logcat capture

Brief (owner, 2026-10-18 ~07:50 PDT): the Fable launch that same morning (jerky
intro videos, audio skips) was lost because nothing was capturing logcat when
the hold was taken at 07:09. On 10-17 a Halo run survived only by luck (a
capture left over from an unrelated lane run). The fix has to be in
`hold.sh take`/`who`/`wait-idle`/`release` for a tag starting `owner-play`, not
a reminder anyone has to remember to act on.

## Step 0: already read, already tried

| Source | What it says | How it bears on this lane |
|---|---|---|
| `jobs/hold.sh` header + `hold_py` | `take` is `O_CREAT\|O_EXCL` on `hold/<label>`, `.why` written only by the winner; `release` compares the stored tag before removing either file; `wait-idle` gates on the hold existing, the dispatcher having seen it (`lanes/<label>` pid check), and `running/*.owner`. Exit codes used: 0/1/3/4. | New owner-play behaviour has to compose with this state machine, not replace it: capture start/stop hangs off the *existing* take/release success paths, and the new `wait-idle` capture check is a second condition ANDed onto the existing idle gate (brief's new exit 5). |
| `selftest.d/99-hold-take.sh` | Legs (a)-(g8) replay the two incidents (#433's own 09-26 hold-ownership bug, and the 10-01 wait-idle bug) against a scratch `DISPATCH_DIR`; `SELFTEST_HOLD_SH` can point at another copy. None of the existing tags (`hostupd-100`, `lane.perfregimen`, `racer1..8`, `lane.holdtake`, `lane.titleroutes`, `other`) start `owner-play`, so none of them will touch the new code path -- satisfies "do not change what a hold does for a non-owner-play tag" (req. 7) for free, so long as the new logic is gated strictly behind the tag prefix check. | Confirms the new work is additive and the existing 99 fragment's legs double as the regression check for req. 7; no edit needed there. |
| `selftest.d/79-stop-hook-hold.sh` | The Stop hook (`stop-emulator.sh`) already treats ANY hold on a label (other than one whose `.why` says "battery") as "leave it running" -- it never force-stops or sleeps a held device. It resolves label<->serial via a subshell that sources `devices.sh` and calls `device_env <serial>`, exactly the direction (serial->label) `device_env` supports natively. | This lane needs the OPPOSITE direction (label->serial, to find which serial `nova`/`thor` is before invoking adb). `devices.sh` has no such helper; the existing scripts that need it (this hook, `dispatcher.sh`) all iterate `adb devices` and call `device_env` per attached serial, comparing `$DEVICE_LABEL`. Lifted that exact pattern rather than inventing a new one. |
| `dispatcher.sh` `LOGCAT_SPEC` (line ~3156) | Set from `LOGCAT_SPEC_OVERRIDE` (not `LOGCAT_SPEC` itself -- the file has a whole section on why re-exporting the same name would make an edit here invisible to a running fleet) immediately before the `case "${1:-status}"` dispatch; the `*)` fallthrough just prints a usage excerpt and returns. `selftest.d/51-dispatch-hardening.sh:440` already sources the whole file with a bogus subcommand (`SERIAL=ee317437 DISPATCH_DIR=... . dispatcher.sh selftest-not-a-subcommand`) purely to read `$LOGCAT_SPEC` back out, side-effecting only `mkdir -p "$D"/{queue,running,results,logs}`. No lighter-weight "print the spec" subcommand exists. | Reused the same sourcing trick in `hold.sh` (one source, not a copied literal) rather than adding a new dispatcher.sh subcommand, which the brief's "no emulator/dispatcher code" file list would have made awkward to review anyway (hold.sh is not in that exclusion, `dispatcher.sh` is not in this lane's `Files:` list). |
| `lane.sh` (`systemd-run --user --unit "hakux-lane-$name" --collect --setenv=... bash -c "..."`) | The existing convention for a long-running job that must outlive the shell that started it. | Copied the shape (`--unit`, `--collect`, `--setenv=`, `bash -c '<script>'`) for `hakux-ownerplay-capture-<label>`. |
| `selftest.sh` header + body (`$T/bin/systemctl`, `$T/bin/systemd-run`, `$T/bin/adb`) | The harness's GLOBAL shims are inert for this lane's purpose: `systemctl *is-active*` unconditionally prints `active` for ANY unit name (even one never started), and the global `systemd-run` only **logs** its argv and exits 0 -- it never actually runs the given command. The global `adb` ignores its arguments and always prints the two-device list. | Two consequences, both load-bearing: (1) `hold.sh` cannot use `systemctl is-active` to decide whether a capture is already running -- the global shim would say "active" for a label that was never held, so detection has to be by a PID this lane's own code wrote and can verify (`/proc/<pid>/cmdline` contains `logcat`, the same idiom `hold_py idle`'s `lanes/<label>` check already uses for "is this really still that process"). (2) the new selftest fragment cannot rely on the global `systemd-run`/`adb` shims to exercise the capture-start path at all (nothing would ever actually run) -- it needs its own local shims on a prepended `PATH`, the same way `79-stop-hook-hold.sh` already does with its own local `adb`. |

Stop rule read and accepted: the same failure twice for one cause means stop
and report rather than attempt a third variant.

## Design landed on

- Detection of "is a capture already running for `<label>`" is by a pidfile
  this lane writes (`$DISPATCH_DIR/hold/<label>.capture.pid`, holding the
  capture loop's own `$$`) plus `/proc/<pid>/cmdline` containing `logcat` --
  never by asking systemd, because the harness's own global shim answers
  `active` unconditionally and a real systemd could answer confidently wrong
  after a crash too. `systemctl --user stop` is still called on release, as a
  no-op-if-absent courtesy to a real systemd in production; the pidfile kill
  is what actually guarantees the stop, in both production and under test.
- The capture's own command is a small restart loop (`trap ... TERM;
  while :; do adb ... logcat ... & wait; sleep 2; done`), the same shape
  `99-hold-take.sh`'s own `dispatcher.sh` test fixture already uses for "a
  backgrounded process that dies cleanly on SIGTERM" -- reused rather than
  invented.
- Label -> serial resolution lives in `hold.sh` itself (`label_serial`),
  copying `stop-emulator.sh`'s `device_label_lease` shape (iterate
  `adb devices`, `device_env` each, compare `$DEVICE_LABEL`) rather than
  adding a reverse lookup to `devices.sh`, which is outside this lane's
  `Files:` list.
