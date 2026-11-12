# -*- coding: utf-8 -*-
"""Stage 3a: scene-cut detection (shot boundaries) per episode.

Output: one txt per episode with cut timestamps (pts_time), used to snap
clip-segment boundaries to real shot changes (no mid-shot jumps).

Usage:
  python scene_cuts.py <video_dir> <out_dir> [--pattern "第%02d集.mp4"] \
      [--start 1] [--max 30] [--threshold 0.30]
"""
import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video_dir')
    ap.add_argument('out_dir')
    ap.add_argument('--pattern', default='第%02d集.mp4')
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--max', type=int, default=30)
    ap.add_argument('--threshold', type=float, default=0.30,
                    help='0.30 for live-action; lower to 0.15 for AI/soft cuts')
    a = ap.parse_args()
    ff = common.get_ffmpeg()
    os.makedirs(a.out_dir, exist_ok=True)

    total = 0
    for i in range(a.start, a.max + 1):
        src = common.episode_path(a.video_dir, i, a.pattern)
        if not src:
            continue
        r = [ff, '-hide_banner', '-i', src, '-vf',
             "select='gt(scene,%.2f)',showinfo" % a.threshold, '-f', 'null', '-']
        p = common.subprocess_run(r)
        cuts = re.findall(r'pts_time:([\d.]+)', p)
        out = os.path.join(a.out_dir, 'ep%02d.txt' % i)
        with io.open(out, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cuts))
        total += len(cuts)
        print('ep%02d: %d cuts' % (i, len(cuts)))
    print('total cuts: %d (dir: %s)' % (total, a.out_dir))


if __name__ == '__main__':
    main()
