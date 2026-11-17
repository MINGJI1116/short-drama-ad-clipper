# -*- coding: utf-8 -*-
"""Stage 3 (dialogue-block mode): speech-safe segment planning.

User rules 2026-11-17: cut ONLY at speech gaps (句尾 >=0.45s / 句头 >=0.25s),
tail hold +1.2s after the last subtitle, blocks stay dialogue-complete,
<=2 xfade per clip, ~2min per clip, every episode used, global uniqueness.

Inputs (in <workdir>):
  cues.txt      output of srt_to_cues.py
  ep_dur.json   {"1": 52.08, ...} measured durations (ffmpeg -i, no ffprobe)
  old_narr.json {"d1": {"lines": [[ep, anchor], ...], ...}, ...}   optional
  assets/tts/durations.json   regenerated TTS meta (file/dur/text per line)
  plan_spec.json  hand-designed run boundaries (see schema below)

plan_spec.json schema:
{
  "runs":   {"01": [["1", 0.0, 52.06], ...], ...},   # clip order preserved
  "smooth": {"01": [2], ...},                        # xfade AFTER segment i
  "ep_range": {"01": "1--2", ...},                   # filename episode field
  "narr": [{"prefix": "08", "narr_id": "d1", "target": 115.0}, ...],
  "fallback": ["5", "4", "7", ...]                   # anchor-overflow eps
}

Output: <workdir>/project.json (merged pinjie + jieping, audited).
"""
import json, os, re, sys

TAIL_HOLD = 1.2      # s after last subtitle (rule: smooth scene exits)
HEAD_PAD = 0.25      # lead-in before first subtitle of a run
TAIL_MIN = 0.05      # min tail when next cue is adjacent (zero-gap)
GAP_MIN = 0.8        # min free space to count as an insert slot

def load(work):
    d = lambda *p: os.path.join(work, *p)
    ep_dur = json.load(open(d('ep_dur.json'), encoding='utf-8'))
    cues, cur = {}, None
    for ln in open(d('cues.txt'), encoding='utf-8'):
        m = re.match(r'==== EP(\d+) ====', ln.strip())
        if m:
            cur = str(int(m.group(1))); cues[cur] = []; continue
        m = re.match(r'\d+ \[(\d+\.?\d*)-(\d+\.?\d*)\]', ln.strip())
        if m and cur is not None:
            a, b = float(m.group(1)), float(m.group(2))
            if b - a >= 0.15 and b <= ep_dur[cur] + 0.01:
                cues[cur].append((a, b))
    for e in cues:
        cues[e].sort()
    return ep_dur, cues

def speech_ok(ep, a, b, cues, ep_dur):
    bad = []
    if a > 0.01 and any(x < a - 1e-9 < y - HEAD_PAD for x, y in cues[ep]):
        bad.append('START-IN-SPEECH@%s' % a)
    if b < ep_dur[ep] - 0.02 and any(x + 0.45 < b < y - 1e-9 for x, y in cues[ep]):
        bad.append('END-IN-SPEECH@%s' % b)
    return bad

def build_pinjie(spec, cues, ep_dur):
    occ, out, ok = {}, {}, True
    for cid, runs in spec['runs'].items():
        segs, total, pe, pb = [], 0.0, None, None
        for ep, a, b in runs:
            ep = str(ep); a, b = round(a, 2), round(b, 2)
            errs = speech_ok(ep, a, b, cues, ep_dur)
            if b > ep_dur[ep] - 0.01: errs.append('EXCEED-EP-END')
            if pe == ep and a < pb: errs.append('ORDER/OVERLAP')
            if pe == ep and a - pb < 0.5: errs.append('MICRO-CUT<0.5s')
            if errs: ok = False; print(' c%s ep%s %s' % (cid, ep, errs))
            segs.append([int(ep), a, b]); total += b - a
            occ.setdefault(ep, []).append((a, b)); pe, pb = ep, b
        flag = '' if 110 <= total <= 122 and 3 <= len(segs) <= 9 else '  <-- CHECK'
        print('c%s segs=%d story=%.1f total=%.1f%s'
              % (cid, len(segs), total, total + 3, flag))
        out[cid] = segs
    # global uniqueness + coverage
    for cid, segs in out.items():
        for ep, a, b in segs:
            for x, y in occ.get(str(ep), []):
                if a < y - 1e-6 and x < b - 1e-6 and (cid, a, b) != ():
                    pass  # same-clip self pairs skipped via occ built once
    seen = {}
    clash = False
    for cid, segs in out.items():
        for ep, a, b in segs:
            for (c2, x, y) in seen.get(str(ep), []):
                if a < y - 1e-6 and x < b - 1e-6:
                    clash = True; print(' PINJIE-CLASH', cid, c2, ep, (x, y), (a, b))
            seen.setdefault(str(ep), []).append((cid, a, b))
    if clash: ok = False
    missing = [e for e in range(1, max(int(k) for k in ep_dur) + 1)
               if str(e) not in seen]
    if missing: ok = False; print(' EP MISSING:', missing)
    print('pinjie audit:', 'OK' if ok else 'FAIL')
    return out, occ, ok

def free_slots(ep, oc, ep_dur):
    out, t = [], 0.0
    for a, b in sorted(oc.get(ep, [])):
        if a - t >= GAP_MIN: out.append((t, a))
        t = max(t, b)
    if ep_dur[ep] - t >= GAP_MIN: out.append((t, ep_dur[ep]))
    return out

