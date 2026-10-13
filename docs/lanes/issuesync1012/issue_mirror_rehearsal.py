#!/usr/bin/env python3
"""issue_mirror_rehearsal.py -- lane.issuesync1012 round 3, "the proof: a rehearsal on a live snapshot".

Snapshots live GitHub (through the staged gateway copy, read-only `get --out`) and the live forge
(read-only curl via FG()) into in-memory structures, loads them -- deep-copied -- into write-counting
fakes (FakeGH/FakeFG, reused from issue_mirror_selftest.py), and replays the real issue_mirror.py code
entirely in memory: seed --yes -> backfill --yes (all) -> sync --yes -> dry-run sync -> check. Pacing
sleeps are patched to a no-op. State/lock/log files are redirected to a scratch temp dir for the
duration (see `isolated()` in the selftest module), so this script never touches the real persisted
baseline, and never makes a single GitHub or forge WRITE of any kind: the fakes hold the snapshot in
plain dicts, there is no subprocess, no curl, no socket, anywhere past the snapshot step.

Then it applies one synthetic edit per field (title, body, state, labels, a comment) on each side, to
ten distinct plain (non-PR-kind) common pairs, and re-syncs: the next sync must make exactly one write
per edit, in the right direction; the run after that must make zero.

Usage: python3 issue_mirror_rehearsal.py
Exit 0 if every required count held; exit 1, with FAIL lines, otherwise.
"""
import contextlib
import copy
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import issue_mirror as im
from issue_mirror_selftest import FakeGH, FakeFG, isolated, silent

HERE = os.path.dirname(os.path.abspath(__file__))
STAGED_GATEWAY = os.path.join(HERE, 'github_gateway.py')

FAILURES = []


def require(cond, label):
    print(('  OK   ' if cond else '  FAIL ') + label)
    if not cond:
        FAILURES.append(label)


class RehearsalGH(FakeGH):
    """create() replicates the REAL gateway's two-HTTP-call shape for a closed-kind item:
    github_gateway.py's cmd_issue_create always POSTs open first (GitHub's create API has no state
    field), then, only if state=='closed', makes a SEPARATE patch call. A plain single-call fake would
    under-count backfill's real write cost by one per closed-kind item. This subclass exists only so
    the rehearsal counts that faithfully; the unit selftest doesn't need this fidelity and FakeGH
    itself stays simple."""
    def create(self, title, body='', labels=(), state=None):
        n = FakeGH.create(self, title, body, labels, state=None)
        if state == 'closed':
            self.patch(n, state='closed')
        return n


def snapshot_live():
    """Read-only. GitHub via the staged gateway copy (carries the /labels GET_OK fix this round
    added); the forge via FG() directly. No --yes anywhere, no write call of any kind. Only GitHub
    reads count against the gateway's daily budget; the forge is a local Forgejo instance with no
    such budget, so pull_detail is fetched for every backfill-range PR-kind forge item without
    worrying about cost."""
    gh_client = im.GH(gateway=STAGED_GATEWAY)
    fg_client = im.FG()
    print('snapshot: reading live GitHub (read-only, staged gateway copy)...')
    gh = gh_client.all_issues()
    gh_labels = gh_client.repo_labels()
    print('snapshot: %d live GitHub item(s), %d GitHub repo label(s)' % (len(gh), len(gh_labels)))
    print('snapshot: reading live forge (read-only curl)...')
    fg = fg_client.all_issues()
    print('snapshot: %d live forge item(s)' % len(fg))
    d = im.build_diff(gh, fg)
    pr_backfill_nums = [n for n in d['backfill'] if im.kind_of(fg[n]) == 'PR']
    print('snapshot: reading pull_detail for %d backfill-range forge PR(s) (read-only, local forge)...' %
          len(pr_backfill_nums))
    pulls = {n: fg_client.pull_detail(n) for n in pr_backfill_nums}
    return gh, gh_labels, fg, pulls


def load_into_fakes(gh, gh_labels, fg, pulls):
    gh_f = RehearsalGH()
    gh_f.items = copy.deepcopy(gh)
    gh_f.repo_labels_list = copy.deepcopy(gh_labels)
    fg_f = FakeFG()
    fg_f.items = copy.deepcopy(fg)
    fg_f.pulls = copy.deepcopy(pulls)
    return gh_f, fg_f


def closed_kind_count(fg_f, todo):
    """Mirrors build_backfill_body's own rule: PR-kind backfill items are ALWAYS closed (gap 3's
    unified PR-twin shape); plain issue-kind items are closed only if the forge item itself is
    closed."""
    n = 0
    for num in todo:
        item = fg_f.items[num]
        if im.kind_of(item) == 'PR' or item['state'] == 'closed':
            n += 1
    return n


