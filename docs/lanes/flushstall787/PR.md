flushstall787: time translation, TLB refill and flush work per window, to answer "is the guest-late stall the flush?" (#787)

State: draft

Lane: flushstall787     Issue: #787
Base: master @ 5d5d2c51a5
Files: accel/tcg/translate-all.c, accel/tcg/cputlb.c, accel/tcg/cpu-exec.c, docs/lanes/flushstall787/PR.md, docs/lanes/flushstall787/NOTES.md, docs/lanes/flushstall787/OUTBOX.md, docs/lanes/flushstall787/fs_windows.py, docs/lanes/flushstall787/fs_pages.py
Prediction: pending (registered before the one Kabuki run)
Needs device: yes (Nova, one perflog soak)    Needs NDK: yes

Work in progress. Step 1 (instrument) first; no fix before the measurement.
