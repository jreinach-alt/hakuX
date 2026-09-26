#!/usr/bin/env python3
"""Turn a directory of uploaded test images into a comparable result set.

The test suite uploads each captured framebuffer under a flat name built as
``<suite name>::<test name>.png``, so an FTP server that took a run ends up
with a few thousand files in one directory.  The comparison tooling instead
walks a tree and reads the suite from the containing directory:

    <run>/<Suite_Name>/<Test_Name>.png

which is also the layout of the hardware goldens.  This rearranges one into
the other, copying by default so that a bad collection can be redone.

See pgraph-harness.md for where this sits in the pipeline.
"""

import argparse
import os
import shutil
import sys

SEPARATOR = "::"


def collect(source, destination, skip_zbuffer=False, move=False):
    """Copy <suite>::<test>.png files from source into destination/<suite>/."""
    unnamed = []
    suites = {}

    for root, _dirnames, filenames in os.walk(source):
        for filename in sorted(filenames):
            if not filename.lower().endswith(".png"):
                continue
            if SEPARATOR not in filename:
                unnamed.append(os.path.join(root, filename))
                continue

            suite, _, test = filename.partition(SEPARATOR)
            if skip_zbuffer and test.lower().endswith("_zb.png"):
                continue

            # The goldens name suite directories with underscores.
            suite_directory = os.path.join(destination, suite.replace(" ", "_"))
            os.makedirs(suite_directory, exist_ok=True)
            target = os.path.join(suite_directory, test)
            source_path = os.path.join(root, filename)
            if move:
                shutil.move(source_path, target)
            else:
                shutil.copyfile(source_path, target)
            suites.setdefault(suite, []).append(test)

    return suites, unnamed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="directory the run was uploaded into")
    parser.add_argument("-o", "--output", default="local/results",
                        help="root to build the result tree under "
                             "(default: %(default)s)")
    parser.add_argument("--run-id", default="hakuX/Android/unknown",
                        help="'build/platform/renderer', used only to label the "
                             "run in the comparison output (default: %(default)s)")
    parser.add_argument("--skip-zbuffer", action="store_true",
                        help="drop the _ZB depth captures. The goldens do carry "
                             "them, so this only makes a run smaller.")
    parser.add_argument("--move", action="store_true",
                        help="move instead of copying")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.source):
        parser.error("%s is not a directory" % args.source)

    destination = os.path.join(args.output, *args.run_id.split("/"))
    suites, unnamed = collect(args.source, destination, args.skip_zbuffer, args.move)

    total = sum(len(tests) for tests in suites.values())
    print("collected %d image(s) across %d suite(s) into %s" % (total, len(suites), destination))
    if not total:
        print("\nNothing was collected. The suite uploads names shaped like\n"
              "  'Texture format::Fmt_A8R8G8B8.png'\n"
              "so a source directory without '%s' in its filenames is not a run."
              % SEPARATOR, file=sys.stderr)
        return 1
    if unnamed:
        print("skipped %d file(s) with no '%s' in the name, e.g. %s"
              % (len(unnamed), SEPARATOR, os.path.basename(unnamed[0])))

    print("\nCompare against the hardware goldens with:")
    print("  python3 dev_scripts/compare.py %s -o local/compare" % destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
