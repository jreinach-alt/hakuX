#!/usr/bin/env python3
"""Measure which pgraph tests depend on what ran before them (issue #15).

A test can pass in one sweep and fail in the next with no code change, because
the suite does not reset all pgraph state between tests. That makes a sweep
diff untrustworthy in both directions -- it invents regressions and it hides
them -- which is why issue #15 blocks using the suite as a gate.

"Some tests are order-dependent" is not a number. This turns it into one, on
the desktop lane rather than a device. Order-dependence is a property of what
the emulator resets between draws, so it reproduces on any renderer even though
the absolute pixels do not match the Nova -- unlike an accuracy question, which
this lane cannot settle. A run costs about 17 seconds.

Two modes:

    order_dependence.py --suite "Pixel shader" ...
        Run the suite whole, then each of its tests alone. Answers: does this
        suite contaminate itself?

    order_dependence.py --target "Pixel shader::Passthru" ...
        Run the target alone, then once behind each other suite. Answers: which
        suite contaminates this test? Exhaustive rather than a bisect, because
        there is no reason to assume a single culprit.

Every run is checked against its own progress log before its captures are
compared. A disc that ran a different set of tests than was asked for is
answering a different question, and the mistake is invisible in the images: an
early version of this script compared eight captures believing they were one,
and looked perfectly healthy doing it.
"""

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TOML = """[general]
show_welcome = false

[display]
renderer = '{renderer}'

[sys.files]
bootrom_path = '{bootrom}'
flashrom_path = '{flashrom}'
eeprom_path = '{eeprom}'
hdd_path = '{hdd}'
dvd_path = '{dvd}'
"""


def roster(goldens, sample_config=None):
    """Suite name -> its test names, for the suites that must be split up.

    Only a suite being *isolated* needs this: a suite the config marks
    unskipped with no test entries runs in full, so a predecessor needs no
    roster at all. That matters, because no roster here is authoritative --
    the goldens were captured from a build of the test suite that named some
    tests differently (`2DLine-15-...` where this disc runs
    `2DLine-R5G5B5-...`). Suite display names are directory names with
    underscores turned into spaces, which is a guess.

    Nothing downstream trusts any of that. Every run is checked against its
    progress log, so a stale name or a wrong suite runs the wrong set and is
    reported as a failure instead of a result.
    """
    out = {}
    results = Path(goldens) / "results"
    if not results.is_dir():
        raise SystemExit(f"{results} does not exist; --goldens wants an "
                         f"nxdk_pgraph_tests_golden_results checkout")
    for d in sorted(results.iterdir()):
        if d.is_dir():
            tests = sorted(p.stem for p in d.glob("*.png"))
            if tests:
                out[d.name.replace("_", " ")] = tests
    if sample_config:
        data = json.loads(Path(sample_config).read_text())
        for suite, block in data.get("test_suites", {}).items():
            named = sorted(k for k, v in block.items() if isinstance(v, dict))
            out[suite] = sorted(set(out.get(suite, [])) | set(named))
    return out


def started(log_text):
    """Suite -> set of test names the progress log says actually started."""
    out = {}
    for line in log_text.splitlines():
        if not line.startswith("Starting ["):
            continue
        name = line.split("] ", 1)[1].strip()
        suite, _, test = name.partition("::")
        out.setdefault(suite, set()).add(test)
    return out