def fmt_eps(eps):
    """Episode list -> name segment: consecutive runs 'a--b', jumps '-'
    (user rule: 19-20-21-22 must render as 19--22, never 19-20-21-22)."""
    eps = sorted(set(eps)); out = []; i = 0
    while i < len(eps):
        j = i
        while j + 1 < len(eps) and eps[j + 1] == eps[j] + 1:
            j += 1
        out.append(str(eps[i]) if i == j else '%d--%d' % (eps[i], eps[j]))
        i = j + 1
    return '-'.join(out)

def alloc_narr(spec, occ, ep_dur, work, proj=None):
    import json as J
    tts = J.load(open(os.path.join(work, 'assets/tts/durations.json'), encoding='utf-8'))
    # ---- clean-master check: a jieping anchor on an episode whose NOSUB
    # master is missing dies mid-render ("file: Invalid argument"). The cheng
    # (subtitled) file is NOT a substitute for narration clips. Restrict all
    # narration anchors + fallback episodes to episodes with clean masters.
    nosub = (proj or {}).get('nosub_dir') or spec.get('nosub_dir')
    pat = ((proj or {}).get('episode_pattern') or spec.get('episode_pattern')
           or '第{ep:02d}集.mp4').replace('{ep:02d}', '%02d').replace('{ep}', '%d')
    clean = None
    if nosub and os.path.isdir(nosub):
        clean = {e for e in ep_dur if os.path.exists(os.path.join(nosub, pat % int(e)))}
        dirty = sorted(set(ep_dur) - clean, key=int)
        if dirty:
            print('  NO NOSUB MASTER for eps %s — narration anchors/fallback '
                  'excluded them' % dirty)
    old = {}
    p = os.path.join(work, 'old_narr.json')
    if os.path.exists(p):
        old = J.load(open(p, encoding='utf-8'))
    oc = {k: list(v) for k, v in occ.items()}
    clips, ok = {}, True
    for item in spec.get('narr', []):
        nid, pref, tgt = item['narr_id'], item['prefix'], item.get('target', 115.0)
        src = old.get(nid) or item
        meta = tts[nid]
        assert len(src['lines']) == len(meta), nid
        speech = sum(m['dur'] for m in meta)
        g = min(2.0, max(1.2, (tgt - speech) / len(meta)))
        lines, ends, eps = [], {}, []
        fb_list = [e for e in spec.get('fallback', [])
                   if clean is None or e in clean]
        for i, ((ep0, a), m) in enumerate(zip(src['lines'], meta), 1):
            ep, a = str(ep0), float(a)
            need = m['dur'] + g
            if clean is not None and ep not in clean:
                ep = None  # force fallback path below
            start = None
            if ep is not None:
                start = next((round(a, 2) for fa, fb in free_slots(ep, oc, ep_dur)
                              if fa - 0.05 <= a <= fb - need), None)
                if start is None:
                    start = next((max(fa, 0.05) for fa, fb in
                                  free_slots(ep, oc, ep_dur) if fb - fa >= need), None)
            fbep = None
            if start is None:
                for fe in fb_list:
                    s2 = next((max(fa, 0.05) for fa, fb in
                               free_slots(fe, oc, ep_dur) if fb - fa >= need), None)
                    if s2 is not None: start, ep, fbep = s2, fe, fe; break
            if start is None:
                ok = False; print(' NARR-NO-SPACE', nid, i); continue
            end = round(min(start + need, ep_dur[ep] - 0.05), 2)
            oc.setdefault(ep, []).append((start, end))
            lines.append([int(ep), start]); ends[str(i)] = end; eps.append(int(ep))
            if fbep: print('  %s L%02d ->ep%s (overflow)' % (nid, i, fbep))
        story = sum(ends[str(i)] - lines[i - 1][1] for i in range(1, len(lines) + 1))
        name = '%s_%s' % (pref, fmt_eps(eps))
        clips[nid] = {'name': name, 'cfg': {'type': 'jieping', 'narr_id': nid,
                      'tail': 2.3, 'lines': lines, 'ends': ends}}
        print('%s %s lines=%d speech=%.1f g=%.2f story=%.1f total=%.1f'
              % (pref, nid, len(lines), speech, g, story, story + 3))
    return clips, ok

def main():
    work = sys.argv[1] if len(sys.argv) > 1 else '.'
    base = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base)
    spec = json.load(open(os.path.join(work, 'plan_spec.json'), encoding='utf-8'))
    proj = json.load(open(os.path.join(base, '..', 'references',
                          'project_template.json'), encoding='utf-8')) \
        if os.path.exists(os.path.join(base, '..', 'references',
                                       'project_template.json')) else {}
    ep_dur, cues = load(work)
    pinjie, occ, ok = build_pinjie(spec, cues, ep_dur)
    narr, ok2 = alloc_narr(spec, occ, ep_dur, work, proj)
    for cid, segs in pinjie.items():
        name = 'PINJIE_%s' % cid
        if cid in spec.get('ep_range', {}):
            name = spec['ep_range'][cid]
        proj.setdefault('clips', {})['PINJIE_' + cid] = {
            'type': 'pinjie', 'segs': segs, 'nosnap': True,
            **({'smooth': {'fade': 0.4, 'at': spec['smooth'][cid]}}
               if cid in spec.get('smooth', {}) else {})}
    for nid, item in narr.items():
        proj.setdefault('clips', {})['NARR_' + nid] = item['cfg']
    json.dump(proj, open(os.path.join(work, 'project.json'), 'w',
              encoding='utf-8'), ensure_ascii=False, indent=1)
    print('project.json written:', len(proj['clips']), 'clips;',
          'AUDIT', 'OK' if (ok and ok2) else 'FAIL')

if __name__ == '__main__':
    main()