def pick_plain_pairs(gh_f, fg_f, n_generic, n_zero_comment_gh, n_zero_comment_fg):
    """Picks n_generic distinct plain (non-PR-kind) common pairs for the title/body/state/labels edits, plus
    separate pairs for the comment edits. The comment-edit pairs specifically need comments==0 on the relevant
    side at snapshot time: the fake's comments_store is seeded fresh (it never carries the live snapshot's real
    historical comment bodies, only the one synthetic comment this script adds), so sync_comments' `[prev_gh:]`
    slice only lines up when prev_gh (the live comment COUNT at snapshot time) is 0 -- otherwise it would slice
    past the one synthetic entry and see nothing, which is a rehearsal-harness artifact, not a tool defect."""
    d = im.build_diff(gh_f.items, fg_f.items)
    excluded = set(im.NEVER_SYNC) | set(im.STATE_CONFLICT_NUMS) | set(im.CONTENT_FIX_NUMS)
    cands = [n for n in d['common'] if n not in excluded and im.kind_of(fg_f.items[n]) != 'PR']
    used = set()
    generic = cands[:n_generic]
    used.update(generic)
    zero_gh = [n for n in cands if n not in used and gh_f.items[n].get('comments', 0) == 0][:n_zero_comment_gh]
    used.update(zero_gh)
    zero_fg = [n for n in cands if n not in used and fg_f.items[n].get('comments', 0) == 0][:n_zero_comment_fg]
    used.update(zero_fg)
    return generic, zero_gh, zero_fg


