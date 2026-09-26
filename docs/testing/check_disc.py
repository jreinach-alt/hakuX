#!/usr/bin/env python3
"""Say what a test disc will actually run, before spending device time on it.

    check_disc.py <iso> [--expect "Suite name" ...]

Reads nxdk_pgraph_tests_config.json straight out of the xiso image and prints
the suites it enables and where the guest will write. With --expect, exits 1
unless every named suite is enabled -- so a run script can refuse to boot a
disc that would sit at the menu for its whole timeout.

Why this exists: the stock disc also carries a sample-config.json with
skip_tests_by_default=false and no suites, and a naive search finds that one
first. Two device runs were spent "verifying" the wrong file. The config we
write is the one whose settings block names our --output-dir, so that string
is the anchor, and the object is found by trying every '{' before it from the
outermost inward until one parses and contains it.
"""
import argparse, json, sys

def read_config(path):
    raw = open(path, "rb").read()
    i = raw.find(b'"output_directory_path"')
    while i >= 0:
        lo = max(0, i - 8192)
        for a in range(lo, i):                      # outermost first
            if raw[a:a+1] != b"{":
                continue
            depth = 0
            for b in range(a, min(len(raw), i + 16384)):
                c = raw[b:b+1]
                if c == b"{": depth += 1
                elif c == b"}":
                    depth -= 1
                    if depth == 0:
                        try:
                            j = json.loads(raw[a:b+1].decode())
                        except Exception:
                            break
                        if "test_suites" in j or "settings" in j:
                            return j
                        break
        i = raw.find(b'"output_directory_path"', i + 1)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--expect", action="append", default=[])
    a = ap.parse_args()
    cfg = read_config(a.iso)
    if cfg is None:
        print("no test config found in", a.iso); return 2
    settings = cfg.get("settings", cfg)
    suites = cfg.get("test_suites", {})
    enabled = [s for s, v in suites.items()
               if not (v.get("skipped", False) if isinstance(v, dict) else False)]
    print(f"{a.iso}")
    shutdown = settings.get('enable_shutdown_on_completion')
    print(f"  output: {settings.get('output_directory_path')}   "
          f"skip_by_default={settings.get('skip_tests_by_default')}   "
          f"progress_log={settings.get('enable_progress_log')}   "
          f"shutdown_on_completion={shutdown}")
    if not shutdown:
        # Without it the guest reboots and reruns the suite when it finishes,
        # and run_disc.sh waits out its whole cap. With it the process exits
        # seconds after the last capture. Pass --shutdown-on-completion to
        # make_test_iso.py.
        print("  WARNING: no shutdown-on-completion; this run will idle to its"
              " timeout instead of exiting when the suite finishes")
    print(f"  enabled suites ({len(enabled)}): " + ", ".join(enabled))
    missing = [s for s in a.expect if s not in enabled]
    if missing:
        print("  MISSING:", ", ".join(missing)); return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
