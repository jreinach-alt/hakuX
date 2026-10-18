# holdcap1018: an owner-play hold starts a host logcat capture

State: draft

Lane: holdcap1018            Issue: #433
Base: master @ bb1817defc
Files: docs/testing/jobs/hold.sh, docs/testing/jobs/selftest.d/99-ownerplay-capture.sh, docs/lanes/holdcap1018/**
Prediction: none: no arm
Needs device: no    Needs NDK: no

Work in progress. `hold.sh take` for a tag starting `owner-play` will start a
host `adb logcat` capture (as a transient user systemd unit,
`hakux-ownerplay-capture-<label>`) so an owner playthrough is never lost to
the device's ~2-3 minute logcat ring again (10-17 Halo survived by luck; 10-18
Fable's first 30 s did not). `who`/`wait-idle`/`release` gain the matching
capture-aware behaviour; a non-owner-play tag is unaffected.

Step 0 (NOTES.md) is committed. Implementation and selftest fragment next.