def run():
    with isolated():
        print('=== snapshot (live, read-only) ===')
        gh, gh_labels, fg, pulls = snapshot_live()
        gh_f, fg_f = load_into_fakes(gh, gh_labels, fg, pulls)

        old_sleep = im.time.sleep
        im.time.sleep = lambda s: None   # patch out backfill's pacing gap for the whole rehearsal
        try:
            d0 = im.build_diff(gh_f.items, fg_f.items)
            todo = d0['backfill']

            # --- 1. seed --yes ---
            print('\n=== step: seed --yes ===')
            expected_closes = len([n for n in im.STATE_CONFLICT_NUMS if n in fg_f.items])
            expected_fix = len([n for n in im.CONTENT_FIX_NUMS if n in gh_f.items and n in fg_f.items])
            before_fg, before_gh = fg_f.write_calls, gh_f.write_calls
            rc, out = silent(im.cmd_seed, gh_f, fg_f, True)
            sys.stdout.write(out)
            seed_fg = fg_f.write_calls - before_fg
            seed_gh = gh_f.write_calls - before_gh
            summary = [l for l in out.splitlines() if l.startswith('seed: baseline written')]
            print('SUMMARY: ' + (summary[0] if summary else '(no summary line found)'))
            require(seed_fg == expected_closes + expected_fix,
                    'seed: exactly %d forge writes (brief: 25; got %d)' % (expected_closes + expected_fix, seed_fg))
            require(seed_gh == 0, 'seed: 0 GitHub writes (got %d)' % seed_gh)

            # --- 2. backfill --yes (all) ---
            print('\n=== step: backfill --yes (all) ===')
            expected_creates = len(todo)
            expected_closed = closed_kind_count(fg_f, todo)
            expected_gh_writes = expected_creates + expected_closed
            before_fg, before_gh_create, before_gh_write = fg_f.write_calls, gh_f.create_calls, gh_f.write_calls
            rc, out = silent(im.cmd_backfill, gh_f, fg_f, True, 0, 999999, False)
            sys.stdout.write(out)
            bf_creates = gh_f.create_calls - before_gh_create
            bf_gh_writes = gh_f.write_calls - before_gh_write
            bf_fg_writes = fg_f.write_calls - before_fg
            summary = [l for l in out.splitlines() if l.startswith('backfill:')]
            print('SUMMARY: ' + (summary[-1] if summary else '(no summary line found; rc=%d)' % rc))
            require(bf_creates == expected_creates,
                    'backfill: GitHub creates == backfill count (%d, got %d)' % (expected_creates, bf_creates))
            require(bf_gh_writes == expected_gh_writes,
                    'backfill: GitHub writes == creates + closes (%d creates + %d closes = %d, got %d)' %
                    (expected_creates, expected_closed, expected_gh_writes, bf_gh_writes))
            require(bf_fg_writes == 0, 'backfill: 0 forge writes (got %d)' % bf_fg_writes)

            # --- pre-leveling mirror-down (informational; not one of the brief's required-zero counts) ---
            print('\n=== step: mirror-down (pre-leveling, informational) ===')
            only_gh_before = im.build_diff(gh_f.items, fg_f.items)['only_gh']
            before_fg = fg_f.write_calls
            rc, out = silent(im.cmd_mirror_down, gh_f, fg_f, True)
            sys.stdout.write(out)
            md_fg_writes = fg_f.write_calls - before_fg
            print('SUMMARY: mirror-down drained %d GitHub-only number(s), %d forge write(s) '
                  '(not a round-3 required-zero count -- a genuine new GitHub issue filed since '
                  'the forge last caught up is expected leveling, not drift)' %
                  (len(only_gh_before), md_fg_writes))

            # --- 3. sync --yes (first, after seed + backfill + mirror-down) ---
            print('\n=== step: sync --yes (first) ===')
            before_gh, before_fg = gh_f.write_calls, fg_f.write_calls
            rc, out = silent(im.cmd_sync, gh_f, fg_f, True)
            sys.stdout.write(out)
            sync1_gh = gh_f.write_calls - before_gh
            sync1_fg = fg_f.write_calls - before_fg
            summary = [l for l in out.splitlines() if l.startswith('sync:')]
            print('SUMMARY: ' + (summary[0] if summary else '(no summary line found)'))
            require(sync1_gh == 0, 'first sync --yes: 0 GitHub writes (got %d)' % sync1_gh)
            require(sync1_fg == 0, 'first sync --yes: 0 forge writes (got %d)' % sync1_fg)

            # --- 4. dry-run sync ---
            print('\n=== step: sync (dry run) ===')
            before_gh, before_fg = gh_f.write_calls, fg_f.write_calls
            rc, out = silent(im.cmd_sync, gh_f, fg_f, False)
            sys.stdout.write(out)
            dry_gh = gh_f.write_calls - before_gh
            dry_fg = fg_f.write_calls - before_fg
            m = re.search(r'(\d+) field actions, (\d+) conflicts', out)
            actions_n = int(m.group(1)) if m else -1
            conflicts_n = int(m.group(2)) if m else -1
            summary = [l for l in out.splitlines() if l.startswith('sync:')]
            print('SUMMARY: ' + (summary[0] if summary else '(no summary line found)'))
            require(actions_n == 0, 'dry-run sync: 0 actions (got %d)' % actions_n)
            require(conflicts_n == 0, 'dry-run sync: 0 conflicts (got %d)' % conflicts_n)
            require(dry_gh == 0 and dry_fg == 0,
                    'dry-run sync: 0 writes either side (got gh=%d fg=%d)' % (dry_gh, dry_fg))

            # --- check ---
            print('\n=== step: check ===')
            rc, out = silent(im.cmd_check, gh_f, fg_f)
            sys.stdout.write(out)
            print('SUMMARY: ' + out.strip().splitlines()[-1] if out.strip() else 'SUMMARY: (empty)')
            require('DRIFT' not in out, 'check: clean (no DRIFT line)')

            # --- synthetic edits: one per field, per side, on ten distinct plain pairs ---
            print('\n=== step: synthetic edits (one field each, 5 on GitHub, 5 on the forge) ===')
            generic, zero_gh, zero_fg = pick_plain_pairs(gh_f, fg_f, 8, 1, 1)
            require(len(generic) == 8, 'found 8 distinct plain common pairs for title/body/state/labels (got %d)' % len(generic))
            require(len(zero_gh) == 1, 'found a plain pair with 0 GitHub comments for the GitHub-side comment edit (got %d)' % len(zero_gh))
            require(len(zero_fg) == 1, 'found a plain pair with 0 forge comments for the forge-side comment edit (got %d)' % len(zero_fg))
            gh_shared = im.compute_shared_vocab(gh_f.repo_labels_list)
            p_title_gh, p_body_gh, p_state_gh, p_labels_gh, \
                p_title_fg, p_body_fg, p_state_fg, p_labels_fg = generic
            p_comment_gh = zero_gh[0]
            p_comment_fg = zero_fg[0]

            gh_f.items[p_title_gh]['title'] = gh_f.items[p_title_gh]['title'] + ' (edited on GitHub)'
            gh_f.items[p_body_gh]['body'] = (gh_f.items[p_body_gh].get('body') or '') + '\n\nedited on GitHub.'
            gh_f.items[p_state_gh]['state'] = 'closed' if gh_f.items[p_state_gh]['state'] == 'open' else 'open'
            cur_names = {l['name'] for l in gh_f.items[p_labels_gh].get('labels', [])}
            new_label = next((l for l in sorted(gh_shared) if l not in cur_names), None)
            require(new_label is not None, 'found a shared label to add on the GitHub side')
            if new_label:
                gh_f.items[p_labels_gh]['labels'] = list(gh_f.items[p_labels_gh].get('labels', [])) + [{'name': new_label}]
            gh_f.comment(p_comment_gh, 'synthetic edit: a new comment posted on GitHub.')

            fg_f.items[p_title_fg]['title'] = fg_f.items[p_title_fg]['title'] + ' (edited on the forge)'
            fg_f.items[p_body_fg]['body'] = (fg_f.items[p_body_fg].get('body') or '') + '\n\nedited on the forge.'
            fg_f.items[p_state_fg]['state'] = 'closed' if fg_f.items[p_state_fg]['state'] == 'open' else 'open'
            cur_names_fg = {l['name'] for l in fg_f.items[p_labels_fg].get('labels', [])}
            new_label_fg = next((l for l in sorted(gh_shared) if l not in cur_names_fg), None)
            require(new_label_fg is not None, 'found a shared label to add on the forge side')
            if new_label_fg:
                fg_f.items[p_labels_fg]['labels'] = list(fg_f.items[p_labels_fg].get('labels', [])) + [{'name': new_label_fg}]
            fg_f.comment(p_comment_fg, 'synthetic edit: a new comment posted on the forge.')

            print('edited: github side of #%d(title) #%d(body) #%d(state) #%d(labels +%s) #%d(comment)' %
                  (p_title_gh, p_body_gh, p_state_gh, p_labels_gh, new_label, p_comment_gh))
            print('edited: forge side of #%d(title) #%d(body) #%d(state) #%d(labels +%s) #%d(comment)' %
                  (p_title_fg, p_body_fg, p_state_fg, p_labels_fg, new_label_fg, p_comment_fg))

            print('\n=== step: sync --yes (after synthetic edits) ===')
            before_gh, before_fg = gh_f.write_calls, fg_f.write_calls
            rc, out = silent(im.cmd_sync, gh_f, fg_f, True)
            sys.stdout.write(out)
            edit_gh = gh_f.write_calls - before_gh
            edit_fg = fg_f.write_calls - before_fg
            summary = [l for l in out.splitlines() if l.startswith('sync:')]
            print('SUMMARY: ' + (summary[0] if summary else '(no summary line found)'))
            # github-side edits (title/body/state/labels/comment) -> written TO the forge (5)
            # forge-side edits (title/body/state/labels/comment) -> written TO github (5)
            require(edit_fg == 5, 'edit sync: exactly 5 forge writes (one per GitHub-side edit, got %d)' % edit_fg)
            require(edit_gh == 5, 'edit sync: exactly 5 GitHub writes (one per forge-side edit, got %d)' % edit_gh)
            require(gh_f.items[p_title_fg]['title'].endswith('(edited on the forge)') or
                    'edited on the forge' in (gh_f.items.get(p_title_fg) or {}).get('title', ''),
                    'forge-side title edit landed on GitHub #%d' % p_title_fg)
            require('edited on GitHub' in (fg_f.items.get(p_title_gh) or {}).get('title', ''),
                    'GitHub-side title edit landed on the forge #%d' % p_title_gh)

            print('\n=== step: sync --yes (settle, after the edit-sync) ===')
            before_gh, before_fg = gh_f.write_calls, fg_f.write_calls
            rc, out = silent(im.cmd_sync, gh_f, fg_f, True)
            sys.stdout.write(out)
            settle_gh = gh_f.write_calls - before_gh
            settle_fg = fg_f.write_calls - before_fg
            summary = [l for l in out.splitlines() if l.startswith('sync:')]
            print('SUMMARY: ' + (summary[0] if summary else '(no summary line found)'))
            require(settle_gh == 0 and settle_fg == 0,
                    'settle sync: 0 writes either side (got gh=%d fg=%d)' % (settle_gh, settle_fg))
        finally:
            im.time.sleep = old_sleep

    print('\n=== result ===')
    if FAILURES:
        print('issue_mirror_rehearsal: %d FAILURE(S):' % len(FAILURES))
        for f in FAILURES:
            print('  - ' + f)
        return 1
    print('issue_mirror_rehearsal: all required counts held')
    return 0


if __name__ == '__main__':
    sys.exit(run())
