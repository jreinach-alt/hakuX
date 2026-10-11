#!/usr/bin/env python3
"""Write the call-site patches under docs/lanes/dispatchgate1006/patches/ as unified
diffs against the files they change (this lane may not edit them; their owners
apply the patch). Re-run against a newer base to regenerate:

    python3 docs/lanes/dispatchgate1006/tools/make_patches.py [--pathfind-tree W/wt/pathfind]

Each edit is an exact-string replacement; a base that has moved under one fails
loudly here rather than producing a patch that does not apply.
"""
import argparse
import difflib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.join(HERE, "..", "patches")


def edit(path, reps):
    src = open(path).read()
    new = src
    for a, b in reps:
        if a not in new:
            sys.exit("make_patches: %s: anchor not found:\n%s" % (path, a[:200]))
        new = new.replace(a, b, 1)
    return src, new


def write_patch(name, rel, src, new):
    d = difflib.unified_diff(src.splitlines(True), new.splitlines(True), "a/" + rel, "b/" + rel, n=3)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        f.writelines(d)
    print("wrote patches/%s" % name)


REQUEST = [
    ('''while [ $# -gt 0 ]; do
    case "$1" in
        --who) WHO="$2"; shift 2;;''',
     '''GATE_ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --who) WHO="$2"; shift 2;;'''),
    ('''        --priority) PRIORITY="$2"; shift 2;;
        *) echo "unknown option $1" >&2; exit 2;;''',
     '''        --priority) PRIORITY="$2"; shift 2;;
        # THE DISPATCH GATE (docs/testing/dispatch_gate.py, owner order 2026-10-06
        # ~16:50): what a title run is FOR and the records it rests on. Passed to
        # `dispatch_gate.py admit-request` below; see that file for the classes.
        --gate-class) GATE_ARGS+=(--class "$2"); shift 2;;
        --gate-because) GATE_ARGS+=(--because "$2"); shift 2;;
        --gate-input-seq) GATE_ARGS+=(--input-seq "$2"); shift 2;;
        --gate-valid-end) GATE_ARGS+=(--valid-end "$2"); shift 2;;
        --gate-order) GATE_ARGS+=(--order "$2"); shift 2;;
        --gate-plan) GATE_ARGS+=(--plan "$2"); shift 2;;
        --gate-declare) GATE_ARGS+=(--declare "$2"); shift 2;;
        *) echo "unknown option $1" >&2; exit 2;;'''),
    ('''mv "$D/queue/.$ID.req.tmp" "$D/queue/$ID.req"
echo "queued $ID"''',
     '''# THE DISPATCH GATE. A title run reaches a handheld only through admit():
# the title's registry row (pm/title-registry.tsv), its class, its evidence and
# the run-level checks. Every decision is a row of pm/dispatch-log.tsv. In
# SHADOW mode (pm/dispatch-gate.mode absent or not `enforce`) it refuses
# nothing and logs what it would have refused; in ENFORCE mode a deny, or a
# gate that cannot run, refuses the queue (fail closed). A disc request has no
# title and is not gated here.
if [ -n "$TITLE" ]; then
    GATE_PY="$(dirname "$0")/dispatch_gate.py"
    GATE_ROOT="$(dirname "$D")"
    if ! python3 "$GATE_PY" admit-request "$D/queue/.$ID.req.tmp" --root "$GATE_ROOT" --caller "$WHO" \\
            ${GATE_ARGS[@]+"${GATE_ARGS[@]}"}; then
        if [ ! -f "$GATE_PY" ] \\
                || [ "$(python3 "$GATE_PY" mode --root "$GATE_ROOT" 2>/dev/null)" = enforce ]; then
            rm -f "$D/queue/.$ID.req.tmp"
            echo "refusing to queue: the dispatch gate refused this title run (reasons above; pm/dispatch-log.tsv)" >&2
            exit 2
        fi
        echo "dispatch gate: failed in shadow mode; queued anyway (shadow refuses nothing)" >&2
    fi
fi
mv "$D/queue/.$ID.req.tmp" "$D/queue/$ID.req"
echo "queued $ID"'''),
]

