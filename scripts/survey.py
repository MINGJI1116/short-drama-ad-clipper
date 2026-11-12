# -*- coding: utf-8 -*-
"""Stage 1: survey material directories.

Scans a folder tree for videos / audio / subtitles, probes specs, and prints
a JSON report + per-episode duration table. Use --frames to grab sample
frames (start/mid/end of the first video) for hard-subtitle / logo checks.

Usage:
  python survey.py <material_root> [--out report.json] [--frames outdir] [--deep]
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

VID_EXT = ('.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v', '.flv')
AUD_EXT = ('.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg')
SRT_EXT = ('.srt', '.ass', '.vtt')
IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--out', default=None, help='write JSON report here')
    ap.add_argument('--frames', default=None, help='grab sample frames of the first video here')
    ap.add_argument('--deep', action='store_true', help='probe every video (default: one per folder)')
    a = ap.parse_args()
    ff = common.get_ffmpeg()

    report = {'root': a.root, 'folders': {}, 'images': []}
    for dirpath, dirnames, files in os.walk(a.root):
        rel = os.path.relpath(dirpath, a.root)
        entry = {'videos': [], 'audio': [], 'subs': []}
        for fn in sorted(files):
            p = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext in IMG_EXT:
                report['images'].append(os.path.relpath(p, a.root))
            elif ext in VID_EXT:
                # deep: probe all; else probe first video per folder and count rest
                if a.deep or not entry['videos']:
                    entry['videos'].append(common.probe(p, ff))
                else:
                    entry['videos'].append({'path': fn, 'probe': 'skipped'})
            elif ext in AUD_EXT:
                entry['audio'].append(fn)
            elif ext in SRT_EXT:
                entry['subs'].append(fn)
        if entry['videos'] or entry['audio'] or entry['subs']:
            report['folders'][rel] = entry

    print(json.dumps(report, ensure_ascii=False, indent=1))

    # frame grabs for the first real video found
    if a.frames:
        os.makedirs(a.frames, exist_ok=True)
        for folder in report['folders'].values():
            for v in folder['videos']:
                p = v.get('path') if not v.get('probe') else None
                if p and os.path.isabs(p):
                    dur = v.get('duration') or 60
                    for t, lab in ((1.0, 'head'), (dur * 0.45, 'mid'), (dur - 1.0, 'tail')):
                        subprocess_frame(ff, p, t, os.path.join(a.frames, 'frame_%s.jpg' % lab))
                    print('# frames saved to', a.frames, file=sys.stderr)
                    break
            else:
                continue
            break
    if a.out:
        common.write_json(a.out, report)
        print('# report saved to', a.out, file=sys.stderr)


def subprocess_frame(ff, video, t, out):
    import subprocess
    subprocess.run([ff, '-v', 'error', '-ss', '%.1f' % t, '-i', video,
                    '-frames:v', '1', '-q:v', '4', '-y', out], capture_output=True)


if __name__ == '__main__':
    main()
