# lane.blendrace50 -- #50 full-disc run-to-run instability

Brief: get an honest run-to-run measurement on the FULL 1,673-capture disc,
per capture, and say which captures actually race (vary run-to-run on the
SAME disc) versus which only vary BETWEEN disc compositions.

## Starting state (read before doing anything)

`nv2a_issues.toml` issue.50 carries `blocker_tested = "REFUTED"`, on the
grounds that three full-disc runs already exist "at ONE apk_sha
(b0cba34acef7) and ONE disc_id (iso:85b525/Blend tests)", and
`fulldisc_instability_50.py` reports 5 of 1,673 captures differ across them,
with the shape "4 of the 5 outliers are the SAME RUN (blendstack-A), the
fifth is run B -- instability is RUN-SCOPED, not per-capture."

## Finding 1: those three runs are not three runs of one thing

`result.json` for each:

| run | requester | device_label | device_serial | apk_sha | disc_id | scorer_rev |
|---|---|---|---|---|---|---|
| 1789318910-blendstack-A-63953 | blendstack-A | **nova** | ee317437 | b0cba34acef7 | iso:85b525/Blend tests | *(absent)* |
| 1789318915-blendstack-B-64031 | blendstack-B | **thor** | bdc158a5 | b0cba34acef7 | iso:85b525/Blend tests | 4a6a98dce4 |
| 1789326864-blendstack-thor2-889257 | blendstack-thor2 | **thor** | bdc158a5 | b0cba34acef7 | iso:85b525/Blend tests | 027fa3d552 |

`fulldisc_instability_50.py` asserts equality of `(apk_sha, disc_id)` and
refuses to summarise otherwise -- a real control, and it holds. But it does
not read `device_serial`, and the three runs span **two devices**. A is the
only nova run. So "4 of the 5 outliers are the same run, A" and "4 of the 5
outliers are the only nova run" are the same statement in that data: the
run-scoped shape is not separable from a nova-vs-thor device difference.

That is the same error class the entry already withdrew a rate for -- pooling
runs that differ in a variable nothing in the comparison names.

`scorer_rev` also differs across all three (absent / 4a6a98dce4 / 027fa3d552),
a second uncontrolled variable on the same axis.

The only same-device pair in the existing data is B vs thor2 (both thor), so
the honest existing sample for "run-to-run on one device, one binary, one
disc" is n=2, not n=3.

(continued below as runs land)
