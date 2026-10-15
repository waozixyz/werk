#!/usr/bin/env python3
"""Resize the owner-selected modular W bitmap for all distribution sizes."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/app/logo.png'
def render(size, background=None):
    image = Image.open(SOURCE).convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
    if background:
        base = Image.new('RGBA', image.size, background); base.alpha_composite(image); image = base
    return image
outputs = {'assets/app/icon.png':512, 'fastlane/metadata/android/en-US/images/icon.png':512,
'web/site/icons/favicon-32.png':32, 'web/site/icons/apple-touch-icon.png':180,
'web/site/icons/icon-192.png':192, 'web/site/icons/icon-512.png':512,
'web/site/app/icons/icon-192.png':192, 'web/site/app/icons/icon-512.png':512}
for density, size in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:
    outputs[f'droid/app/src/main/res/mipmap-{density}/ic_launcher.png'] = size
for path, size in outputs.items():
    render(size, '#ffffff' if 'launcher' in path or '/icons/' in path else None).save(ROOT / path)
font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
name = 'Werkzeug'
for path, size in [('assets/app/readme-banner.png',(1536,512)), ('assets/app/readme-square-630x500.png',(630,500)), ('showcase/banner.png',(1536,1024)), ('web/site/images/social.png',(1536,1024))]:
    w,h=size; image=Image.new('RGB',size,'#f7f3ff'); d=ImageDraw.Draw(image)
    icon_size=int(min(w*.24,h*.55))
    while True:  # shrink the mark until the name fits with a margin
        fs=int(icon_size*.55); font=ImageFont.truetype(font_path,fs)
        box=d.textbbox((0,0),name,font=font); tw=box[2]; gap=icon_size*.18
        if icon_size+gap+tw <= w*.86: break
        icon_size-=2
    mark=render(icon_size)
    left=int((w-mark.width-gap-tw)/2); top=int((h-mark.height)/2)
    image.paste(mark,(left,top),mark)
    d.text((left+mark.width+gap, (h-(box[3]-box[1]))/2-box[1]),name,font=font,fill='#291747')
    image.save(ROOT/path)
print('Rendered Werkzeug brand assets')
