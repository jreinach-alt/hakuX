#!/usr/bin/env python3
"""learned.py -- drive.py's cross-run memory of what to press on a screen it cannot
name (#433 Part C).

One JSONL record per press drive.py made while `state == "unknown"`:
{"title": <profile name>, "key": "unknown:<classify.py source>", "embedding": [...] or
null, "button": <what was pressed>, "outcome": "advanced"|"changed"|"regressed"|"none",
"t": <route seconds, 1dp>, "run": <drive.py --out dir's basename>}

`embedding` is pathclass's own pooled, L2-normalized SigLIP2 vector (classify.py's
`out["pathclass"]["embedding"]`, present whenever the pathclass branch ran) -- already
normalized, so a plain dot product between two of these IS their cosine similarity, no
numpy needed. A profile with no pathclass branch (a crop-only title, or this module's own
selftest) never gets one; `key` -- the exact state+source classify.py named the screen --
is the fallback match, used whenever either side has no embedding.

Every record goes to two files: `learned/<title>.jsonl` (this title only) and
`learned/_global.jsonl` (every title, read-only fallback for one this lane has never
seen before) -- `suggest()` is given both, title's own records ranked first.

VETO (owner, #433): a button that ever `regressed` a screen this close to this one is
never suggested again for it, no matter how many times another button `advanced` from
there. A raw count or a recency-only pick would let a bad-but-frequent answer outvote one
lesson that said "don't"."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "learned")
GLOBAL_PATH = os.path.join(DIR, "_global.jsonl")

OUTCOME_RANK = {"advanced": 3, "changed": 2, "none": 1}
SIM_BAR = 0.90  # cosine similarity floor for "the same screen" -- #433 Part D tunes this
                # against real GTA III / held-out frames; untuned here for lack of either.


def path_for(title):
    return os.path.join(DIR, "%s.jsonl" % title) if title else None


def _read(path):
    recs = []
    if not path or not os.path.exists(path):
        return recs
    with open(path) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except ValueError:
                # an append-only log a process could have been killed mid-write to; one
                # torn last line must not cost every record before it (#433 selftest
                # covers this with a deliberately truncated fixture).
                print("learned.py: %s:%d: not JSON, skipped" % (path, i + 1))
    return recs


def load(title):
    """This title's own records (ranked first by the caller) plus every title's."""
    return _read(path_for(title)), _read(GLOBAL_PATH)


def record(title, key, embedding, button, outcome, t, run):
    if outcome not in OUTCOME_RANK and outcome != "regressed":
        raise ValueError("learned.py: bad outcome %r" % outcome)
    rec = {"title": title, "key": key, "embedding": embedding, "button": button,
           "outcome": outcome, "t": round(t, 1), "run": run}
    os.makedirs(DIR, exist_ok=True)
    line = json.dumps(rec) + "\n"
    own = path_for(title)
    if own:
        with open(own, "a") as f:
            f.write(line)
    with open(GLOBAL_PATH, "a") as f:
        f.write(line)
    return rec


def cosine(a, b):
    if a is None or b is None or len(a) != len(b):
        return -1.0
    return sum(x * y for x, y in zip(a, b))


def _matches(records, key, embedding):
    out = []
    for rec in records:
        if embedding is not None and rec.get("embedding") is not None:
            if cosine(embedding, rec["embedding"]) >= SIM_BAR:
                out.append(rec)
        elif rec.get("key") == key:
            out.append(rec)
    return out


def suggest(own_records, global_records, key, embedding, tried):
    """The best button to press again for this screen, or None (nothing learned, or
    everything learned is either vetoed or already tried this visit -- the caller falls
    back to the next untried rung of the hardcoded explore ladder either way)."""
    for records in (own_records, global_records):
        matches = _matches(records, key, embedding)
        if not matches:
            continue
        by_button = {}
        for rec in matches:
            by_button.setdefault(rec["button"], []).append(rec["outcome"])
        vetoed = {b for b, outs in by_button.items() if "regressed" in outs}
        best, best_score = None, -1
        for b, outs in by_button.items():
            if b in vetoed or b in tried:
                continue
            score = max(OUTCOME_RANK.get(o, 0) for o in outs)
            if score > best_score:
                best, best_score = b, score
        if best is not None:
            return best
    return None