HOLD = [
    ('''    take)
        [ $# -ge 4 ] || usage
        valid tag "$3"
        hold_py take "$label" "$3" "${*:4}" || exit $?''',
     '''    take)
        [ $# -ge 4 ] || usage
        valid tag "$3"
        gate_check "$label" "$3" "${*:4}" || exit 3
        hold_py take "$label" "$3" "${*:4}" || exit $?'''),
    ('''        deadline=$(( $(date +%s) + $4 ))
        while :; do
            hold_py take "$label" "$3" "${*:5}" 2>/dev/null && { notice_idle; exit 0; }''',
     '''        deadline=$(( $(date +%s) + $4 ))
        gate_check "$label" "$3" "${*:5}" || exit 3
        while :; do
            hold_py take "$label" "$3" "${*:5}" 2>/dev/null && { notice_idle; exit 0; }'''),
    ('''[ $# -ge 2 ] || usage
op=$1 label=$2''',
     '''# THE DISPATCH GATE (docs/testing/dispatch_gate.py hold-check). A direct hold
# that runs a title is a dispatch: it must carry an unexpired ALLOW token from
# `dispatch_gate.py admit --via hold` for this device, issued to this tag (or
# with the token in <why>), for the title id <why> names. SHADOW mode (the
# default; pm/dispatch-gate.mode != enforce) logs an ungated hold to
# pm/dispatch-log.tsv and refuses nothing. ENFORCE refuses it (exit 3), except
# the non-dispatch holds the gate exempts (host update window, charging, the
# Thor's fan-wait park, the owner's playtest). In shadow a gate that cannot
# run refuses nothing either: pathfind's holds must never be refused by it.
gate_check() {   # <label> <tag> <why> ; 0 = take may proceed
    local gate root
    gate="$(dirname "$0")/../dispatch_gate.py"
    root="$(dirname "$D")"
    [ -f "$gate" ] || return 0
    python3 "$gate" hold-check --root "$root" --device "$1" --tag "$2" --why "$3" && return 0
    [ "$(python3 "$gate" mode --root "$root" 2>/dev/null)" = enforce ] && return 1
    return 0
}

[ $# -ge 2 ] || usage
op=$1 label=$2'''),
]

PATHFIND = [
    ('''def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\\n")[0])
    ap.add_argument("title")''',
     '''GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dispatch_gate.py")


def dispatch_gate(tid, name, dev_label, a, dry_run=False):
    """THE DISPATCH GATE (docs/testing/dispatch_gate.py, owner order 2026-10-06 ~16:50):
    pathfind's title intake. admit() with --via hold, the run's class and evidence, the
    title's own recorded path (or `discovery` for a first run) and the installed APK read
    back off the device. Returns (ok, lines). In SHADOW mode (the default) it is never
    False: it prints what it would have refused and the run goes on."""
    if dry_run:
        return True, ["dispatch gate: dry run (PATHFIND_DRY), not asked"]   # never logs a simulated run
    if not os.path.isfile(GATE):
        return True, ["dispatch gate: %s missing; not gated" % GATE]
    own = os.path.join(KNOW, "paths", "%s.json" % tid.upper()) if tid else ""
    seq = "discovery"
    if own and os.path.isfile(own):
        import hashlib
        seq = "path:%s@%s" % (tid, hashlib.sha256(open(own, "rb").read()).hexdigest()[:12])
    cmd = ["python3", GATE, "admit", "--title", tid or name, "--device", dev_label, "--via", "hold",
           "--caller", a.gate_caller, "--class", a.dispatch_class or "", "--build", a.build or "",
           "--input-seq", seq, "--valid-end", a.valid_end, "--seconds", str(int(a.hold_s or 0) + int(a.budget_min * 60))]
    for b in a.because or []:
        cmd += ["--because", b]
    if a.order:
        cmd += ["--order", a.order]
    cmd.append("--readback")
    out = subprocess.run(cmd, capture_output=True, text=True)
    lines = (out.stdout + out.stderr).strip().splitlines()
    return out.returncode == 0, lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\\n")[0])
    ap.add_argument("title")'''),
    ('''    ap.add_argument("--sim", help="PATHFIND_DRY: frames dir to play back")''',
     '''    # THE DISPATCH GATE: what this run is FOR (dispatch_gate.py's classes) and its evidence ids.
    ap.add_argument("--dispatch-class", choices=("PLAYABLE_ATTEMPT", "SCREEN", "TELEMETRY", "VALIDATION",
                                                 "OWNER_DIAGNOSTIC"))
    ap.add_argument("--because", action="append",
                    help="evidence id: verdict:<path> fix:<sha> issue:#N order:<id> plan:<file>#<row> condition:<text>")
    ap.add_argument("--build", help="the build lane.local installed for this run (a commit); read back against the device")
    ap.add_argument("--order", help="an owner order id in pm/owner-holds.tsv (OWNER_DIAGNOSTIC)")
    ap.add_argument("--valid-end", default="valid-verdict",
                    help="valid-verdict | capture:<N>s | condition:<text>: the run ends only on a valid result")
    ap.add_argument("--gate-caller", default="lane.pathfind", help="the hold tag the gate's token is issued to")
    ap.add_argument("--sim", help="PATHFIND_DRY: frames dir to play back")'''),
    ('''    tid, name, iso = resolve(dev, a.title)
    why = blocked(tid, name)''',
     '''    tid, name, iso = resolve(dev, a.title)
    ok, lines = dispatch_gate(tid, name, dev.label, a, dry_run=dry())
    for line in lines:
        print("pathfind: " + line, flush=True)
    if not ok:
        sys.exit("pathfind: the dispatch gate refused %s (%s); see pm/dispatch-log.tsv" % (name, tid))
    why = blocked(tid, name)'''),
]