class Lane:
    """One desktop emulator, driven a run at a time."""

    def __init__(self, args, all_tests):
        self.a = args
        self.all_tests = all_tests
        self.why = None          # why the last run could not be trusted
        self.work = Path(args.work)
        self.work.mkdir(parents=True, exist_ok=True)
        self.settings = json.loads(Path(args.settings).read_text())["settings"]

    def _config(self, tag, whole, isolate):
        s = copy.deepcopy(self.settings)
        s["enable_progress_log"] = True
        s["skip_tests_by_default"] = True
        # Forward slashes. A backslash is written into the guest path
        # literally, and the run then produces nothing without complaining.
        s["output_directory_path"] = f"e:/{tag}"
        suites = {}
        for suite in whole:
            # No test entries: the whole suite runs.
            suites[suite] = {"skipped": False}
        for suite, tests in isolate.items():
            if suite not in self.all_tests:
                raise SystemExit(f"no roster for {suite!r}, so its other tests "
                                 f"cannot be skipped")
            block = {"skipped": False}
            for name in self.all_tests[suite]:
                block[name] = {"skipped": name not in tests}
            suites[suite] = block
        return {"settings": s, "test_suites": suites}

    def run(self, tag, whole=(), isolate=None):
        """Returns {capture: md5}, or None if the run cannot be trusted."""
        self.why = None
        whole, isolate = set(whole), dict(isolate or {})
        cfg = self.work / f"cfg_{tag}.json"
        cfg.write_text(json.dumps(self._config(tag, whole, isolate), indent=2))
        iso = self.work / f"iso_{tag}.iso"
        subprocess.run(["python3", str(self.a.make_iso), self.a.base_iso,
                        "-o", str(iso), "--config", str(cfg)],
                       check=True, capture_output=True)

        hdd = self.work / f"hdd_{tag}.qcow2"
        shutil.copy(self.a.pristine, hdd)
        Path(self.a.xemu_toml).write_text(TOML.format(
            renderer=self.a.renderer, bootrom=self.a.bootrom,
            flashrom=self.a.flashrom, eeprom=self.a.eeprom, hdd=hdd, dvd=iso))

        log = self.work / f"run_{tag}.log"
        with open(log, "wb") as fh:
            rc = subprocess.run(
                ["xvfb-run", "-a", "--server-args=-screen 0 640x480x24",
                 "timeout", "-k", "5", str(self.a.timeout),
                 str(self.a.emulator), "-machine", "xbox", "-display", "none"],
                stdout=fh, stderr=subprocess.STDOUT,
                env={**os.environ, "SDL_AUDIODRIVER": "dummy"},
                cwd=str(Path(self.a.emulator).parent)).returncode
        if rc != 0:
            self.why = f"emulator exited {rc}"
            return None

        out = self.work / f"out_{tag}"
        shutil.rmtree(out, ignore_errors=True)
        subprocess.run(["python3", str(self.a.extract), str(hdd),
                        "-o", str(out), "-d", tag], check=True,
                       capture_output=True)
        progress = out / "pgraph_progress_log.txt"
        if not progress.exists():
            self.why = "no progress log; nothing ran, or nothing was written"
            return None

        ran = started(progress.read_text())
        for suite, tests in isolate.items():
            if ran.get(suite, set()) != set(tests):
                self.why = (f"{suite}: ran {sorted(ran.get(suite, []))[:3]}, "
                            f"asked for {sorted(tests)[:3]}")
                return None
        for suite in whole:
            if not ran.get(suite):
                self.why = f"{suite}: nothing ran; is that the XBE's name for it?"
                return None
        unexpected = set(ran) - whole - set(isolate)
        if unexpected:
            self.why = f"unasked-for suites ran: {sorted(unexpected)[:3]}"
            return None
        return {p.name: hashlib.md5(p.read_bytes()).hexdigest()
                for p in sorted(out.glob("*.png"))}


def compare(reference, other):
    """Verdict for one test, given its isolated captures and another run.

    A test does not always write one capture named after itself -- some add a
    suffix, `MaskOff_ZB` for the zeta buffer. Rather than predict the names,
    take them from the isolated run, where every capture present belongs to
    the test that ran, and look those up in the other run.
    """
    if reference is None or other is None:
        return "RUN FAILED", True
    if not reference:
        return "NO CAPTURE", True
    if any(n not in other for n in reference):
        return "MISSING IN THE OTHER RUN", True
    if all(reference[n] == other[n] for n in reference):
        return "stable", False
    return "ORDER-DEPENDENT", False


