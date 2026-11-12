# -*- coding: utf-8 -*-
"""Shared helpers: ffmpeg resolution, probe parsing, episode path patterns."""
import io
import json
import os
import re
import subprocess


def get_ffmpeg():
    """Resolve ffmpeg path: env FFMPEG_PATH -> imageio_ffmpeg -> PATH."""
    p = os.environ.get('FFMPEG_PATH')
    if p and os.path.exists(p):
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    import shutil
    w = shutil.which('ffmpeg')
    if w:
        return w
    raise SystemExit('ffmpeg not found: set FFMPEG_PATH or pip install imageio-ffmpeg')


def probe(path, ff=None):
    """Return dict with duration(s), video WxH, video/audio codec, bitrate(kbps)."""
    ff = ff or get_ffmpeg()
    r = subprocess.run([ff, '-hide_banner', '-i', path], capture_output=True,
                       text=True, errors='replace')
    info = r.stderr
    out = {'path': path, 'exists': os.path.exists(path)}
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', info)
    out['duration'] = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else None
    m = re.search(r'Video: .*?, (\d{2,5})x(\d{2,5})', info)
    out['width'], out['height'] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    m = re.search(r'Video: ([^,]+)', info)
    out['vcodec'] = m.group(1).split()[0] if m else None
    out['is_aac'] = 'Audio: aac' in info
    out['has_audio'] = 'Audio:' in info
    m = re.search(r'Video: .*?(\d+) kb/s', info)
    out['bitrate_kbps'] = int(m.group(1)) if m else None
    return out


def episode_path(folder, ep, pattern=None):
    """Resolve episode file: try common Chinese naming patterns."""
    pats = pattern and [pattern] or ['第%02d集.mp4', '第%d集.mp4', 'EP%02d.mp4', 'ep%02d.mp4', '%02d.mp4']
    for p in pats:
        f = os.path.join(folder, p % ep)
        if os.path.exists(f):
            return f
    return None


def read_json(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


def write_json(p, obj):
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    with io.open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def subprocess_run(cmd):
    """Run command, return combined stdout+stderr text."""
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    return (r.stdout or '') + (r.stderr or '')


def load_shot_cuts(shots_dir, pattern='ep%02d.txt'):
    """Load scene-cut timestamps: {ep: [t, ...]}"""
    shots = {}
    if not shots_dir or not os.path.isdir(shots_dir):
        return shots
    for fn in os.listdir(shots_dir):
        m = re.search(r'(\d+)', fn)
        if not m or not fn.endswith('.txt'):
            continue
        with io.open(os.path.join(shots_dir, fn), encoding='utf-8') as f:
            shots[int(m.group(1))] = [float(x) for x in f.read().split() if x]
    return shots


def snap(t, ep, shots, exclude=(), max_dist=0.45):
    """Snap timestamp to nearest scene cut within max_dist seconds."""
    best, bd = t, max_dist
    for s in shots.get(ep, []):
        if any(abs(s - x) < 0.01 for x in exclude):
            continue
        d = abs(s - t)
        if d < bd:
            bd, best = d, s
    return best
