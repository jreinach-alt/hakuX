#!/usr/bin/env python3
"""Arctic Thunder race reader for tcg424flip-arctic-nova.json (#424).

    python3 arcticread3.py <result-id-or-suffix> [...]

arcticread2.py loaded with one string swapped: the race-over sample is
gfps >= 55 instead of >= 45. The runs move to the Nova (owner, 2026-09-29
11:20 PDT), and no Arctic Thunder race has run there, so its race gfps is not
known. The results and menu screens run at 59-60 on the Thor; 55 still stops
the window at them, and leaves the Nova 20+ gfps of headroom over the Thor's
race (at most 34 in the four Thor runs on disk). Everything else, the columns
included, is arcticread2.py's.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, 'arcticread2.py')).read()
assert SRC.count('g >= 45') == 1, 'arcticread2.py changed: the race-end test is not where this expects it'
G = {'__file__': os.path.join(HERE, 'arcticread2.py'), '__name__': 'arcticread2'}
exec(compile(SRC.replace('g >= 45', 'g >= 55'), 'arcticread2.py', 'exec'), G)

if __name__ == '__main__':
    G['main']()
