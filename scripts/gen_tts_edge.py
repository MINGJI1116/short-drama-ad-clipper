# -*- coding: utf-8 -*-
"""Stage 4b: narration TTS via Edge neural voices (multi-language).

Input: a lines JSON:  {"d1": [["narration text", "seg1"], ...], ...}
Tag convention: segN / segNb (b = second line of same segment), final line
tagged "outro" (CTA, scheduled over the end card).
Output: per-line wav/mp3 in <out_dir> + durations.json:
        {d1: [{file, text, tag, dur}, ...]}

Usage:
  python gen_tts_edge.py <lines.json> <out_dir> [--voice en-US-AvaNeural] [--rate +8%]
Common voices: en-US-AvaNeural / en-US-AndrewNeural / en-GB-SoniaNeural
               es-ES-ElviraNeural / pt-BR-FranciscaNeural / id-ID-GadisNeural
"""
import argparse
import asyncio
import os
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


async def synth(text, mp3_path, voice, rate):
    import edge_tts
    c = edge_tts.Communicate(text, voice, rate=rate)
    await c.save(mp3_path)


def to_wav(mp3_path, wav_path, ff):
    subprocess.run([ff, '-y', '-v', 'error', '-i', mp3_path,
                    '-ar', '44100', '-ac', '1', '-sample_fmt', 's16', wav_path],
                   check=True)


async def run(lines, out_dir, voice, rate):
    ff = common.get_ffmpeg()
    meta = {}
    for did, arr in lines.items():
        meta[did] = []
        for j, item in enumerate(arr, 1):
            text, tag = item[0], item[1]
            mp3 = os.path.join(out_dir, '%s_%02d.mp3' % (did, j))
            wav = os.path.join(out_dir, '%s_%02d.wav' % (did, j))
            await synth(text, mp3, voice, rate)
            to_wav(mp3, wav, ff)
            with wave.open(wav, 'rb') as w:
                dur = w.getnframes() / w.getframerate()
            meta[did].append({'file': os.path.basename(wav), 'text': text,
                              'tag': tag, 'dur': round(dur, 2)})
            print('%s_%02d %.2fs %s' % (did, j, dur, text[:60]))
    common.write_json(os.path.join(out_dir, 'durations.json'), meta)
    print('tts done ->', out_dir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('lines_json')
    ap.add_argument('out_dir')
    ap.add_argument('--voice', default='en-US-AvaNeural')
    ap.add_argument('--rate', default='+8%')
    a = ap.parse_args()
    lines = common.read_json(a.lines_json)
    os.makedirs(a.out_dir, exist_ok=True)
    asyncio.run(run(lines, a.out_dir, a.voice, a.rate))


if __name__ == '__main__':
    main()
