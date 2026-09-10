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
    nv2a_index.py query gaps "Fog gen"     known-wrong markers in that code
    nv2a_index.py query unread "Fog gen"   state it sets that nothing reads
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

SYMBOL_RE = re.compile(r"^(#(?:\s*)?)define\s+(NV097_[A-Z0-9_]+|NV_PGRAPH_[A-Z0-9_]+)\s+(\S+)")
# Indentation in nv2a_regs.h encodes the hierarchy - see docs/nv2a/vocabulary.md.
# "#define" is a register or method, "#   define" a field mask, "#       define"
# an enum value of that field. Without this a missing enum value and a missing
# register read the same, and they are very different findings.
DEPTH_KIND = {0: "register/method", 1: "field", 2: "enum-value"}
IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
# Suites declare their name three different ways; all three are load-bearing.
# Missing any of them silently drops suites from the index, which is how the
# Fog / 3D primitive / 2D Lines entries in the tracker came to look unresolvable.
# Method handlers are declared by token-pasting macro, so the full symbol
# NEVER appears as a literal identifier:
#   DEF_METHOD(NV097, SET_SURFACE_COLOR_OFFSET)  ->  NV097_SET_SURFACE_COLOR_OFFSET
# Without this the index reports every implemented method as having no site,
# which is worse than an empty index - it is an authoritative wrong answer.
# Known-wrong markers already in the code. The last class is the point:
# an unmarked hedge ("R is probably unsigned", pgraph/texture.c:389 - the
# comment behind issue #21) is a lead that grepping for FIXME never finds,
# and it carries no marker for anyone to notice it later.
GAP_RES = (
    ("MARKED", re.compile(r"\b(FIXME|TODO|XXX|HACK)\b")),
    ("STUB", re.compile(r"\bNV2A_UNIMPLEMENTED\b")),
    ("ABORT", re.compile(r"assert\s*\(\s*(?:false|0|!\s*\")|\babort\s*\(\s*\)")),
    ("HEDGE", re.compile(r"\b(probably|might be|may not be|not sure|unclear|"
                         r"unconfirmed|we assume|presumably|best guess)\b", re.I)),
)
COMMENTISH_RE = re.compile(r"^\s*(/\*|\*|//)|/\*|//")

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
            name, value = m.group(2), m.group(3)
            indent = len(m.group(1)) - 1
            depth = 0 if indent < 2 else (1 if indent < 6 else 2)
            symbols[name] = {
                "value": value,
                "defined_at": "%s:%d" % (REGS_H, n),
                "family": "NV097" if name.startswith("NV097_") else "NV_PGRAPH",
                "kind": DEPTH_KIND[depth],
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


def scan_sites(repo, symbols, seen_idents=None):
    """Every reference to a known symbol under hw/xbox, classified."""
    sites = {}
    for full, rel in source_files(repo):
        if rel == REGS_H:
            continue
        with open(full, errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if seen_idents is not None:
                    seen_idents.update(IDENT_RE.findall(line))
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


def map_method_regs(repo):
    """method -> the PGRAPH registers its handler touches.

    Tests push NV097_* methods and never name a register, while the state
    that goes unread is almost all NV_PGRAPH_* fields. Without this hop a
    suite can never be joined to the state it actually drives. Derived by
    attributing every NV_PGRAPH_* reference to the DEF_METHOD block it falls
    inside, which is exact because handlers do not nest.
    """
    method_regs = {}
    for full, rel in source_files(repo):
        if not rel.endswith(".c"):
            continue
        with open(full, errors="replace") as fh:
            lines = fh.readlines()
        current = None
        for line in lines:
            found = DEF_METHOD_RE.search(line)
            if found:
                # the macro's own #define lines are not handlers
                current = (None if line.lstrip().startswith("#")
                           else "%s_%s" % found.groups())
                continue
            if current is None:
                continue
            for ident in IDENT_RE.findall(line):
                if ident.startswith("NV_PGRAPH_"):
                    method_regs.setdefault(current, set()).add(ident)
    return {k: sorted(v) for k, v in sorted(method_regs.items())}


def find_unread(symbols, sites, seen):
    """Symbols with no site, split into genuinely absent and merely renamed.

    A symbol with no reference is a candidate ignored state bit - the shape
    behind the missing-state half of the accuracy tracker. But the emulator
    also keeps parallel enums for state it does handle: PRIM_TYPE_LINE_LOOP
    (pgraph/vsh_regs.h:189) is NV097_SET_BEGIN_END_OP_LINE_LOOP under another
    name. Reporting those as ignored would be confidently wrong, so they are
    separated out - and a parallel name is its own unenforced coupling.
    """
    unread = {}
    for name, meta in symbols.items():
        if name in sites:
            continue
        parts = name.split("_")
        aliases = []
        for start in range(1, len(parts) - 1):
            tail = "_".join(parts[start:])
            if len(tail) < 6:
                break
            aliases = sorted(i for i in seen
                             if i != name and i.endswith("_" + tail))
            if aliases:
                break
        unread[name] = {
            "kind": meta["kind"],
            "defined_at": meta["defined_at"],
            "aliases": aliases[:4],
        }

    # Rank the enum values. An unread enum value means very different things
    # depending on whether its parent field is read, and whether any sibling
    # value is:
    #
    #   ZFUNC_ALWAYS         parent read, NO sibling referenced -> the value is
    #                        used numerically and the names are decoration
    #   PROVOKING_VERTEX_    parent read, siblings referenced, this one not ->
    #   FIRST                the code branches on some values and not others.
    #                        That is a real unhandled case.
    #   (parent unread)      the whole field is ignored.
    for name, entry in unread.items():
        if entry["kind"] != "enum-value":
            continue
        parts = name.split("_")
        parent = next((p for p in ("_".join(parts[:i])
                                   for i in range(len(parts) - 1, 2, -1))
                       if symbols.get(p, {}).get("kind") == "field"), None)
        if parent is None:
            entry["signal"] = "unknown-parent"
            continue
        siblings = [s for s in symbols
                    if s != name and s.startswith(parent + "_")
                    and symbols[s]["kind"] == "enum-value"]
        if parent not in sites:
            entry["signal"] = "field-ignored"
        elif any(s in sites for s in siblings):
            entry["signal"] = "unhandled-case"
        else:
            entry["signal"] = "positional"
        entry["parent"] = parent
    return unread


def scan_gaps(repo, sites):
    """Harvest known-wrong markers and attach them to nearby symbols.

    Derived, not curated: a punch list kept as a file goes stale the moment
    somebody fixes an entry. This regenerates, so a fixed FIXME leaves the
    list by being fixed.
    """
    by_file = {}
    for symbol, refs in sites.items():
        for ref in refs:
            path, line = ref["loc"].rsplit(":", 1)
            by_file.setdefault(path, {}).setdefault(int(line), set()).add(symbol)

    gaps = []
    for full, rel in source_files(repo):
        with open(full, errors="replace") as fh:
            lines = fh.readlines()
        for n, line in enumerate(lines, 1):
            for kind, pattern in GAP_RES:
                if not pattern.search(line):
                    continue
                # HEDGE only counts inside prose; elsewhere it is a variable name
                if kind == "HEDGE" and not COMMENTISH_RE.search(line):
                    continue
                near = set()
                for probe in range(max(1, n - 8), n + 9):
                    near |= by_file.get(rel, {}).get(probe, set())
                gaps.append({
                    "loc": "%s:%d" % (rel, n),
                    "kind": kind,
                    "text": line.strip()[:170],
                    "symbols": sorted(near),
                })
                break
    return gaps


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
    issues, current, pending = {}, None, None
    with open(ISSUES_PATH, errors="replace") as fh:
        for line in fh:
            # Strip trailing comments, but not a '#' inside a quoted string.
            if not line.lstrip().startswith("#"):
                line = re.sub(r'\s+#(?=(?:[^"]*"[^"]*")*[^"]*$).*$', "", line)
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if pending is not None:          # continuing a multi-line array
                pending += " " + line
                if "]" not in pending:
                    continue
                body = pending[pending.index("[") + 1:pending.rindex("]")]
                issues[current]["suites"] = [v.strip().strip('"')
                                             for v in body.split(",") if v.strip()]
                pending = None
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
            if re.match(r"^suites\s*=\s*\[", line):
                # Arrays wrap across lines. Reading only single-line ones made
                # five issues silently suite-less, and check() could not see it
                # because an empty list has nothing to disagree with.
                if "]" in line:
                    body = line[line.index("[") + 1:line.rindex("]")]
                    issues[current]["suites"] = [v.strip().strip('"')
                                                 for v in body.split(",") if v.strip()]
                else:
                    pending = line
    return issues


def build_index(repo, tests_root, support_dirs=None):
    symbols = parse_regs(repo)
    seen = set()
    sites = scan_sites(repo, symbols, seen)
    unread = find_unread(symbols, sites, seen)
    method_regs = map_method_regs(repo)
    tables = resolve_tables(support_dirs) if support_dirs else {}
    suites = parse_suites(tests_root, tables) if tests_root else {}
    gaps = scan_gaps(repo, sites)
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
            "gaps": len(gaps),
            "unread": sum(1 for v in unread.values() if not v["aliases"]),
        },
        "symbols": symbols,
        "sites": sites,
        "gaps": gaps,
        "unread": unread,
        "method_regs": method_regs,
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


def gaps_for_files(index, files):
    want = set(files)
    return [g for g in index.get("gaps", []) if g["loc"].split(":")[0] in want]


def print_gaps(gaps, limit=40):
    # Scarcest and least self-announcing first. A bare assert(false) in a
    # default branch is ordinary defensive code; an unmarked hedge is an
    # unresolved question nobody will ever grep for.
    order = {"HEDGE": 0, "STUB": 1, "MARKED": 2, "ABORT": 3}
    shown = sorted(gaps, key=lambda g: (order.get(g["kind"], 9), g["loc"]))
    for g in shown[:limit]:
        print("  %-7s %-46s %s" % (g["kind"], g["loc"], g["text"][:88]))
    if len(shown) > limit:
        print("  ... %d more" % (len(shown) - limit))


def summarise_gaps(gaps, indent="  "):
    counts = {}
    for g in gaps:
        counts[g["kind"]] = counts.get(g["kind"], 0) + 1
    if not counts:
        return
    print(indent + "known-wrong here: " +
          ", ".join("%d %s" % (counts[k], k) for k in
                    sorted(counts, key=lambda k: -counts[k])))


def q_unread(index, target=None):
    """Symbols with no reader: candidate ignored state."""
    unread = index.get("unread", {})
    scope = None
    if target and target not in ("all", "*"):
        match = [s for s in index["suites"] if target.lower() in s.lower()]
        if match:
            scope = match[0]
            methods = set(index["suites"][scope]["symbols"])
            regs = set()
            for m in methods:
                regs.update(index.get("method_regs", {}).get(m, []))
            keep = set(methods) | regs
            unread = {k: v for k, v in unread.items()
                      if k in keep or any(k.startswith(r + "_") for r in regs)}
        else:
            unread = {k: v for k, v in unread.items()
                      if target.upper() in k.upper()}
    if not unread:
        sys.exit("no unread symbols matching %r" % target)

    absent = {k: v for k, v in unread.items() if not v["aliases"]}
    aliased = {k: v for k, v in unread.items() if v["aliases"]}
    if scope:
        iss = issues_for_suite(index, scope)
        print("STATE %r EXERCISES THAT NOTHING READS%s\n"
              % (scope, ("   tracker #" + ", #".join(iss)) if iss else ""))
    print("%d symbol(s) with no site under hw/xbox — %d absent, %d renamed\n"
          % (len(unread), len(absent), len(aliased)))

    positional = [k for k, v in absent.items() if v.get("signal") == "positional"]
    groups = [
        ("REGISTER/METHOD - nothing references it at all",
         [k for k, v in absent.items() if v["kind"] == "register/method"]),
        ("FIELD - the whole field is unread",
         [k for k, v in absent.items() if v["kind"] == "field"]),
        ("ENUM VALUE - its field is unread entirely",
         [k for k, v in absent.items() if v.get("signal") == "field-ignored"]),
        ("ENUM VALUE - siblings are handled, this case is not",
         [k for k, v in absent.items() if v.get("signal") == "unhandled-case"]),
    ]
    for title, rows in groups:
        rows = sorted(rows)
        if not rows:
            continue
        print("%s (%d)" % (title, len(rows)))
        for name in rows[:25]:
            extra = absent[name].get("parent", "")
            print("  %-56s %s" % (name, extra or absent[name]["defined_at"]))
        if len(rows) > 25:
            print("  ... %d more" % (len(rows) - 25))
        print()
    if positional:
        print("%d enum value(s) omitted: their field is read but the value is used"
              % len(positional))
        print("numerically, so the name being unreferenced means nothing.\n")
    if aliased:
        print("HANDLED UNDER ANOTHER NAME (%d) — not ignored, but nothing keeps"
              % len(aliased))
        print("the two spellings in step:")
        for name in sorted(aliased)[:12]:
            print("  %-52s -> %s" % (name, ", ".join(aliased[name]["aliases"][:2])))
        if len(aliased) > 12:
            print("  ... %d more" % (len(aliased) - 12))
    print("\nA symbol with no reader is a CANDIDATE, not a finding: it may be")
    print("read through a mask this scan cannot follow. Verify before acting.")


def q_gaps(index, target):
    """Known-wrong markers, scoped to a suite, a file or a symbol."""
    if target in index["suites"] or any(target.lower() in s.lower() for s in index["suites"]):
        suite = target if target in index["suites"] else next(
            s for s in sorted(index["suites"]) if target.lower() in s.lower())
        syms = set(index["suites"][suite]["symbols"])
        files = {s["loc"].split(":")[0]
                 for sym in syms & set(index["sites"])
                 for s in index["sites"][sym]}
        gaps = [g for g in gaps_for_files(index, files)
                if not g["symbols"] or set(g["symbols"]) & syms]
        iss = issues_for_suite(index, suite)
        print("KNOWN-WRONG IN THE CODE %r EXERCISES%s" %
              (suite, ("   tracker #" + ", #".join(iss)) if iss else ""))
        print("%d marker(s) across %d file(s)\n" % (len(gaps), len(files)))
        print_gaps(gaps)
        return
    hits = [g for g in index.get("gaps", [])
            if target in g["loc"] or target in g["symbols"]
            or any(target in s for s in g["symbols"])]
    if not hits:
        sys.exit("no known-wrong markers matching %r" % target)
    print("%d marker(s) matching %r\n" % (len(hits), target))
    print_gaps(hits, limit=80)


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
    near = [g for g in index.get("gaps", []) if sym in g["symbols"]]
    if near:
        print("\nKNOWN-WRONG NEARBY (%d)" % len(near))
        print_gaps(near, limit=12)
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
    gaps = gaps_for_files(index, files)
    if gaps:
        print()
        summarise_gaps(gaps, indent="")
        print("  nv2a_index.py query gaps %r  for the list" % suite)
    if unimpl:
        ur = index.get("unread", {})
        absent = [s for s in unimpl if not ur.get(s, {}).get("aliases")]
        renamed = [s for s in unimpl if ur.get(s, {}).get("aliases")]
        print("\nNOTHING READS THESE (%d absent, %d handled under another name)"
              % (len(absent), len(renamed)))
        for s in sorted(absent)[:15]:
            print("  %-56s %s" % (s, ur.get(s, {}).get("kind", "")))
        if len(absent) > 15:
            print("  ... %d more" % (len(absent) - 15))
        print("  nv2a_index.py query unread %r  for the full split" % suite)


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
    parsed = load_issues()
    if not parsed:
        problems.append("nv2a_issues.toml parsed to nothing")
    for num, meta in parsed.items():
        # An issue with no suites is not a valid entry - it is the signature of
        # a parser that silently dropped them.
        if not meta["suites"]:
            problems.append("issue #%s has no suites (parse failure or empty entry)"
                            % num)
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
    q.add_argument("kind",
                   choices=["symbol", "suite", "file", "ident", "gaps", "unread"])
    q.add_argument("target", nargs="?")

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
    if args.kind != "unread" and not args.target:
        sys.exit("query %s needs a target" % args.kind)
    if args.kind == "symbol":
        return q_symbol(index, args.target)
    if args.kind == "suite":
        return q_suite(index, args.target)
    if args.kind == "file":
        return q_file(index, args.target)
    if args.kind == "ident":
        return q_ident(REPO, args.target)
    if args.kind == "gaps":
        return q_gaps(index, args.target)
    if args.kind == "unread":
        return q_unread(index, args.target)


if __name__ == "__main__":
    sys.exit(main() or 0)