def mode_suite(lane, suite):
    tests = lane.all_tests[suite]
    print(f"# {suite}: whole suite, then {len(tests)} solo runs", flush=True)
    whole = lane.run("whole", whole={suite})
    if whole is None:
        sys.exit(f"the whole-suite run of {suite!r} is unusable: {lane.why}")
    print(f"  {len(whole)} captures from the suite run", flush=True)

    dependent, broken = [], []
    for t in tests:
        tag = "solo_" + "".join(c for c in t.lower() if c.isalnum())[:40]
        solo = lane.run(tag, isolate={suite: {t}})
        verdict, failed = compare(solo, whole)
        if failed:
            broken.append(t)
            verdict += f" -- {lane.why}" if lane.why else ""
        elif verdict == "ORDER-DEPENDENT":
            dependent.append(t)
        print(f"  {t:38s} {verdict}", flush=True)

    print(f"\n{len(dependent)} of {len(tests) - len(broken)} measured tests in "
          f"{suite!r} differ between solo and in-suite", flush=True)
    if broken:
        print(f"  {len(broken)} not measured: {', '.join(broken)}", flush=True)
    return dependent


def mode_target(lane, target):
    suite, test = target.split("::", 1)
    others = [s for s in sorted(lane.all_tests) if s != suite]
    print(f"# {target}: alone, then once behind each of {len(others)} "
          f"other suites", flush=True)

    alone = lane.run("alone", isolate={suite: {test}})
    if not alone:
        sys.exit(f"{target} produced nothing usable on its own: {lane.why}")
    print("  alone: " + ", ".join(f"{n}={d[:8]}" for n, d in alone.items()),
          flush=True)

    hits, failed = [], []
    for other in others:
        tag = "pre_" + "".join(c for c in other.lower() if c.isalnum())[:40]
        got = lane.run(tag, whole={other}, isolate={suite: {test}})
        verdict, broken = compare(alone, got)
        if broken:
            failed.append(other)
            verdict += f" -- {lane.why}" if lane.why else ""
        elif verdict == "ORDER-DEPENDENT":
            hits.append(other)
        print(f"  {other:38s} {verdict}", flush=True)

    print(f"\n{len(hits)} of {len(others) - len(failed)} scanned suites change "
          f"{target}; {len(failed)} run(s) unusable", flush=True)
    for other in hits:
        print(f"  contaminates: {other}")
    if failed:
        print(f"  unusable: {', '.join(failed)}")
    return hits


def main():
    here = Path(__file__).parent
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", help="measure this suite against itself")
    ap.add_argument("--target", help='"Suite::Test" to scan predecessors for')
    ap.add_argument("--goldens", required=True,
                    help="nxdk_pgraph_tests_golden_results checkout; its "
                         "results/ tree names the tests in each suite")
    ap.add_argument("--sample-config",
                    help="optional resources/sample-config.json, unioned in")
    ap.add_argument("--base-iso", required=True)
    ap.add_argument("--emulator", required=True, help="qemu-system-i386")
    ap.add_argument("--pristine", required=True,
                    help="a blank qcow2 Xbox disk; copied fresh for each run")
    ap.add_argument("--settings", required=True,
                    help="JSON file whose .settings block seeds each config")
    ap.add_argument("--work", default="order-runs")
    ap.add_argument("--renderer", default="VULKAN", choices=["VULKAN", "OPENGL"])
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--xemu-toml", required=True)
    ap.add_argument("--bootrom", required=True)
    ap.add_argument("--flashrom", required=True)
    ap.add_argument("--eeprom", required=True)
    ap.add_argument("--make-iso", default=here / "make_test_iso.py")
    ap.add_argument("--extract", default=here / "extract_results.py")
    args = ap.parse_args()

    if bool(args.suite) == bool(args.target):
        ap.error("pass exactly one of --suite or --target")

    all_tests = roster(args.goldens, args.sample_config)
    lane = Lane(args, all_tests)
    if args.suite:
        if args.suite not in all_tests:
            ap.error(f"{args.suite!r} is not among the {len(all_tests)} suites "
                     f"the goldens name")
        mode_suite(lane, args.suite)
    else:
        if "::" not in args.target:
            ap.error('--target looks like "Suite::Test"')
        mode_target(lane, args.target)


if __name__ == "__main__":
    main()
