#!/usr/bin/env python3
"""models.py -- the one reader for docs/testing/jobs/models.toml (#433).

    models.py model <kind> [--escalate]   the model for this kind of work,
                                           in whichever mode is active now
    models.py resolve <token> [--escalate]  <token> is a kind name OR a bare
                                           legacy model id ($WORK/briefs/*.model)
    models.py dial <name>                 a [usage] value, e.g. low_pct
    models.py low                         exit 0 if Low is active, 1 otherwise
    models.py kinds                       the known kind names, one per line

Importable the same way: model_for(kind, escalate=False), resolve(token,
escalate=False), dial(name), is_low().

$HAKUX_WORK picks the work tree (default /home/justin/hakux-work); Low is
active iff $HAKUX_WORK/usage/low-active exists. $HAKUX_MODELS_TOML overrides
which table this reads, for a selftest's own fixture.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOML_PATH = os.environ.get("HAKUX_MODELS_TOML", os.path.join(HERE, "models.toml"))

try:
    import tomllib
except ImportError:
    tomllib = None


def _load():
    if tomllib is not None:
        with open(TOML_PATH, "rb") as f:
            return tomllib.load(f)
    # No tomllib (Python < 3.11): a tiny reader for this file's own shape
    # only -- flat key="value" lines, [table] / [table.sub] headers, and
    # ["a", "b"] lists of strings. Not a general TOML parser.
    import re
    d, cur = {}, None
    for line in open(TOML_PATH, encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^\[([\w.]+)\]$", line)
        if m:
            cur = d
            for part in m.group(1).split("."):
                cur = cur.setdefault(part, {})
            continue
        m = re.match(r'^(\w+)\s*=\s*"([^"]*)"$', line)
        if m:
            (cur if cur is not None else d)[m.group(1)] = m.group(2)
            continue
        m = re.match(r"^(\w+)\s*=\s*(\d+)$", line)
        if m:
            (cur if cur is not None else d)[m.group(1)] = int(m.group(2))
            continue
        m = re.match(r"^(\w+)\s*=\s*\[(.*)\]$", line)
        if m:
            items = [s.strip().strip('"') for s in m.group(2).split(",") if s.strip()]
            (cur if cur is not None else d)[m.group(1)] = items
    return d


_TABLE = None


def table():
    global _TABLE
    if _TABLE is None:
        _TABLE = _load()
    return _TABLE


def kinds():
    return sorted(table().get("kinds", {}).keys())


def is_low(work=None):
    work = work or os.environ.get("HAKUX_WORK", "/home/justin/hakux-work")
    return os.path.exists(os.path.join(work, "usage", "low-active"))


def dial(name, work=None):
    """A [usage] value by name (e.g. "low_pct"). No limits.env override: the
    table is the single point now."""
    return table()["usage"][name]


def _ladder():
    t = table()
    ids = t["models"]
    names = ids["ladder"]
    return [ids[n] for n in names]


def ladder_step(model_id):
    """One rung up (haiku -> sonnet -> opus); already at the top, or not on
    the ladder at all, passes through unchanged."""
    rungs = _ladder()
    if model_id not in rungs:
        return model_id
    i = rungs.index(model_id)
    return rungs[min(i + 1, len(rungs) - 1)]


def cap_at_sonnet(model_id):
    """Low's hard ceiling: an escalated pick above Sonnet comes back down to
    it. Sonnet and Haiku are untouched -- Low does not push Haiku UP."""
    t = table()
    opus, sonnet = t["models"]["opus"], t["models"]["sonnet"]
    return sonnet if model_id == opus else model_id


def model_for(kind, escalate=False, work=None):
    """The model for one kind of work (a models.toml [kinds.*] row), under
    whichever mode (Normal/Low) is active now."""
    t = table()
    row = t["kinds"][kind]
    low = is_low(work)
    base = t["models"][row["low" if low else "normal"]]
    if escalate:
        base = ladder_step(base)
        if low:
            base = cap_at_sonnet(base)
    return base


def model_ids():
    return set(_ladder())


def resolve(token, escalate=False, work=None):
    """<token> is a kind name (looked up in the table) or a bare legacy
    model id ($WORK/briefs/<lane>.model, 77 files predating this table) --
    either way, Low and escalation apply the same."""
    if token in model_ids():
        base = token
        if escalate:
            base = ladder_step(base)
        if is_low(work):
            base = cap_at_sonnet(base)
        return base
    return model_for(token, escalate=escalate, work=work)


def main(argv):
    if not argv:
        sys.stderr.write(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    escalate = "--escalate" in rest
    rest = [a for a in rest if a != "--escalate"]
    if cmd == "model":
        print(model_for(rest[0], escalate=escalate))
    elif cmd == "resolve":
        print(resolve(rest[0], escalate=escalate))
    elif cmd == "dial":
        print(dial(rest[0]))
    elif cmd == "low":
        return 0 if is_low() else 1
    elif cmd == "kinds":
        print("\n".join(kinds()))
    else:
        sys.stderr.write("models.py: unknown command %r\n" % cmd)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
