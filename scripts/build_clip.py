# -*- coding: utf-8 -*-
"""Stage 5: batch-build ad clips (pinjie / jieping) from a project JSON.

Proven ffmpeg-9 filter pipeline: segs -> scale -> logo/title overlay ->
(ASS narration subs for jieping) -> concat -> 3s static end card -> libx264.

project.json schema:
{
  "cheng_dir":   "D:/.../成片",          // subtitled masters (pinjie source)
  "nosub_dir":   "D:/.../无字幕成片",     // clean masters (jieping source)
  "episode_pattern": "第{ep:02d}集.mp4",  // optional, uses {ep}
  "assets_dir":  ".../assets",           // logo_overlay.png / title_card.png / end_card.png
  "tts_json":    ".../assets/tts/durations.json",  // required for jieping
  "bgm":         "path/to/soft_bgm.mp3", // single soft track, trimmed to clip
  "output_dir":  ".../成片素材输出",
  "shots_dir":   ".../shots",            // optional epNN.txt scene cuts (snapping)
  "resolution": [720, 1280], "fps": 30, "crf": 19, "endcard": 3.0,
  "narr_gain": 1.35, "bgm_gain": 0.14,   // jieping mix; pinjie endcard bgm 0.55
  "clips": {
    "<full 9-part filename>": {
      "type": "pinjie",
      "segs": [[ep, a, b], ...]
    },
    "<full 9-part filename>": {
      "type": "jieping", "narr_id": "d1", "tail": 2.3,
      "lines": [[ep, anchor], ...],        // one segment per narration line
      "ends": {"1": 43.05},                // optional forced seg end (by line idx)
      "bonus": [[4, [ep, a, b]], ...]      // optional extra segs after line N
    }
  }
}

Usage:
  python build_clip.py <project.json> [name_filter ...]
Env: CRF=19 override; FORCE=1 build despite audit overlap (not recommended)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

A4 = 'aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo'


def esc(p):
    return p.replace('\\', '/').replace(':', '\\:')


def ts(s):
    return '%d:%02d:%05.2f' % (int(s // 3600), int(s % 3600 // 60), s % 60)


def wrap(text, width=28):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        lines.append(cur)
    return '\\N'.join(lines)


def write_ass(path, cues, W, H):
    scale = H / 1280.0
    fs, mv = int(40 * scale), int(380 * scale)
    hdr = '''[Script Info]
ScriptType: v4.00+
PlayResX: %d
PlayResY: %d
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narr,Arial,%d,&H00FFFFFF,&H00FFFFFF,&H00101010,&H7A000000,-1,0,0,0,100,100,0,0,1,3,1,2,40,40,%d,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
''' % (W, H, fs, mv)
    ev = ['Dialogue: 0,%s,%s,Narr,,0,0,0,,%s' % (ts(st), ts(en), txt)
          for st, en, txt in cues]
    with open(path, 'w', encoding='utf-8-sig') as f:
        f.write(hdr + '\n'.join(ev) + '\n')


def jieping_segs(cfg, tts_meta):
    d = tts_meta[cfg['narr_id']]
    tail = cfg.get('tail', 2.3)
    ends = {int(k): v for k, v in cfg.get('ends', {}).items()}
    bonus = {int(i): tuple(b) for i, b in cfg.get('bonus', [])}
    segs, line_idx = [], []
    for i, (ep, a) in enumerate(cfg['lines'], 1):
        dur = d[i - 1]['dur']
        segs.append((int(ep), float(a), float(ends.get(i, a + dur + tail))))
        line_idx.append(len(segs) - 1)
        if i in bonus:
            segs.append(bonus[i])
    return segs, line_idx


def all_segs_of(proj):
    tts_meta = common.read_json(proj['tts_json']) if proj.get('tts_json') else {}
    out = {}
    for name, cfg in proj['clips'].items():
        out[name] = (list(map(tuple, cfg['segs'])) if cfg['type'] == 'pinjie'
                     else jieping_segs(cfg, tts_meta)[0])
    return out


def build(name, cfg, proj, tts_meta):
    W, H = proj.get('resolution', [720, 1280])
    FPS = proj.get('fps', 30)
    CRF = os.environ.get('CRF', str(proj.get('crf', 19)))
    endcard = proj.get('endcard', 3.0)
    pat = proj.get('episode_pattern', '第{ep:02d}集.mp4').replace('{ep:02d}', '%02d').replace('{ep}', '%d')
    shots = common.load_shot_cuts(proj.get('shots_dir'))
    assets = proj['assets_dir']
    logo, title, endimg = (os.path.join(assets, x) for x in
                           ('logo_overlay.png', 'title_card.png', 'end_card.png'))

    # resolve segments + narration schedule
    if cfg['type'] == 'pinjie':
        segs = [tuple(s) for s in cfg['segs']]
        if shots:   # snap boundaries to scene cuts unless another clip already uses them
            bounds = {}
            for n2, s2 in all_segs_of(proj).items():
                for ep, a, b in s2:
                    bounds.setdefault(ep, []).extend([a, b])
            snapped = []
            for ep, a, b in segs:
                others = [t for t in bounds.get(ep, []) if t not in (a, b)]
                a2 = a if any(abs(t - a) < 1.0 for t in others) else common.snap(a, ep, shots, others)
                b2 = b if any(abs(t - b) < 1.0 for t in others) else common.snap(b, ep, shots, others)
                if b2 - a2 < 2.0:
                    a2, b2 = a, b
                snapped.append((ep, a2, b2))
            segs = snapped
        cues, narr_events = [], []
    else:
        segs, line_idx = jieping_segs(cfg, tts_meta)
        lines = tts_meta[cfg['narr_id']]
        cues, narr_events = [], []
        for k, si in enumerate(line_idx):
            off = sum(b - a for j, (_, a, b) in enumerate(segs) if j < si) + 0.30
            cues.append((off, off + lines[k]['dur'] + 0.25, wrap(lines[k]['text'])))
            narr_events.append((off, lines[k]['file']))

    story = sum(b - a for _, a, b in segs)
    total = story + endcard
    is_jp = cfg['type'] == 'jieping'
    src_dir = proj['nosub_dir'] if is_jp else proj['cheng_dir']

    # ---- inputs ----
    inputs = []
    for ep, a, b in segs:
        f = os.path.join(src_dir, pat % ep)
        inputs += ['-ss', '%.3f' % a, '-t', '%.3f' % (b - a), '-i', f]
    nvid = len(segs)
    inputs += ['-loop', '1', '-t', '%.2f' % (story + 0.5), '-i', logo]
    inputs += ['-loop', '1', '-t', '4.2', '-i', title]
    inputs += ['-loop', '1', '-t', '%.2f' % endcard, '-i', endimg]
    i_logo, i_title, i_ec = nvid, nvid + 1, nvid + 2
    aux = ([os.path.join(os.path.dirname(proj['tts_json']), f) for _, f in narr_events]
           if is_jp else []) + [proj['bgm']]
    for p in aux:
        inputs += ['-i', p]
    i_aux0 = nvid + 3

    # ---- filter graph ----
    fc = []
    for i in range(nvid):
        fc.append('[%d:v]scale=%d:%d:flags=lanczos,setsar=1,fps=%d[vi%d]' % (i, W, H, FPS, i))
    fc.append('%sconcat=n=%d:v=1:a=0[vcat]' % (''.join('[vi%d]' % i for i in range(nvid)), nvid))
    fc.append('[%d:v]format=rgba[lgo]' % i_logo)
    fc.append('[vcat][lgo]overlay=x=W-w-24:y=24[v0]')
    fc.append('[%d:v]format=rgba,fade=t=in:st=0:d=0.4:alpha=1,fade=t=out:st=3.4:d=0.6:alpha=1[ttl]' % i_title)
    fc.append("[v0][ttl]overlay=x=0:y=0:enable='lte(t,4.0)'[v1]")
    fc.append('[v1]format=yuv420p[vmain]')
    fc.append('color=c=black:s=%dx%d:r=%d:d=%.2f[cb]' % (W, H, FPS, endcard))
    fc.append('[%d:v]format=rgba[eo]' % i_ec)
    fc.append('[cb][eo]overlay=0:0,format=yuv420p[vend]')
    fc.append('[vmain][vend]concat=n=2:v=1:a=0[vjoin]')
    if is_jp:
        ass_path = os.path.join(assets, 'sub_%s.ass' % cfg['narr_id'])
        write_ass(ass_path, cues, W, H)
        fc.append("[vjoin]subtitles=filename='%s'[vout]" % esc(ass_path))
    else:
        fc.append('[vjoin]copy[vout]')

    if not is_jp:
        for i in range(nvid):
            fc.append('[%d:a]%s[ai%d]' % (i, A4, i))
        fc.append('%sconcat=n=%d:v=0:a=1[acat]' % (''.join('[ai%d]' % i for i in range(nvid)), nvid))
        fc.append('[%d:a]atrim=0:%.2f,afade=t=out:st=%.2f:d=1.0,volume=0.55,%s[aend]'
                  % (i_aux0, endcard + 0.2, endcard - 1.0, A4))
        fc.append('[acat][aend]concat=n=2:v=0:a=1[amix]')
        fc.append('[amix]alimiter=limit=0.92[aout]')
    else:
        parts = []
        k = i_aux0
        gain = proj.get('narr_gain', 1.35)
        for off, f in narr_events:
            ms = int(round(off * 1000))
            fc.append('[%d:a]volume=%.2f,%s,adelay=%d:all=1[nl%d]' % (k, gain, A4, ms, k))
            parts.append('[nl%d]')
            parts[-1] = parts[-1] % k
            k += 1
        bgm_gain = proj.get('bgm_gain', 0.14)
        fc.append('[%d:a]atrim=0:%.2f,volume=%.2f,afade=t=in:st=0:d=0.6,afade=t=out:st=%.2f:d=1.3,%s[bg]'
                  % (k, total + 0.2, bgm_gain, total - 1.3, A4))
        parts.append('[bg]')
        fc.append('%samix=inputs=%d:duration=longest:normalize=0[mx]' % (''.join(parts), len(parts)))
        fc.append('[mx]alimiter=limit=0.9,apad=whole_dur=%.2f,atrim=0:%.2f,%s[aout]'
                  % (total, total, A4))

    out = os.path.join(proj['output_dir'], name + '.mp4')
    cmd = [common.get_ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error']
    cmd += inputs
    cmd += ['-filter_complex', ';\n'.join(fc), '-map', '[vout]', '-map', '[aout]',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', CRF,
            '-maxrate', '4000k', '-bufsize', '8000k', '-profile:v', 'high',
            '-pix_fmt', 'yuv420p', '-r', str(FPS),
            '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',
            '-movflags', '+faststart', out]
    print('=== building', name)
    r = common.subprocess_run(cmd)
    sz = os.path.getsize(out) / 1048576.0 if os.path.exists(out) else 0
    if sz < 0.05:
        print('FAILED', name)
        print(r[-3000:])
        sys.exit(1)
    print('OK %-70s %6.1f MB  story=%.1fs total=%.1fs segs=%d'
          % (name[:70], sz, story, total, nvid))


def main():
    proj = common.read_json(sys.argv[1])
    only = sys.argv[2:] or None
    os.makedirs(proj['output_dir'], exist_ok=True)
    tts_meta = common.read_json(proj['tts_json']) if proj.get('tts_json') else {}
    segs_map = all_segs_of(proj)

    # audit
    flat = sorted((ep, a, b, n[:20]) for n, s in segs_map.items() for ep, a, b in s)
    bad = []
    for i in range(len(flat)):
        ep1, a1, b1, n1 = flat[i]
        for j in range(i + 1, len(flat)):
            ep2, a2, b2, n2 = flat[j]
            if ep2 != ep1:
                break
            if a2 < b1 - 0.01:
                bad.append('ep%d %.2f-%.2f(%s) vs %.2f-%.2f(%s)' % (ep1, a1, b1, n1, a2, b2, n2))
    print('=== GLOBAL AUDIT: %d segments, %d overlaps' % (len(flat), len(bad)))
    for x in bad:
        print('  OVERLAP', x)
    if bad and os.environ.get('FORCE') != '1':
        sys.exit(2)

    for name, cfg in proj['clips'].items():
        if only and not any(o in name for o in only):
            continue
        build(name, cfg, proj, tts_meta)
    print('ALL DONE')


if __name__ == '__main__':
    main()
