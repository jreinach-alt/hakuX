#!/usr/bin/env python3
"""nv2a_index - one command instead of five greps.

Derives a machine-readable map of the NV2A emulation:

    hardware symbol  <->  source site  <->  pgraph test suite  <->  tracker issue

Everything except the issue->suite table is DERIVED from the trees themselves,
so it regenerates and can be checked rather than maintained by hand. The one
hand-written part lives in nv2a_issues.toml and `check` validates every suite
it names against the derived list, so a rename or a typo fails loudly instead
of rotting.

Why this exists: tracing one texture format through this tree takes five
greps, and the fifth - that the sampler-signedness bits it depends on are
NV2A_UNIMPLEMENTED in both backends - is one nobody runs unprompted. See
docs/testing/pgraph-harness.md for the measurement side.

Usage:
    nv2a_index.py build [--tests DIR]      regenerate nv2a_index.json
    nv2a_index.py check [--tests DIR]      fail if the committed index is stale
    nv2a_index.py query symbol NV097_...   definition, sites, suites, issues
    nv2a_index.py query suite "Bump map"   what it exercises and where
    nv2a_index.py query file PATH[:LINE]   what lives here and who tests it
    nv2a_index.py query ident snorm_tex    cross-ref any identifier
    nv2a_index.py blast FILE [FILE...]     suites to re-measure after a patch
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
INDEX_PATH = os.path.join(HERE, "nv2a_index.json")
ISSUES_PATH = os.path.join(HERE, "nv2a_issues.toml")

REGS_H = "hw/xbox/nv2a/nv2a_regs.h"
SCAN_ROOTS = ["hw/xbox"]
SCAN_EXTS = (".c", ".h", ".inc", ".cpp")

SYMBOL_RE = re.compile(r"^\s*#\s*define\s+(NV097_[A-Z0-9_]+|NV_PGRAPH_[A-Z0-9_]+)\s+(\S+)")
IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
# Suites declare their name three different ways; all three are load-bearing.
# Missing any of them silently drops suites from the index, which is how the
# Fog / 3D primitive / 2D Lines entries in the tracker came to look unresolvable.
# Method handlers are declared by token-pasting macro, so the full symbol
# NEVER appears as a literal identifier:
#   DEF_METHOD(NV097, SET_SURFACE_COLOR_OFFSET)  ->  NV097_SET_SURFACE_COLOR_OFFSET
# Without this the index reports every implemented method as having no site,
# which is worse than an empty index - it is an authoritative wrong answer.
DEF_METHOD_RE = re.compile(r"\bDEF_METHOD(?:_[A-Z0-9_]+)?\s*\(\s*(\w+)\s*,\s*(\w+)")

SUITE_RES = (
    re.compile(r'TestSuite\(\s*host\s*,\s*std::move\(output_dir\)\s*,\s*"([^"]+)"'),
    re.compile(r'suite_name\s*=\s*"([^"]+)"'),
    re.compile(r'kSuiteName\s*=\s*"([^"]+)"'),
    # a subclass handing its name to a base-class ctor in the member-init list
    re.compile(r':\s*\w*Tests\([^;]*?"([^"]+)"\s*\)\s*\{'),
)


def sh(args, cwd):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def parse_regs(repo):
    """Every NV097_* / NV_PGRAPH_* define, with its value and definition site."""
    symbols = {}
    path = os.path.join(repo, REGS_H)
    with open(path, errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            m = SYMBOL_RE.match(line)
            if not m:
                continue
            name, value = m.group(1), m.group(2)
            symbols[name] = {
                "value": value,
                "defined_at": "%s:%d" % (REGS_H, n),
                "family": "NV097" if name.startswith("NV097_") else "NV_PGRAPH",
            }
    return symbols


def source_files(repo):
    for root in SCAN_ROOTS:
        for dirpath, _, names in os.walk(os.path.join(repo, root)):
            for name in sorted(names):
                if name.endswith(SCAN_EXTS):
                    full = os.path.join(dirpath, name)
                    yield full, os.path.relpath(full, repo)


def classify(line, symbol):
    """Role of a reference. Heuristic, and deliberately conservative."""
    s = line.strip()
    if s.startswith(("*", "//", "/*")):
        return "COMMENT"
    if re.search(r"\[\s*%s\s*\]\s*=" % re.escape(symbol), line):
        return "TABLE-ENTRY"
    if re.search(r"\bcase\s+%s\s*:" % re.escape(symbol), line):
        return "DISPATCH"
    if "NV2A_UNIMPLEMENTED" in line:
        return "STUB"
    if re.search(r"\bSET_MASK\s*\([^,]+,\s*%s" % re.escape(symbol), line):
        return "WRITE"
    if re.search(r"\bGET_MASK\s*\([^,]+,\s*%s" % re.escape(symbol), line):
        return "READ"
    if re.search(r"pgraph_reg_w\s*\([^)]*%s" % re.escape(symbol), line):
        return "WRITE"
    if re.search(r"pgraph_reg_r\s*\([^)]*%s" % re.escape(symbol), line):
        return "READ"
    return "REF"


def scan_sites(repo, symbols):
    """Every reference to a known symbol under hw/xbox, classified."""
    sites = {}
    for full, rel in source_files(repo):
        if rel == REGS_H:
            continue
        with open(full, errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                hits = {}
                if "NV097_" in line or "NV_PGRAPH_" in line:
                    for ident in set(IDENT_RE.findall(line)):
                        if ident in symbols:
                            hits[ident] = classify(line, ident)
                for gclass, name in DEF_METHOD_RE.findall(line):
                    pasted = "%s_%s" % (gclass, name)
                    if pasted in symbols:
                        hits[pasted] = "DECL" if rel.endswith(".inc") else "HANDLER"
                for ident, role in hits.items():
                    sites.setdefault(ident, []).append({
                        "loc": "%s:%d" % (rel, n),
                        "role": role,
                        "text": line.strip()[:160],
                    })
    return sites


TABLE_DEF_RE = re.compile(r"\b(?:constexpr|static|const)[^;=\n]*?\b(\w+)\s*\[\s*\]\s*=\s*\{")


def resolve_tables(support_dirs):
    """identifier -> hardware symbols, for shared tables in helper libraries.

    Several suites never name a format: `Texture format` iterates
    kTextureFormats[], defined in pbkitplusplus. Without this the index would
    report that the suite most central to issue #21 exercises no texture format
    at all, which is worse than useless - it is confidently wrong.
    """
    tables = {}
    for root in support_dirs or []:
        for dirpath, _, names in os.walk(root):
            if os.sep + ".git" in dirpath:
                continue
            for name in sorted(names):
                if not name.endswith((".c", ".cpp", ".h", ".hpp", ".inc")):
                    continue
                try:
                    with open(os.path.join(dirpath, name), errors="replace") as fh:
                        body = fh.read()
                except OSError:
                    continue
                for m in TABLE_DEF_RE.finditer(body):
                    start = body.index("{", m.end() - 1)
                    depth, i = 0, start
                    while i < len(body):
                        if body[i] == "{":
                            depth += 1
                        elif body[i] == "}":
                            depth -= 1
                            if depth == 0:
                                break
                        i += 1
                    block = body[start:i]
                    syms = {s for s in IDENT_RE.findall(block)
                            if s.startswith(("NV097_", "NV_PGRAPH_"))}
                    if syms:
                        tables.setdefault(m.group(1), set()).update(syms)
    return tables


def parse_suites(tests_root, tables=None):
    """Suite name -> the hardware symbols its own source pushes.

    A suite is a (name, source unit) pair. One unit can declare several suites
    (fog_tests.cpp declares Fog, Fog vsh and Fog coord vec4), and they share a
    symbol set because they share the code that pushes it.
    """
    suites = {}
    src_dir = os.path.join(tests_root, "src", "tests")
    if not os.path.isdir(src_dir):
        return suites
    units = {}
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith((".cpp", ".h")):
            continue
        stem = name.rsplit(".", 1)[0]
        units.setdefault(stem, []).append(name)
    for stem, names in sorted(units.items()):
        found, used = set(), set()
        for name in names:
            with open(os.path.join(src_dir, name), errors="replace") as fh:
                body = fh.read()
            for pattern in SUITE_RES:
                found.update(pattern.findall(body))
            idents = set(IDENT_RE.findall(body))
            used.update(i for i in idents
                        if i.startswith(("NV097_", "NV_PGRAPH_")))
            for name in idents & set(tables or {}):
                used.update(tables[name])
        for suite in found:
            entry = suites.setdefault(suite, {
                "sources": [],
                "symbols": [],
                "results_name": suite.replace(" ", "_"),
            })
            entry["sources"] = sorted(set(entry["sources"]) |
                                      {"src/tests/" + n for n in names})
            entry["symbols"] = sorted(set(entry["symbols"]) | used)
    return suites


def load_issues():
    """The one hand-written table: tracker issue -> suites. Validated by check."""
    if not os.path.exists(ISSUES_PATH):
        return {}
    issues, current = {}, None
    with open(ISSUES_PATH, errors="replace") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            m = re.match(r"^\[issue\.(\d+)\]$", line)
            if m:
                current = m.group(1)
                issues[current] = {"title": "", "suites": []}
                continue
            if current is None:
                continue
            m = re.match(r'^title\s*=\s*"(.*)"$', line)
            if m:
                issues[current]["title"] = m.group(1)
                continue
            m = re.match(r"^suites\s*=\s*\[(.*)\]$", line)
            if m:
                issues[current]["suites"] = [
                    v.strip().strip('"') for v in m.group(1).split(",") if v.strip()
                ]
    return issues


def build_index(repo, tests_root, support_dirs=None):
    symbols = parse_regs(repo)
    sites = scan_sites(repo, symbols)
    tables = resolve_tables(support_dirs) if support_dirs else {}
    suites = parse_suites(tests_root, tables) if tests_root else {}
    return {
        "schema": 1,
        "provenance": {
            "emulator_commit": sh(["git", "rev-parse", "HEAD"], repo),
            "tests_root": tests_root,
            "tests_commit": sh(["git", "rev-parse", "HEAD"], tests_root) if tests_root else None,
            "support_dirs": sorted(support_dirs or []),
            "resolved_tables": len(tables),
            "symbols": len(symbols),
            "sites": sum(len(v) for v in sites.values()),
            "suites": len(suites),
        },
        "symbols": symbols,
        "sites": sites,
        "suites": suites,
        "issues": load_issues(),
    }


def load_index():
    if not os.path.exists(INDEX_PATH):
        sys.exit("no index at %s - run: nv2a_index.py build --tests DIR" % INDEX_PATH)
    with open(INDEX_PATH) as fh:
        return json.load(fh)


def files_of(sites):
    return sorted({s["loc"].split(":")[0] for s in sites})


def suites_touching(index, files):
    """Which suites exercise a symbol that has a site in any of these files."""
    wanted = set(files)
    by_symbol = {}
    for symbol, sites in index["sites"].items():
        for s in sites:
            if s["loc"].split(":")[0] in wanted:
                by_symbol.setdefault(symbol, set()).add(s["loc"])
    hits = {}
    for suite, meta in index["suites"].items():
        shared = sorted(set(meta["symbols"]) & set(by_symbol))
        if shared:
            hits[suite] = shared
    return hits, by_symbol


def issues_for_suite(index, suite):
    return sorted(n for n, meta in index["issues"].items() if suite in meta["suites"])


def print_sites(sites, limit=None):
    order = {"HANDLER": 0, "DECODE": 1, "TABLE-ENTRY": 2, "DISPATCH": 3,
             "WRITE": 4, "READ": 5, "STUB": 6, "DECL": 7, "REF": 8, "COMMENT": 9}
    for s in sorted(sites, key=lambda s: (order.get(s["role"], 9), s["loc"]))[:limit]:
        print("  %-12s %-52s %s" % (s["role"], s["loc"], s["text"][:80]))
    if limit and len(sites) > limit:
        print("  ... %d more" % (len(sites) - limit))


def q_symbol(index, name):
    matches = [s for s in index["symbols"] if name.lower() in s.lower()]
    if not matches:
        sys.exit("no symbol matching %r" % name)
    if len(matches) > 1 and name not in index["symbols"]:
        print("%d symbols match %r:" % (len(matches), name))
        for m in matches[:40]:
            print("  " + m)
        return
    sym = name if name in index["symbols"] else matches[0]
    meta = index["symbols"][sym]
    sites = index["sites"].get(sym, [])
    print("%s = %s" % (sym, meta["value"]))
    print("  defined  %s" % meta["defined_at"])
    print("\nSITES (%d)" % len(sites))
    print_sites(sites)
    stubs = [s for s in sites if s["role"] == "STUB"]
    if stubs:
        print("\n!! %d site(s) are stubbed - this state is not fully emulated" % len(stubs))
    users = sorted(s for s, m in index["suites"].items() if sym in m["symbols"])
    if users:
        print("\nSUITES EXERCISING IT (%d)" % len(users))
        for s in users:
            iss = issues_for_suite(index, s)
            print("  %-40s %s" % (s, ("issue #" + ", #".join(iss)) if iss else ""))


def q_suite(index, name):
    matches = [s for s in index["suites"]
               if name.lower() in s.lower() or name.lower() in s.lower().replace(" ", "_")]
    if not matches:
        sys.exit("no suite matching %r" % name)
    if len(matches) > 1 and name not in index["suites"]:
        print("%d suites match %r:" % (len(matches), name))
        for m in matches:
            print("  " + m)
        return
    suite = name if name in index["suites"] else matches[0]
    meta = index["suites"][suite]
    print("SUITE  %s   (results dir: %s)" % (suite, meta["results_name"]))
    for s in meta["sources"]:
        print("  test source  %s" % s)
    iss = issues_for_suite(index, suite)
    if iss:
        for n in iss:
            print("  tracker      #%s  %s" % (n, index["issues"][n]["title"]))
    known = [s for s in meta["symbols"] if s in index["sites"]]
    print("\nEXERCISES %d hardware symbols, %d of which we implement somewhere"
          % (len(meta["symbols"]), len(known)))
    unimpl = [s for s in meta["symbols"]
              if s in index["symbols"] and s not in index["sites"]]
    files = {}
    stubbed = []
    for sym in known:
        for site in index["sites"][sym]:
            files.setdefault(site["loc"].split(":")[0], set()).add(sym)
            if site["role"] == "STUB":
                stubbed.append((sym, site["loc"]))
    print("\nIMPLEMENTED IN (%d files)" % len(files))
    for f, syms in sorted(files.items(), key=lambda kv: -len(kv[1])):
        print("  %-56s %d symbols" % (f, len(syms)))
    if stubbed:
        print("\nSTUBBED STATE THIS SUITE TOUCHES (%d)" % len(stubbed))
        for sym, loc in sorted(set(stubbed))[:20]:
            print("  %-52s %s" % (sym, loc))
    if unimpl:
        print("\nDEFINED BUT NO SITE FOUND UNDER hw/xbox (%d)" % len(unimpl))
        for s in sorted(unimpl)[:20]:
            print("  " + s)
        print("  (a symbol with no reader is a candidate ignored state bit)")


def q_file(index, spec):
    path, _, want_line = spec.partition(":")
    want_line = int(want_line) if want_line.isdigit() else None
    found = []
    for sym, sites in index["sites"].items():
        for s in sites:
            f, n = s["loc"].rsplit(":", 1)
            if f.endswith(path) or path in f:
                if want_line is None or abs(int(n) - want_line) <= 6:
                    found.append((sym, s))
    if not found:
        sys.exit("no indexed symbol references in %r" % spec)
    print("%d symbol reference(s) in %s" % (len(found), spec))
    for sym, s in sorted(found, key=lambda t: t[1]["loc"])[:60]:
        print("  %-12s %-46s %s" % (s["role"], s["loc"], sym))
    syms = {sym for sym, _ in found}
    users = {s: sorted(set(m["symbols"]) & syms)
             for s, m in index["suites"].items() if set(m["symbols"]) & syms}
    if users:
        print("\nSUITES THAT EXERCISE THIS CODE (%d)" % len(users))
        for s, shared in sorted(users.items(), key=lambda kv: -len(kv[1]))[:25]:
            iss = issues_for_suite(index, s)
            print("  %-40s %2d symbols  %s"
                  % (s, len(shared), ("#" + ", #".join(iss)) if iss else ""))


def q_ident(repo, ident):
    """Live cross-ref for any identifier - the struct fields the index omits."""
    hits = []
    pat = re.compile(r"\b%s\b" % re.escape(ident))
    for full, rel in source_files(repo):
        with open(full, errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if pat.search(line):
                    hits.append((rel, n, line.strip()[:150]))
    if not hits:
        sys.exit("no references to %r under hw/xbox" % ident)
    print("%d reference(s) to %s" % (len(hits), ident))
    for rel, n, text in hits:
        kind = "READ"
        if re.search(r"\b%s\b[^=!<>]*=(?!=)" % re.escape(ident), text):
            kind = "WRITE"
        if re.search(r"^\s*(bool|int|uint\w+|float|char|unsigned)\b.*\b%s\b" % re.escape(ident), text):
            kind = "DECL"
        if text.startswith(("*", "//", "/*")):
            kind = "COMMENT"
        emit = "  <- emits shader text" if "mstring_append" in text else ""
        print("  %-8s %s:%d%s" % (kind, rel, n, emit))
        print("           %s" % text)


def cmd_blast(index, files):
    rels = [os.path.relpath(os.path.abspath(f), REPO) for f in files]
    hits, by_symbol = suites_touching(index, rels)
    if not hits:
        print("No indexed suite exercises symbols in those files.")
        print("That is not a guarantee of safety - it may mean the coupling")
        print("is through a struct field rather than a hardware symbol.")
        print("Try: nv2a_index.py query ident <field>")
        return
    ranked = sorted(hits.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    top = len(ranked[0][1])
    # A suite sharing most of the symbols is implicated; one sharing a couple
    # probably just touches the same file. Split rather than print 54 rows.
    cut = max(3, top // 4)
    strong = [(s, v) for s, v in ranked if len(v) >= cut]
    weak = [(s, v) for s, v in ranked if len(v) < cut]
    print("Touching %d file(s) implicates %d suite(s).\n" % (len(rels), len(ranked)))
    print("RE-MEASURE THESE (%d):" % len(strong))
    for suite, shared in strong:
        iss = issues_for_suite(index, suite)
        print("  %-42s %2d shared symbols  %s"
              % (suite, len(shared), ("#" + ", #".join(iss)) if iss else ""))
    if weak:
        print("\nWeaker overlap (%d suites, <%d shared symbols) - likely incidental:"
              % (len(weak), cut))
        print("  " + ", ".join(s for s, _ in weak[:18]))
        if len(weak) > 18:
            print("  ... and %d more" % (len(weak) - 18))


def cmd_check(repo, tests_root, support_dirs=None):
    if not os.path.exists(INDEX_PATH):
        sys.exit("FAIL: no committed index at %s" % INDEX_PATH)
    with open(INDEX_PATH) as fh:
        committed = json.load(fh)
    fresh = build_index(repo, tests_root, support_dirs)
    problems = []
    for part in ("symbols", "sites"):
        if committed.get(part) != fresh.get(part):
            c, f = committed.get(part, {}), fresh.get(part, {})
            added = sorted(set(f) - set(c))[:10]
            removed = sorted(set(c) - set(f))[:10]
            problems.append("%s differ (committed %d, tree %d)%s%s" % (
                part, len(c), len(f),
                "\n    new: " + ", ".join(added) if added else "",
                "\n    gone: " + ", ".join(removed) if removed else ""))
    if tests_root and committed.get("suites") != fresh.get("suites"):
        problems.append("suites differ (committed %d, tests tree %d)"
                        % (len(committed.get("suites", {})), len(fresh.get("suites", {}))))
    known = set(fresh["suites"] or committed.get("suites", {}))
    for num, meta in load_issues().items():
        for suite in meta["suites"]:
            if known and suite not in known:
                problems.append("issue #%s names unknown suite %r" % (num, suite))
    if problems:
        print("STALE INDEX - regenerate with: nv2a_index.py build --tests DIR\n")
        for p in problems:
            print("  " + p)
        return 1
    print("index matches the tree (%d symbols, %d sites, %d suites)"
          % (len(fresh["symbols"]), sum(len(v) for v in fresh["sites"].values()),
             len(fresh["suites"])))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="regenerate the index")
    b.add_argument("--tests", help="path to an nxdk_pgraph_tests checkout")
    b.add_argument("--support", action="append", default=[],
                   help="helper-library checkout holding shared tables "
                        "(e.g. pbkitplusplus); repeatable")
    c = sub.add_parser("check", help="fail if the committed index is stale")
    c.add_argument("--tests", help="path to an nxdk_pgraph_tests checkout")
    c.add_argument("--support", action="append", default=[])

    q = sub.add_parser("query", help="look something up")
    q.add_argument("kind", choices=["symbol", "suite", "file", "ident"])
    q.add_argument("target")

    bl = sub.add_parser("blast", help="suites to re-measure after touching these files")
    bl.add_argument("files", nargs="+")

    args = ap.parse_args()
    tests = args.tests if getattr(args, "tests", None) else os.environ.get("PGRAPH_TESTS")
    support = getattr(args, "support", None) or (
        [d for d in os.environ.get("PGRAPH_SUPPORT", "").split(os.pathsep) if d])

    if args.cmd == "build":
        index = build_index(REPO, tests, support)
        with open(INDEX_PATH, "w") as fh:
            json.dump(index, fh, indent=1, sort_keys=True)
            fh.write("\n")
        p = index["provenance"]
        print("wrote %s" % os.path.relpath(INDEX_PATH, REPO))
        print("  %d symbols, %d sites, %d suites" % (p["symbols"], p["sites"], p["suites"]))
        if not tests:
            print("  NOTE: no --tests given, so the suite half is empty.")
        return 0
    if args.cmd == "check":
        return cmd_check(REPO, tests, support)
    if args.cmd == "blast":
        return cmd_blast(load_index(), args.files)

    index = load_index()
    if args.kind == "symbol":
        return q_symbol(index, args.target)
    if args.kind == "suite":
        return q_suite(index, args.target)
    if args.kind == "file":
        return q_file(index, args.target)
    if args.kind == "ident":
        return q_ident(REPO, args.target)


if __name__ == "__main__":
    sys.exit(main() or 0)
