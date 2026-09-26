#!/usr/bin/env python3
"""Build one disc per suite that runs a single test, to classify substitutions.

`crossmatch.py` finds tests that render *another test's* image. That signature
has two causes needing opposite fixes:

  * **contamination** — earlier state leaks forward; the test is correct alone;
  * **an unimplemented state distinction** — two tests differ by a bit we
    ignore, so the test is wrong even alone.

Running the test by itself is what tells them apart. This builds those discs.

Only the *solo* arm needs a new run: the full sweep the crossmatch came from is
already the "in company" arm, so one disc per suite is enough rather than two.

    make_isolation_discs.py crossmatch.txt --results results_final \\
        --base nxdk_pgraph_tests_xiso.iso --out-dir discs/

For each suite it picks the most unambiguous substitution (largest ratio between
the error against its own golden and against the golden it actually reproduces),
enables that one test, and skips every other test it can name for that suite.
The skip list unions the sweep's results with the goldens: a test that *aborts*
writes no PNG, so results alone miss it and it runs regardless, defeating the
isolation. Each disc has `enable_progress_log` on, because neither
`--newer-than` nor FATX mtimes prove a test ran — see
docs/testing/pgraph-harness.md, and check the log shows our test as `[1/1]`.

Suite names come from the results directory with underscores turned into
spaces. That matches the XBE for every suite present in `sample-config.json`,
but a handful of suites are absent from that file and their names are therefore
a guess. A wrong guess runs nothing and shows up as an empty progress log, so it
fails loudly rather than silently — check the log before trusting a result.
"""
import argparse
import collections
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_crossmatch(path):
    """Yield (suite, test, impersonated, own_err, other_err) from a report."""
    rows = []
    for line in open(path, encoding="utf-8").read().splitlines():
        f = line.split()
        if len(f) < 5 or line.startswith("-") or line.startswith("suite"):
            continue
        try:
            own, other = float(f[-2]), float(f[-1])
        except ValueError:
            continue
        rows.append((f[0], f[1], f[2], own, other))
    return rows


def tests_to_skip(results_dir, goldens_dir, suite):
    """Every test name we can find for this suite, to skip all but one.

    Union of two sources on purpose. The sweep's results are what actually
    produced output, but a test that *aborts* writes no PNG and so is absent
    from them -- and would then run, defeating the isolation. The goldens
    enumerate every test the suite can run. Over-skipping is harmless; a name
    the XBE does not know is ignored.
    """
    out = set()
    for name in os.listdir(results_dir):
        if name.endswith(".png") and name.startswith(suite + "::"):
            out.add(name[:-4].split("::", 1)[1])
    gdir = os.path.join(goldens_dir, suite)
    if os.path.isdir(gdir):
        for name in os.listdir(gdir):
            if name.endswith(".png"):
                out.add(name[:-4])
    return sorted(out)


def config_for(suite_key, keep, skip, out_dir="e:/nxdk_pgraph_tests"):
    suite = {"skipped": False, keep: {"skipped": False}}
    for t in skip:
        if t != keep:
            suite[t] = {"skipped": True}
    return {
        "settings": {
            # The only trustworthy record that a test actually ran.
            "enable_progress_log": True,
            "disable_autorun": False,
            "enable_autorun_immediately": True,
            "enable_shutdown_on_completion": True,
            "enable_pgraph_region_diff": False,
            "skip_tests_by_default": True,
            "delay_milliseconds_between_tests": 0,
            "delay_milliseconds_before_exit": 4000,
            "network": {
                "enable": False, "config_automatic": False, "config_dhcp": False,
                "static_ip": "", "static_netmask": "", "static_gateway": "",
                "static_dns_1": "", "static_dns_2": "",
                "ftp": {"ftp_ip": "", "ftp_port": 21, "ftp_user": "xbox",
                        "ftp_password": "xbox", "ftp_timeout_milliseconds": 10000},
            },
            "sharding": {"index": 0, "count": 0},
            "output_directory_path": out_dir,
        },
        "test_suites": {suite_key: suite},
    }


def build_one(args):
    """One disc for one test, written to --out-dir/iso.iso, plan on stdout."""
    suite, test = args.build_one.split("::", 1)
    skip = tests_to_skip(args.results, args.goldens, suite)
    if test not in skip:
        skip.append(test)
    # Unique across the whole corpus, not just within a suite: two suites both
    # numbering from zero overwrote each other's progress logs once already.
    tag = hashlib.md5(args.build_one.encode()).hexdigest()[:8]
    out_dir = f"e:/{tag}"
    os.makedirs(args.out_dir, exist_ok=True)
    cfg_path = os.path.join(args.out_dir, "cfg.json")
    iso_path = os.path.join(args.out_dir, "iso.iso")
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(config_for(suite.replace("_", " "), test, skip, out_dir), fh, indent=2)
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "make_test_iso.py"), args.base,
         "-o", iso_path, "--config", cfg_path],
        capture_output=True, text=True)
    if r.returncode != 0:
        print((r.stderr or r.stdout).strip()[:200], file=sys.stderr)
        return 1
    print(json.dumps({"suite": suite, "test": test, "guest_dir": tag,
                      "iso": iso_path}))
    return 0


