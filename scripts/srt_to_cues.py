# -*- coding: utf-8 -*-
"""Stage 1b: SRT -> cue table (index [start-end] text) for episode planning.

Usage:
  python srt_to_cues.py <sub_dir> <out_txt> [--pattern "第%02d集.srt"] [--max 18]
"""
import argparse
import io
import os
import re
import sys


def ts(s):
    s = s.replace(',', '.')
    h, m, rest = s.split(':')
    return round(int(h) * 3600 + int(m) * 60 + float(rest), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sub_dir')
    ap.add_argument('out')
    ap.add_argument('--pattern', default='第%02d集.srt')
    ap.add_argument('--max', type=int, default=999)
    ap.add_argument('--start', type=int, default=1)
    a = ap.parse_args()

    out = io.open(a.out, 'w', encoding='utf-8')
    n = 0
    for i in range(a.start, a.max + 1):
        p = os.path.join(a.sub_dir, a.pattern % i)
        if not os.path.exists(p):
            continue
        n += 1
        t = io.open(p, encoding='utf-8-sig', errors='replace').read()
        out.write('==== EP%02d ====\n' % i)
        for b in re.split(r'\n\s*\n', t.strip()):
            L = [x.strip() for x in b.splitlines() if x.strip()]
            if len(L) >= 3 and '-->' in L[1]:
                s, e = L[1].split('-->')
                out.write('%s [%.2f-%.2f] %s\n' % (L[0], ts(s.strip()), ts(e.strip()), ' '.join(L[2:])))
    out.close()
    print('cues written for %d episodes -> %s' % (n, a.out))


if __name__ == '__main__':
    main()
