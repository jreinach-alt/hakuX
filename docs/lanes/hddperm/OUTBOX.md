## #397 -- 2026-10-04 PDT

lane.hddperm: the 0644 pushed-disk crash (titles.qcow2 / hdd.img that xemu
cannot open read-write) is fixed on master by lane.hddcrash's 9b274b6be3.
That fix sets mode 660 on `<path>.new` before the rename and repairs a kept
0644 disk before every title run. lane/hddperm merged master and kept only
its increment: `dev_push` now removes `<path>.new` on any failure before the
rename (master left a stale full-size image on the device), plus push-level
selftest legs for a refused chmod and for a chmod that exits 0 without
taking. In both cases hdd.img's bytes and mode stay unchanged and `.new` is
removed. Gate: 99-hdd-split 72/0 under umask 022 and 002. Falsifier: master's
dispatcher fails exactly the two `.new` legs. The full selftest is recorded
in PR.md.