def build_every_test(args):
    """One disc per test in a suite, each with its own guest output directory."""
    suite = args.every_test
    tests = tests_to_skip(args.results, args.goldens, suite)
    if not tests:
        sys.exit(f"no tests found for suite {suite}")
    suite_key = suite.replace("_", " ")
    os.makedirs(args.out_dir, exist_ok=True)
    manifest = []
    for n, test in enumerate(tests):
        # Guest dir names must be unique *across suites*, not just within one:
        # two suites both numbering from 000 overwrite each other's progress
        # logs in the shared image, which silently destroys the per-run
        # verification this whole scheme exists to provide. Namespace by a hash
        # of the suite name, and keep it short for FATX.
        tag = hashlib.md5(suite.encode()).hexdigest()[:4]
        out_dir = f"e:/{tag}{n:03d}"
        cfg_path = os.path.join(args.out_dir, f"cfg-{n:03d}.json")
        iso_path = os.path.join(args.out_dir, f"iso-{n:03d}.iso")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(config_for(suite_key, test, tests, out_dir), fh, indent=2)
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "make_test_iso.py"), args.base,
             "-o", iso_path, "--config", cfg_path],
            capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  {test}: BUILD FAILED {(r.stderr or r.stdout).strip()[:50]}")
            continue
        manifest.append({"suite": suite, "suite_key": suite_key, "test": test,
                         "guest_dir": out_dir.split("/", 1)[1], "iso": iso_path})
    mpath = os.path.join(args.out_dir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"{len(manifest)} discs for {suite} in {args.out_dir}")
    print("Run them all, then pull the image ONCE and extract each guest_dir.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("crossmatch", help="output of crossmatch.py")
    ap.add_argument("--results", required=True,
                    help="the sweep's results dir, to enumerate what each suite ran")
    ap.add_argument("--goldens", required=True,
                    help="goldens/results — enumerates tests that abort and so "
                         "write no output, which the results dir cannot")
    ap.add_argument("--base", required=True, help="stock nxdk_pgraph_tests xiso")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--suite", action="append",
                    help="restrict to these suites (repeatable)")
    ap.add_argument("--build-one", metavar="Suite::Test",
                    help="build a single disc for one test and exit. Lets a long "
                         "queue build discs just-in-time instead of writing "
                         "thousands of ISOs up front.")
    ap.add_argument("--every-test", metavar="SUITE",
                    help="build one disc per test in SUITE rather than one per "
                         "suite, to re-measure a whole suite free of "
                         "contamination. Each disc writes to its own guest "
                         "output directory, so a single image pull afterwards "
                         "yields a separate progress log per run -- pulling a "
                         "1.1GB image per run otherwise dominates the cost.")
    args = ap.parse_args()

    if args.build_one:
        return build_one(args)
    if args.every_test:
        return build_every_test(args)

    os.makedirs(args.out_dir, exist_ok=True)
    rows = parse_crossmatch(args.crossmatch)
    if not rows:
        sys.exit(f"no substitutions parsed from {args.crossmatch}")

    best = {}
    for suite, test, other, own, oth in rows:
        if args.suite and suite not in args.suite:
            continue
        ratio = own / max(oth, 1e-6)
        if suite not in best or ratio > best[suite][0]:
            best[suite] = (ratio, test, other, own, oth)

    print(f"{'suite':<32} {'test run alone':<32} {'own':>7} {'impersonates':>7}")
    print("-" * 88)
    manifest = []
    for suite, (_ratio, test, other, own, oth) in sorted(best.items()):
        skip = tests_to_skip(args.results, args.goldens, suite)
        if test not in skip:
            skip.append(test)
        suite_key = suite.replace("_", " ")
        cfg_path = os.path.join(args.out_dir, f"cfg-{suite}.json")
        iso_path = os.path.join(args.out_dir, f"iso-{suite}.iso")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(config_for(suite_key, test, skip), fh, indent=2)
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "make_test_iso.py"), args.base,
             "-o", iso_path, "--config", cfg_path],
            capture_output=True, text=True)
        if r.returncode != 0:
            print(f"{suite:<32} BUILD FAILED: {(r.stderr or r.stdout).strip()[:40]}")
            continue
        print(f"{suite:<32} {test:<32} {own:>7.2f} {oth:>7.2f}")
        manifest.append({"suite": suite, "suite_key": suite_key, "test": test,
                         "impersonates": other, "own_err": own, "other_err": oth,
                         "iso": iso_path, "in_sweep_tests": len(skip)})

    mpath = os.path.join(args.out_dir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\n{len(manifest)} discs in {args.out_dir}, manifest at {mpath}")
    print("Run each, then check pgraph_progress_log.txt says the test ran before "
          "trusting its result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
