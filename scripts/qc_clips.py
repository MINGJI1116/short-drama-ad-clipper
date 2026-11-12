# -*- coding: utf-8 -*-
"""Stage 6: five-dimension QC of output clips.

Checks specs (resolution/codec/bitrate/size) for every mp4 in the output dir,
measures audio loudness, and grabs head/mid/tail frames for visual review.

Usage:
  python qc_clips.py <output_dir> [--frames outdir] [--min-vbr 2500] [--size 720x1280]
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir')
    ap.add_argument('--frames', default=None)
    ap.add_argument('--min-vbr', type=int, default=2500)
    ap.add_argument('--size', default='720x1280')
    ap.add_argument('--max-mb', type=float, default=500)
    a = ap.parse_args()
    ff = common.get_ffmpeg()
    if a.frames:
        os.makedirs(a.frames, exist_ok=True)

    ok = True
    for name in sorted(os.listdir(a.outdir)):
        if not name.endswith('.mp4'):
            continue
        p = os.path.join(a.outdir, name)
        v = common.probe(p, ff)
        size_mb = os.path.getsize(p) / 1048576.0
        res = '%dx%d' % (v['width'], v['height'])
        vbr = v['bitrate_kbps'] or 0
        h264 = bool(v['vcodec'] and ('h264' in v['vcodec'].lower() or 'avc' in v['vcodec'].lower()))
        good = (res == a.size and h264 and v['is_aac']
                and size_mb < a.max_mb and vbr >= a.min_vbr - 150)
        ok &= good
        print('%-70s %6.1fMB %ss %s v=%dkbps aac=%s %s'
              % (name[:70], size_mb,
                 ('%.1f' % v['duration']) if v['duration'] else '?',
                 res, vbr, v['is_aac'], 'PASS' if good else 'CHECK'))
        # loudness
        lv = common.subprocess_run([ff, '-i', p, '-map', '0:a', '-af', 'volumedetect', '-f', 'null', '-'])
        m = re.search(r'max_volume: (-?[\d.]+) dB', lv)
        mean = re.search(r'mean_volume: (-?[\d.]+) dB', lv)
        if m:
            print('   audio: mean=%sdB max=%sdB%s'
                  % (mean.group(1) if mean else '?', m.group(1),
                     '' if -6.0 <= float(m.group(1)) <= -0.5 else '  <-- check level'))
        # frames: head / mid / tail
        if a.frames and v['duration']:
            tag = re.sub(r'[^\w\-]', '_', name[:24])
            for t, lab in ((1.0, 'head'), (v['duration'] * 0.5, 'mid'), (v['duration'] - 1.0, 'tail')):
                common.subprocess_run([ff, '-v', 'error', '-ss', '%.1f' % t, '-i', p,
                                       '-frames:v', '1', '-q:v', '4', '-y',
                                       os.path.join(a.frames, '%s_%s.jpg' % (tag, lab))])
    print('ALL PASS' if ok else 'SOME ITEMS NEED CHECK')


if __name__ == '__main__':
    main()
