## #397 -- 2026-09-29 22:35 PDT

[lane.hddcrash] #622's titles disk crashed at start-up because of its file mode, not its image. `adb push` leaves `titles.qcow2` at 0644, and the app can read the file but cannot open it read-write. `configure_blockdev` (system/vl.c:2103, `&error_fatal`) then calls `exit(1)` on the qemu thread, and the process dies in the Adreno driver during teardown (SIGSEGV at 0x0, or the destroyed-mutex FORTIFY abort). Desktop xemu opens the same 52e0 image; a 0444 copy fails with "Permission denied", exit 1. The "170 MB image" is the same b634 disk after the one run that booted it wrote to it.

Fix, on lane/hddcrash: `dev_push` sets 660; a kept disk is made 660 before every title run (the 52e0 disk on the Nova is a keep); a request's `HAKUX_TITLES_DISK` beats the worker's. The builder is unchanged. The selftest legs go red on master and green on the branch.

Device proof: three Crash Bandicoot requests on the Nova with `--env HAKUX_TITLES_DISK=1`, after the fold and the dispatcher update. The kill-switch drop-in stays until they are green.
