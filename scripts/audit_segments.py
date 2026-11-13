# -*- coding: utf-8 -*-
"""Stage 3b: GLOBAL segment uniqueness audit — run before rendering anything.

Reads a clips JSON (same schema as build_clip.py) and checks that no footage
range is reused across clips. Exits 2 on any overlap.
Also checks EPISODE COVERAGE: if project.json has "all_episodes": [1,...,N],
every listed episode must appear in at least one segment (user rule
2026-11-13: every provided episode must be used). Exits 3 if any missing.

Usage:
  python audit_segments.py <project.json>
Project clips schema (either form):
  pinjie:  {"type":"pinjie","segs":[[ep,a,b],...]}
  jieping: {"type":"jieping","narr_id":"d1","lines":[[ep,anchor],...],
            "ends":{"lineIdx":end},"bonus":[[lineIdx,[ep,a,b]],...],"tail":2.3}
  + optional "tts_json": path to durations.json (needed for jieping lengths)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def resolve_segs(cfg, tts_meta):
    if cfg['type'] == 'pinjie':
        return [tuple(s) for s in cfg['segs']]
    d = tts_meta[cfg['narr_id']]
    tail = cfg.get('tail', 2.3)
    ends = {int(k): v for k, v in cfg.get('ends', {}).items()}
    bonus = {int(i): tuple(b) for i, b in cfg.get('bonus', [])}
    segs = []
    for i, (ep, a) in enumerate(cfg['lines'], 1):
        dur = d[i - 1]['dur']
        segs.append((ep, a, ends.get(i, a + dur + tail)))
        if i in bonus:
            segs.append(bonus[i])
    return segs


def main():
    proj = common.read_json(sys.argv[1])
    tts_meta = {}
    tj = proj.get('tts_json')
    if tj and os.path.exists(tj):
        tts_meta = common.read_json(tj)
    clips = proj['clips']
    all_segs = []
    for name, cfg in clips.items():
        for ep, a, b in resolve_segs(cfg, tts_meta):
            all_segs.append((int(ep), float(a), float(b), name[:20]))
    all_segs.sort()
    bad = []
    for i in range(len(all_segs)):
        ep1, a1, b1, n1 = all_segs[i]
        for j in range(i + 1, len(all_segs)):
            ep2, a2, b2, n2 = all_segs[j]
            if ep2 != ep1:
                break
            if a2 < b1 - 0.01:
                bad.append('ep%d %.2f-%.2f(%s) vs %.2f-%.2f(%s)'
                           % (ep1, a1, b1, n1, a2, b2, n2))
    print('=== GLOBAL AUDIT: %d segments, %d overlaps' % (len(all_segs), len(bad)))
    for x in bad:
        print('  OVERLAP', x)

    # --- episode coverage check (user rule: every provided episode must be used) ---
    need = proj.get('all_episodes')
    if need:
        used = sorted({s[0] for s in all_segs})
        missing = [e for e in need if e not in used]
        extra = [e for e in used if e not in need]
        print('=== EPISODE COVERAGE: used %d/%d eps %s'
              % (len(used), len(need), used))
        for e in missing:
            print('  MISSING ep%d (provided but unused — add a segment)' % e)
        if extra:
            print('  NOTE eps outside all_episodes: %s' % extra)
        if missing:
            sys.exit(3)

    if bad:
        sys.exit(2)
    print('AUDIT PASS')


if __name__ == '__main__':
    main()
