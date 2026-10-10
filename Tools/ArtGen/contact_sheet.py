"""contact_sheet.py - preview sheet of every prop on turquoise (scratchpad only)."""
import os
import sys
from PIL import Image, ImageDraw
from artkit import ART, PREVIEW

def main(bg=(40, 190, 215), name='props_contact_sheet'):
    d = os.path.join(ART, 'Props')
    files = sorted(f for f in os.listdir(d) if f.endswith('.png'))
    ims = [(f, Image.open(os.path.join(d, f))) for f in files]
    maxw, pad = 1900, 14
    rows, row, x, rh = [], [], pad, 0
    for f, im in ims:
        if x + im.width + pad > maxw and row:
            rows.append((row, rh)); row, x, rh = [], pad, 0
        row.append((f, im, x)); x += im.width + pad; rh = max(rh, im.height)
    rows.append((row, rh))
    H = sum(rh + 30 for _, rh in rows) + pad
    sheet = Image.new('RGBA', (maxw, H), bg + (255,))
    dr = ImageDraw.Draw(sheet)
    y = pad
    for row, rh in rows:
        for f, im, x in row:
            sheet.alpha_composite(im, (x, y + rh - im.height))
            dr.text((x, y + rh + 4), f[:-4], fill=(0, 40, 60, 255))
        y += rh + 30
    p = os.path.join(PREVIEW, name + '.png')
    sheet.convert('RGB').save(p)
    print(p)

if __name__ == '__main__':
    main()
    main((255, 255, 255), 'props_contact_sheet_white')
