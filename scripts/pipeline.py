# -*- coding: utf-8 -*-
"""One-shot pipeline orchestrator: audit -> build -> auto-fix -> final QC.

Runs the whole batch silently and internally:
  1. Global segment audit (overlap = fatal, exits 2 BEFORE rendering anything)
  2. Build every clip
  3. QC every clip (specs + loudness); auto-fix failures:
       - bitrate < min-vbr  -> rebuild with CRF-1 (up to --retries times)
       - still failing      -> rebuild with CRF-1 again, then report as FAILED
  4. Print a single final summary. Only clips that PASS everything reach it.

Usage:
  python pipeline.py <project.json> [--min-vbr 2500] [--retries 2] [--frames outdir]
Exit codes: 0 = all pass; 2 = audit overlap; 1 = some clips failed after retries.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import build_clip


def qc_one(path, min_vbr, size='720x1280', max_mb=500):
    ff = common.get_ffmpeg()
    v = common.probe(path, ff)
    size_mb = os.path.getsize(path) / 1048576.0
    res = '%dx%d' % (v['width'], v['height'])
    vbr = v['bitrate_kbps'] or 0
    h264 = bool(v['vcodec'] and ('h264' in v['vcodec'].lower() or 'avc' in v['vcodec'].lower()))
    reasons = []
    if res != size:
        reasons.append('res=%s' % res)
    if not h264:
        reasons.append('codec=%s' % v['vcodec'])
    if not v['is_aac']:
        reasons.append('not-aac')
    if vbr < min_vbr:
        reasons.append('vbr=%dk' % vbr)
    if size_mb >= max_mb:
        reasons.append('size=%.0fMB' % size_mb)
    # loudness: only flag TOO QUIET output (original-audio clips peak near 0dB, that is normal)
    lv = common.subprocess_run([ff, '-i', path, '-map', '0:a', '-af', 'volumedetect',
                                '-f', 'null', '-'])
    m = re.search(r'max_volume: (-?[\d.]+) dB', lv)
    mean = re.search(r'mean_volume: (-?[\d.]+) dB', lv)
    peak = float(m.group(1)) if m else None
    mean_v = float(mean.group(1)) if mean else None
    if (peak is not None and peak < -10.0) or (mean_v is not None and mean_v < -30.0):
        reasons.append('quiet(peak=%s,mean=%s)' % (peak, mean_v))
    dur = v['duration']
    return reasons, vbr, dur, size_mb, peak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--min-vbr', type=int, default=2500)
    ap.add_argument('--retries', type=int, default=2)
    ap.add_argument('--frames', default=None, help='grab head/mid/tail frames of passers')
    a = ap.parse_args()

    proj = common.read_json(a.project)
    os.makedirs(proj['output_dir'], exist_ok=True)
    tts_meta = common.read_json(proj['tts_json']) if proj.get('tts_json') else {}
    segs_map = build_clip.all_segs_of(proj)

    # ---- 1. audit (fatal before rendering) ----
    flat = sorted((ep, a1, b1, n[:20]) for n, s in segs_map.items() for ep, a1, b1 in s)
    bad = []
    for i in range(len(flat)):
        ep1, a1, b1, n1 = flat[i]
        for j in range(i + 1, len(flat)):
            ep2, a2, b2, n2 = flat[j]
            if ep2 != ep1:
                break
            if a2 < b1 - 0.01:
                bad.append('ep%d %.2f-%.2f(%s) vs %.2f-%.2f(%s)'
                           % (ep1, a1, b1, n1, a2, b2, n2))
    if bad:
        print('AUDIT FAILED — %d overlaps (fix the segment table; nothing was rendered):' % len(bad))
        for x in bad:
            print('  OVERLAP', x)
        sys.exit(2)
    print('AUDIT PASS — %d segments, 0 overlaps' % len(flat))

    # ---- 2. build all ----
    todo = dict(proj['clips'])
    done, results = {}, {}
    for name, cfg in proj['clips'].items():
        build_clip.build(name, cfg, proj, tts_meta)
        done[name] = cfg
        results[name] = {'crf': int(os.environ.get('CRF', str(proj.get('crf', 19))))}

    # ---- 3. qc + auto-fix loop ----
    crf = int(os.environ.get('CRF', str(proj.get('crf', 19))))
    for name, cfg in todo.items():
        out = os.path.join(proj['output_dir'], name + '.mp4')
        for attempt in range(a.retries + 1):
            reasons, vbr, dur, size_mb, peak = qc_one(out, a.min_vbr)
            if not reasons:
                results[name].update(vbr=vbr, dur=dur, peak=peak, status='PASS')
                break
            results[name].update(vbr=vbr, dur=dur, peak=peak,
                                 status='FIXING(%s)' % ','.join(reasons))
            if attempt == a.retries:
                results[name]['status'] = 'FAILED(%s)' % ','.join(reasons)
                break
            # auto-fix: lower CRF for bitrate; report others as-is after retry
            if any(r.startswith('vbr=') for r in reasons):
                crf = max(16, crf - 2)
                os.environ['CRF'] = str(crf)
                build_clip.build(name, cfg, proj, tts_meta)
                results[name]['crf'] = crf

    # ---- 4. single final summary ----
    npass = sum(1 for r in results.values() if r['status'] == 'PASS')
    print('\n' + '=' * 74)
    print('FINAL: %d/%d PASS' % (npass, len(results)))
    for name, r in results.items():
        print('%s  v=%dk peak=%sdB %.1fs crf=%s  %s'
              % (name[:62], r.get('vbr', 0), r.get('peak'), r.get('dur') or 0,
                 r.get('crf'), r['status']))
    if a.frames:
        os.makedirs(a.frames, exist_ok=True)
        ff = common.get_ffmpeg()
        for name, r in results.items():
            if r['status'] != 'PASS':
                continue
            p = os.path.join(proj['output_dir'], name + '.mp4')
            tag = re.sub(r'[^\w\-]', '_', name[:24])
            for t, lab in ((1.0, 'head'), ((r.get('dur') or 60) * 0.5, 'mid'),
                           ((r.get('dur') or 60) - 1.0, 'tail')):
                common.subprocess_run([ff, '-v', 'error', '-ss', '%.1f' % t, '-i', p,
                                       '-frames:v', '1', '-q:v', '4', '-y',
                                       os.path.join(a.frames, '%s_%s.jpg' % (tag, lab))])
    sys.exit(0 if npass == len(results) else 1)


if __name__ == '__main__':
    main()