PATHFIND_SELFTEST = [
    ('''print("pathfind_selftest: " + ("FAIL " + ", ".join(sorted(set(fails))) if fails else "all ok"))''',
     '''# the dispatch gate at pathfind's intake (dispatchgate1006): it asks admit() with --via hold, its own path or
# `discovery`, and never reads back the device on a dry run; a deny stops main() only when the gate says so
# (exit != 0, i.e. enforce mode), a shadow deny prints and goes on.
_calls = []
_real_run = pathfind.subprocess.run


def _fake_gate(rc, text):
    def run(cmd, **kw):
        _calls.append(cmd)
        return types.SimpleNamespace(returncode=rc, stdout=text, stderr="")
    return run


_ga = types.SimpleNamespace(gate_caller="lane.pathfind", dispatch_class="PLAYABLE_ATTEMPT", build="6cef37f426",
                            valid_end="valid-verdict", hold_s=600, budget_min=15, because=["fix:ab8788c38b"], order=None)
pathfind.subprocess.run = _fake_gate(0, "SHADOW-DENY 54430001 PLAYABLE_ATTEMPT on nova\\n  - matrix: below the bar")
_ok_sh, _lines_sh = pathfind.dispatch_gate("54430001", "Dead or Alive 3", "nova", _ga)
pathfind.subprocess.run = _fake_gate(2, "DENY 54430001 PLAYABLE_ATTEMPT on nova\\n  - matrix: below the bar")
_ok_en, _lines_en = pathfind.dispatch_gate("54430001", "Dead or Alive 3", "nova", _ga)
_n = len(_calls)
_ok_dry, _ = pathfind.dispatch_gate("54430001", "Dead or Alive 3", "nova", _ga, dry_run=True)
pathfind.subprocess.run = _real_run
_c = _calls[0] if _calls else []
check("dispatchgate", _ok_sh and not _ok_en and "--via" in _c and _c[_c.index("--via") + 1] == "hold"
      and "--readback" in _c and _c[_c.index("--class") + 1] == "PLAYABLE_ATTEMPT"
      and any(x.startswith("path:") or x == "discovery" for x in _c) and _ok_dry and len(_calls) == _n,
      "shadow deny goes on, enforce deny stops; --via hold, the class, an input sequence, the APK read back; "
      "a dry run never asks the gate (it would log a simulated run)")

print("pathfind_selftest: " + ("FAIL " + ", ".join(sorted(set(fails))) if fails else "all ok"))'''),
]

VERDICT = [
    ('''    v["pass"] = not fails
    v["failing"] = fails[0] if fails else None
    v["failures"] = fails''',
     '''    v["pass"] = not fails
    v["failing"] = fails[0] if fails else None
    v["failures"] = fails
    # EVERY failed gate by name (dispatchgate1006, owner order 2026-10-06 ~16:50).
    # `failing` is the FIRST only: DOA3's read "menu time" and hid its fps miss
    # (fps_ok_share 0.4394) from a plan that copied it. A reader that decides on
    # a verdict reads this list, never `failing`.
    v["failing_all"] = [re.split(r"[:(]", f, 1)[0].strip().replace(" ", "_") for f in fails]
    v.setdefault("fps_ok_share", None)   # always present: None = no perf line inside play'''),
]


HOURLY = [
    ('''  echo "--- harness_health (restored 10-03''',
     '''  echo "--- DISPATCH GATE (dispatch_audit.py, last 24 h: ungated title runs, refusals, Nova min on flagged titles)"
  timeout 120 python3 $R/docs/testing/dispatch_audit.py --hours 24 --max-lines 12 2>&1 | cut -c1-240 \\
      || echo "  dispatch_audit.py unavailable (lane dispatchgate1006 not folded, or it failed)"
  echo "--- harness_health (restored 10-03'''),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pathfind-tree", default="/home/justin/hakux-work/wt/pathfind")
    ap.add_argument("--host-tools", default="/home/justin/hakux-work/host-tools")
    a = ap.parse_args()
    src, new = edit(os.path.join(a.host_tools, "hourly_report.sh"), HOURLY)
    write_patch("hourly_report.sh.patch", "host-tools/hourly_report.sh", src, new)
    for name, rel, reps, root in (("request.sh.patch", "docs/testing/request.sh", REQUEST, REPO),
                                  ("hold.sh.patch", "docs/testing/jobs/hold.sh", HOLD, REPO),
                                  ("title_verdict.py.patch", "docs/testing/title_verdict.py", VERDICT, REPO),
                                  ("pathfind.py.patch", "docs/testing/titles/pathfind.py", PATHFIND, a.pathfind_tree),
                                  ("pathfind_selftest.py.patch", "docs/testing/titles/pathfind_selftest.py",
                                   PATHFIND_SELFTEST, a.pathfind_tree)):
        src, new = edit(os.path.join(root, rel), reps)
        write_patch(name, rel, src, new)


if __name__ == "__main__":
    main()
