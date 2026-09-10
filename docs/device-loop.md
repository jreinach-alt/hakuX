# The device loop

Getting a build onto a device and getting evidence back off it.

The measurement side — running the pgraph suite and comparing against hardware
goldens — is [`testing/pgraph-harness.md`](testing/pgraph-harness.md). This is
the general loop: deploy, observe, capture.

## Why this file exists

The loop was real but undocumented, so it lived in three places at once: the
app's own rotating logs, a PowerShell diagnostic puller, and whatever each
session reinvented. One of those reinventions was written, refined across four
commits, and then deleted as redundant (`f26a485`..`b751c7e`) — which is what
happens to tooling nothing points at.

The surviving PowerShell script also targeted the wrong package. It hardcoded
`com.rfandango.haku_x`, the upstream **source namespace**
(`android/app/build.gradle.kts:23`), while this fork installs as
`com.jreinach.hakux` (`:29`). It found no sessions on a device running this
build and said "none found" rather than failing.

## One entry point

```sh
tools/hakux-device.sh status          what is connected, installed, running
tools/hakux-device.sh logs   -o DIR   the app's rotating logs
tools/hakux-device.sh diag   -o DIR   diag_session_* frame captures
tools/hakux-device.sh shot   -o FILE  screenshot the current frame
tools/hakux-device.sh crash           recent hakuX-crash entries
tools/hakux-device.sh all    -o DIR   all of the above
```

`-s SERIAL` picks a device when several are attached; `-p PKG` overrides
package detection. POSIX shell, so it works from WSL, macOS and Linux.

**Run `status` first.** It reports whether `run-as` is available, which decides
whether anything else can work.

## What the device will and will not give you

| you want | how | needs |
|---|---|---|
| The current frame | `shot` — `adb exec-out screencap` | nothing special |
| Crash diagnostics | `crash` — kernel BugCheck dumps tagged `hakuX-crash` | nothing special |
| App logs | `logs` — `run-as` reads app-private storage | **debuggable build** |
| Frame captures | `diag` — `diag_session_*` from app storage | **debuggable build** |
| pgraph results | FTP, not adb — see the harness doc | networking enabled in-app |

`run-as` only works on a debuggable build. On a release build the app's private
storage is unreadable and `logs` and `diag` will say so rather than half-work.

Two device-side gotchas worth knowing before you lose an afternoon:

- **`adb.exe` under WSL emits CRLF.** Unstripped, it corrupts every path built
  from its output. This cost a commit of its own (`f403f78`); the script strips
  it, and anything else you write against adb should too.
- **App-private files cannot be `adb pull`ed directly.** They have to be staged
  through `/data/local/tmp` via `run-as ... cat`. That is what the script does,
  and why a naive `adb pull /data/data/...` fails with a permission error that
  reads like a device problem.

## Frame captures

Trigger in-app: **Debug → Diag: Capture N Frames**, then `diag`. View with
`debug-tools/diag-viewer.html`.

**Single-frame captures only.** Multi-frame capture writes JSON draw-call logs
and surface dumps synchronously on the pfifo render thread, so disk I/O blocks
GPU command processing and the game freezes. See `KNOWN_ISSUES.md`. This is the
project's only per-draw-call observability and it is half-broken; fixing it is
worth more than it looks, because without it a rendering defect can only be
observed as a final framebuffer.

## What is not here

Several scripts referenced by the tracker and by past sessions were never
committed and exist only on the machines that made them:

| script | referenced by |
|---|---|
| `extract_results.py` | issues 3–14, the reproduce block |
| `diff_specimen.py` | #21 |
| `crossmatch.py` | #19 |
| `isorun.sh`, `boottest.sh`, `repro.sh` | #17, #20 |
| `placement_gate.py` | a later #19 session |

If you have any of them on a working machine, committing them is worth more
than most feature work: every one is currently a dead link in an open issue.
See [`investigations/README.md`](investigations/README.md).

## Which build is on the device

```sh
tools/hakux-device.sh status
```

reports the installed version. This fork ships under its own application id
(`0ff650f`) so it installs alongside an official build without touching it —
which also means **both can be installed at once**, and `status` is how you
tell which one you are about to capture from.
