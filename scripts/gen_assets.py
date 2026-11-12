# -*- coding: utf-8 -*-
"""Stage 4a: UI overlay assets — logo patch, title card, static end card.

Usage:
  python gen_assets.py --logo <logo.png> --brand "SODA TV" \
      --title1 "Fake Divorce," --title2 "Real Regret" --out <assets_dir> \
      [--width 720 --height 1280] [--tagline "Watch the FULL drama for FREE"]

Outputs (in --out):
  logo_overlay.png  - rounded logo w/ soft shadow, for top-right overlay
  title_card.png    - transparent full-frame title (brand + drama name, 4s)
  end_card.png      - OPAQUE dark end card: big logo + search box + store
                      badges + tagline + drama name (3s static, review-safe)
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageFilter

GOLD = (212, 175, 55)


def font(name, size):
    for cand in (name, 'segoeuib.ttf', 'arial.ttf'):
        p = os.path.join(r'C:\Windows\Fonts', cand)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def build_logo_overlay(logo_path, out, logo_w=140):
    logo = Image.open(logo_path).convert('RGBA')
    lh = round(logo.height * logo_w / logo.width)
    s = logo.resize((logo_w, lh), Image.LANCZOS)
    pad = 16
    cv = Image.new('RGBA', (logo_w + pad * 2, lh + pad * 2), (0, 0, 0, 0))
    sh = Image.new('RGBA', cv.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([pad + 3, pad + 5, pad + logo_w + 3, pad + lh + 5],
                         radius=26, fill=(0, 0, 0, 90))
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    cv = Image.alpha_composite(cv, sh)
    cv.alpha_composite(s, (pad, pad))
    cv.save(out)


def build_title_card(brand, t1, t2, W, H, out):
    tc = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(tc)
    f_brand = font('seguisb.ttf', 26)
    brand_txt = ' '.join(brand.upper()) if len(brand) <= 12 else brand.upper()
    brand_txt = '  '.join(brand.split()) + '   O R I G I N A L'
    bw = d.textlength(brand_txt, font=f_brand)
    d.text(((W - bw) / 2, 240), brand_txt, font=f_brand, fill=(255, 235, 200, 235))
    d.rectangle([(W - bw) / 2 - 70, 254, (W - bw) / 2 - 24, 256], fill=(*GOLD, 220))
    d.rectangle([(W + bw) / 2 + 24, 254, (W + bw) / 2 + 70, 256], fill=(*GOLD, 220))
    f_title = font('georgiab.ttf', 84)
    lines = [x for x in (t1, t2) if x]
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=f_title)
        x, y = (W - tw) / 2, 310 + i * 108
        d.text((x + 4, y + 5), line, font=f_title, fill=(0, 0, 0, 200))
        d.text((x, y), line, font=f_title, fill=(255, 255, 255, 245),
               stroke_width=2, stroke_fill=(20, 20, 30, 220))
    d.rectangle([W / 2 - 130, 552 + (len(lines) - 2) * 108,
                 W / 2 + 130, 556 + (len(lines) - 2) * 108], fill=(*GOLD, 235))
    tc.save(out)


def build_end_card(logo_path, brand, t1, t2, tagline, W, H, out):
    ec = Image.new('RGBA', (W, H))
    top, bot = (17, 18, 26), (30, 32, 46)
    px = ec.load()
    for y in range(H):
        t = y / (H - 1)
        c = tuple(round(a + (b - a) * t) for a, b in zip(top, bot))
        for x in range(W):
            px[x, y] = (*c, 255)   # fully opaque
    d = ImageDraw.Draw(ec)
    logo = Image.open(logo_path).convert('RGBA')
    big_w = 260
    big = logo.resize((big_w, round(logo.height * big_w / logo.width)), Image.LANCZOS)
    ec.alpha_composite(big, ((W - big.width) // 2, 330))
    d = ImageDraw.Draw(ec)
    # search box
    sx0, sy0, sx1, sy1 = 110, 660, 610, 738
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=39, fill=(255, 255, 255, 242))
    f_search = font('seguisb.ttf', 40)
    d.text((sx0 + 34, sy0 + 14), brand, font=f_search, fill=(200, 30, 30, 255))
    cx, cy, r = sx1 - 52, (sy0 + sy1) // 2, 15
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(120, 120, 130, 255), width=5)
    d.line([cx + 11, cy + 11, cx + 26, cy + 26], fill=(120, 120, 130, 255), width=6)
    # tagline
    f_tag = font('segoeuib.ttf', 42)
    tw = d.textlength(tagline, font=f_tag)
    d.text(((W - tw) / 2, 790), tagline, font=f_tag, fill=(255, 255, 255, 245))
    # store badges
    f_bs, f_bl = font('segoeui.ttf', 20), font('seguisb.ttf', 34)
    for i, (small, big_t) in enumerate([('Download on the', 'App Store'),
                                        ('GET IT ON', 'Google Play')]):
        bx, by = 74 + i * 300, 900
        d.rounded_rectangle([bx, by, bx + 272, by + 86], radius=18,
                            fill=(255, 255, 255, 255), outline=(255, 255, 255, 255), width=2)
        d.rounded_rectangle([bx + 2, by + 2, bx + 270, by + 84], radius=16, fill=(44, 46, 58, 255))
        d.text((bx + 24, by + 10), small, font=f_bs, fill=(210, 212, 222, 255))
        d.text((bx + 24, by + 36), big_t, font=f_bl, fill=(255, 255, 255, 255))
        if i == 0:
            d.ellipse([bx + 216, by + 30, bx + 250, by + 64], outline=(255, 255, 255, 230), width=3)
        else:
            d.polygon([(bx + 222, by + 28), (bx + 222, by + 66), (bx + 252, by + 47)],
                      fill=(255, 255, 255, 235))
    # drama name bottom
    f_dn = font('segoeuib.ttf', 30)
    dn = '  '.join(x for x in (t1, t2) if x)
    tw = d.textlength(dn, font=f_dn)
    d.text(((W - tw) / 2, 1150), dn, font=f_dn, fill=(255, 255, 255, 200))
    ec.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--logo', required=True)
    ap.add_argument('--brand', default='SODA TV')
    ap.add_argument('--title1', required=True)
    ap.add_argument('--title2', default='')
    ap.add_argument('--tagline', default='Watch the FULL drama for FREE')
    ap.add_argument('--out', required=True)
    ap.add_argument('--width', type=int, default=720)
    ap.add_argument('--height', type=int, default=1280)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    build_logo_overlay(a.logo, os.path.join(a.out, 'logo_overlay.png'))
    build_title_card(a.brand, a.title1, a.title2, a.width, a.height,
                     os.path.join(a.out, 'title_card.png'))
    build_end_card(a.logo, a.brand, a.title1, a.title2, a.tagline, a.width, a.height,
                   os.path.join(a.out, 'end_card.png'))
    print('assets done:', sorted(os.listdir(a.out)))


if __name__ == '__main__':
    main()
