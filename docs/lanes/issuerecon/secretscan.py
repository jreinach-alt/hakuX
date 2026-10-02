#!/usr/bin/env python3
"""secretscan.py DIR [--redact]: look for credentials in every string of DIR/issues/*.json.

Never prints a value: a hit is shown as its kind, its place (number / comment id / field) and a masked
context with the value replaced by [VALUE len=N]. --redact replaces each hit of a redacting kind with
[REDACTED:<kind>] in place and writes DIR/redactions.json (place and kind only).
"""
import glob, json, math, os, re, sys

STRONG = [
    ('github-token', r'\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{30,}\b'),
    ('github-pat', r'\bgithub_pat_[A-Za-z0-9_]{20,}\b'),
    ('aws-key', r'\bAKIA[0-9A-Z]{16}\b'),
    ('slack-token', r'\bxox[abpr]-[A-Za-z0-9-]{10,}\b'),
    ('private-key', r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)'),
    ('anthropic-key', r'\bsk-ant-[A-Za-z0-9_-]{20,}'),
    ('api-key', r'\bsk-[A-Za-z0-9]{32,}\b'),
]
ASSIGN = re.compile(r'(?i)\b(password|passwd|passphrase|pwd|secret|token|api[_-]?key|storePassword|keyPassword|'
                    r'ftp_pass|ftppass|auth)\b(["\']?\s*[:=]\s*["\']?)([^\s"\'`,;)]+)')
URLCRED = re.compile(r'\b[a-z][a-z0-9+.-]*://([^/\s:@]+):([^/\s@]+)@')
PLACEHOLDER = re.compile(r'^(\*+|<[^>]*>|\$\{?\w+\}?|\[?redacted\]?|x+|\.\.\.|none|null|true|false|""|\'\'|'
                         r'required|optional|env|file|yes|no|\d{1,3}|[a-z_]+\(|os\.environ.*)$', re.I)
TOKENISH = re.compile(r'[A-Za-z0-9+/_=-]{28,}')


def entropy(s):
    from collections import Counter
    c = Counter(s)
    return -sum(v / len(s) * math.log2(v / len(s)) for v in c.values())


def suspicious_token(t):
    if re.fullmatch(r'[0-9a-f]{7,64}', t) or re.fullmatch(r'[0-9]+', t) or \
            re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', t):
        return False                                   # shas, ids
    if '/' in t and re.search(r'[a-z]{3,}/[a-z]{3,}', t):
        return False                                   # paths
    if re.fullmatch(r'[A-Za-z_-]+', t) or re.fullmatch(r'[a-z0-9_-]+', t) or re.fullmatch(r'[A-Z0-9_-]+', t):
        return False                                   # identifiers, words joined by - or _
    classes = sum(bool(re.search(p, t)) for p in ('[a-z]', '[A-Z]', '[0-9]'))
    return classes == 3 and entropy(t) >= 4.3


def hits_in(s):
    out = []
    for kind, rx in STRONG:
        for m in re.finditer(rx, s):
            out.append((kind, m.start(), m.end(), True))
    for m in ASSIGN.finditer(s):
        v = m.group(3)
        if not PLACEHOLDER.match(v) and len(v) >= 4:
            out.append(('assignment:' + m.group(1).lower(), m.start(3), m.end(3), True))
    for m in re.finditer(r'(?i)\blog(?:in|ged in)\b[^.\n]{0,40}?\bas\s+([^\s/`]+/[^\s.,;`]+)', s):
        out.append(('login-credential', m.start(1), m.end(1), True))
    for m in URLCRED.finditer(s):
        if not PLACEHOLDER.match(m.group(2)):
            out.append(('url-credential', m.start(2), m.end(2), True))
    for m in TOKENISH.finditer(s):
        if suspicious_token(m.group(0)):
            out.append(('high-entropy', m.start(), m.end(), False))
    if re.search(r'(?i)key\.properties|hakux-release\.jks|\.jks\b|keystore', s):
        for m in re.finditer(r'(?i)key\.properties|hakux-release\.jks|\.jks\b|keystore', s):
            out.append(('keystore-mention', m.start(), m.end(), False))
    return out


def walk(d, path=()):
    if isinstance(d, str):
        yield path, d
    elif isinstance(d, dict):
        for k, v in d.items():
            yield from walk(v, path + (k,))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            yield from walk(v, path + (i,))


def setp(d, path, v):
    for p in path[:-1]:
        d = d[p]
    d[path[-1]] = v


def main():
    root = sys.argv[1]
    redact = '--redact' in sys.argv
    allow = set()
    ap = os.path.join(root, 'secretscan-allow.json')
    if os.path.exists(ap):
        allow = set(json.load(open(ap)))       # masked-context hashes judged not secret
    log = []
    for f in sorted(glob.glob(os.path.join(root, 'issues', '*.json')), key=lambda p: int(os.path.basename(p)[:-5])):
        d = json.load(open(f))
        changed = False
        for path, s in list(walk(d)):
            if path and (path[0] == 'sources' or str(path[-1]).endswith('source')):
                continue                       # provenance strings this tool wrote (transcript paths)
            hs = hits_in(s)
            if not hs:
                continue
            place = [d['number']]
            if path and path[0] == 'comments':
                place.append('comment %s' % (d['comments'][path[1]].get('id') or 'idx%d' % path[1]))
            place.append('.'.join(str(p) for p in path))
            new = s
            for kind, a, b, red in sorted(hs, key=lambda h: -h[1]):
                ctx = s[max(0, a - 50):a] + '[VALUE len=%d]' % (b - a) + s[b:b + 30]
                key = '%s|%s' % (kind, re.sub(r'\s+', ' ', ctx))
                import hashlib
                hk = hashlib.sha256((key + s[a:b]).encode()).hexdigest()[:16]
                if hk in allow:
                    continue
                log.append({'place': place, 'kind': kind, 'redact': red, 'ctx': re.sub(r'\s+', ' ', ctx), 'key': hk})
                if redact and red:
                    new = new[:a] + '[REDACTED:%s]' % kind + new[b:]
            if new != s:
                setp(d, path, new)
                changed = True
        if changed:
            with open(f, 'w') as fh:
                json.dump(d, fh, indent=1, ensure_ascii=False)
                fh.write('\n')
    for h in log:
        print('%-22s %-5s %s :: %s  [%s]' % (h['kind'], 'RED' if h['redact'] else 'look', ' / '.join(map(str, h['place'])), h['ctx'], h['key']))
    if redact:
        json.dump([{'place': h['place'], 'kind': h['kind']} for h in log if h['redact']],
                  open(os.path.join(root, 'redactions.json'), 'w'), indent=1)
    print('hits', len(log), 'redacting', sum(1 for h in log if h['redact']))


if __name__ == '__main__':
    main()
