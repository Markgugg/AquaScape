"""
ui.py - AquaScape UI art: 9-slice glass panels/buttons, HUD icons, the logo
and the title / level-complete key-art panoramas.

Output: Assets/AquaScape/Art/UI/*.png  (+ Tools/ArtGen/_meta_ui.json)
Run:    python3 ui.py [name ...]
"""
import json
import math
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from aqua import *
from artkit import *

META = {}


# ----------------------------------------------------------------------------
# 9-slice glass pieces
# ----------------------------------------------------------------------------

def fade_edges(c, margin=6):
    """Window glows/sparkles to zero near the image border (no clipping)."""
    w = smoothstep(0, margin, c.X) * smoothstep(c.w, c.w - margin, c.X) * \
        smoothstep(0, margin, c.Y) * smoothstep(c.h, c.h - margin, c.Y)
    c.P = c.P * w[..., None]
    c.A = c.A * w


def rrect(c, x0, y0, x1, y1, r):
    return sd_box(c, (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, r)


def panel():
    W = H = 256
    c = Canvas(W, H, 3)
    d = rrect(c, 3, 3, W - 3, H - 3, 46)
    t = clamp01(c.Y / H)
    # white -> pale aqua body, translucent
    col = gradient_map(t, [(0.0, rgb('#ffffff')), (0.45, rgb('#eefbff')), (1.0, rgb('#c4f1ff'))])
    c.over(col, c.cover(d) * 0.75)
    # soft inner aqua glow at the bottom edge
    inner_shadow(c, d, 22, 0.25, tuple(rgb('#7fe3ff')))
    # top gloss band (only near the top, fades out by ~40%)
    band = rrect(c, 12, 9, W - 12, 92, 38)
    g = smoothstep(95, 12, c.Y)
    c.over(WHITE, c.cover(band, 2) * g * 0.55)
    # crisp white 3px border + faint aqua hairline inside it
    c.over(WHITE, c.cover(np.abs(d + 1.5) - 1.5))
    c.over(rgb('#8fe6ff'), c.cover(np.abs(d + 4.6) - 0.7) * 0.6)
    c.over(rgb('#4bb8e6'), c.cover(np.abs(d - 0.6) - 0.6) * 0.7)   # outer edge for white bg
    META['UI/panel.png'] = {'border': [48, 48, 48, 48]}
    return c.image()


def capsule_button(W, H, top, bot, bright=0.0, rim=3.0):
    c = Canvas(W, H, 3)
    r = (H - 6) / 2
    d = rrect(c, 3, 3, W - 3, H - 3, r)
    t = clamp01((c.Y - 3) / (H - 6))
    col = gradient_map(t, [(0.0, rgb(top)), (0.55, mix(rgb(top), rgb(bot), 0.6)), (1.0, rgb(bot))])
    col = col + bright
    c.over(clamp01(col), c.cover(d))
    # bottom refracted glow (lighter band near the bottom inside)
    caus = smoothstep(H * 0.55, H - 6, c.Y) * (1 - smoothstep(H - 12, H - 3, c.Y))
    c.over(rgb('#b8fbff'), c.cover(d + 4) * caus * (0.45 + bright))
    inner_shadow(c, d, 8, 0.25, tuple(rgb('#0a5fb0')))
    # glossy top half highlight
    hl = rrect(c, 3 + r * 0.35, 6, W - 3 - r * 0.35, H * 0.5, r * 0.6)
    c.over(WHITE, c.cover(hl, 2) * (0.25 + 0.55 * smoothstep(H * 0.52, 6, c.Y)))
    # white rim
    c.over(WHITE, c.cover(np.abs(d + rim / 2) - rim / 2) * 0.95)
    c.over(rgb('#1a86d0'), c.cover(np.abs(d - 0.7) - 0.7) * 0.75)   # outer edge for white bg
    return c.image()


def button():
    META['UI/button.png'] = {'border': [48, 44, 48, 44]}
    return capsule_button(256, 96, '#9ff3ff', '#20a8f0')


def button_hover():
    META['UI/button_hover.png'] = {'border': [48, 44, 48, 44]}
    return capsule_button(256, 96, '#d2fbff', '#3cc4ff', bright=0.06)


def pill():
    W, H = 192, 72
    c = Canvas(W, H, 3)
    r = (H - 6) / 2
    d = rrect(c, 3, 3, W - 3, H - 3, r)
    t = clamp01((c.Y - 3) / (H - 6))
    col = gradient_map(t, [(0.0, rgb('#ffffff')), (0.5, rgb('#e2f8ff')), (1.0, rgb('#a8e8ff'))])
    c.over(col, c.cover(d) * 0.78)
    inner_shadow(c, d, 10, 0.22, tuple(rgb('#4fc6f0')))
    hl = rrect(c, 3 + r * 0.4, 6, W - 3 - r * 0.4, H * 0.46, r * 0.55)
    c.over(WHITE, c.cover(hl, 2) * 0.6 * smoothstep(H * 0.5, 6, c.Y))
    c.over(WHITE, c.cover(np.abs(d + 1.25) - 1.25))
    c.over(rgb('#4bb8e6'), c.cover(np.abs(d - 0.6) - 0.6) * 0.7)
    META['UI/pill.png'] = {'border': [36, 36, 36, 36]}
    return c.image()


# ----------------------------------------------------------------------------
# Icons (96 px)
# ----------------------------------------------------------------------------

def thin_film(phase):
    """Iridescent rainbow colour from a phase field (soap-bubble look)."""
    p = phase * 2 * math.pi
    r = 0.5 + 0.5 * np.cos(p)
    g = 0.5 + 0.5 * np.cos(p - 2.1)
    b = 0.5 + 0.5 * np.cos(p - 4.2)
    col = np.dstack([r, g, b])
    # bias towards cyan/magenta/pastel
    return mix(col, rgb('#bff6ff'), 0.25)


def draw_bubble(c, cx, cy, r, strength=1.0):
    d = sd_circle(c, cx, cy, r)
    rr = np.hypot(c.X - cx, c.Y - cy) / r
    ang = np.arctan2(c.Y - cy, c.X - cx)
    cov = c.cover(d)
    # outer soft cyan glow so it reads on white
    c.glow(d, rgb('#5fe0ff'), r * 0.12, 0.35 * strength)
    # interior: faint aqua tint, stronger towards the rim (fresnel)
    film = thin_film(rr * 1.3 + np.sin(ang * 2) * 0.15 + 0.2)
    fres = clamp01(rr) ** 4
    c.over(rgb('#bdf4ff'), cov * 0.18)
    c.over(film, cov * fres * 0.85)
    # dark-blue rim line for contrast on white
    c.over(rgb('#2a8fd8'), c.cover(np.abs(d + r * 0.03) - r * 0.025) * 0.55)
    c.over(WHITE, c.cover(np.abs(d + r * 0.075) - r * 0.02) * 0.55)
    # big curved highlight top-left
    highlight_arc(c, cx, cy, r * 0.74, r * 0.74, r * 0.07, 195, 265, 0.95)
    hl = sd_ellipse(c, cx - r * 0.38, cy - r * 0.42, r * 0.17, r * 0.11)
    c.over(WHITE, c.cover(hl, 2) * 0.9)
    # soft bottom-right reflection
    highlight_arc(c, cx, cy, r * 0.78, r * 0.78, r * 0.04, 20, 80, 0.5, (0.85, 1.0, 1.0))
    sparkle(c, cx + r * 0.55, cy - r * 0.6, r * 0.35, 0.9)


def icon_bubble():
    c = Canvas(96, 96, 3)
    draw_bubble(c, 48, 48, 38)
    fade_edges(c, 5)
    return c.image()


def draw_gem(c, cx, cy, s, glow=1.0):
    """Faceted sapphire/cyan diamond (pointing down), size s = half-width."""
    top = cy - s * 0.55
    girdle = cy - s * 0.15
    tip = cy + s * 1.0
    tw = s * 0.55
    outline = [(cx - tw, top), (cx + tw, top), (cx + s, girdle), (cx, tip), (cx - s, girdle)]
    d = sd_poly(c, outline)
    c.glow(d, rgb('#5fe0ff'), s * 0.35, 0.55 * glow)
    # facets: (polygon, colour)
    F = [
        ([(cx - tw, top), (cx - tw * 0.3, top), (cx - s * 0.45, girdle), (cx - s, girdle)], '#9feeff'),
        ([(cx - tw * 0.3, top), (cx + tw * 0.3, top), (cx + s * 0.45, girdle), (cx - s * 0.45, girdle)], '#e8ffff'),
        ([(cx + tw * 0.3, top), (cx + tw, top), (cx + s, girdle), (cx + s * 0.45, girdle)], '#4fc4f5'),
        ([(cx - s, girdle), (cx - s * 0.45, girdle), (cx, tip)], '#2a8ee8'),
        ([(cx - s * 0.45, girdle), (cx, girdle), (cx, tip)], '#4fb8ff'),
        ([(cx, girdle), (cx + s * 0.45, girdle), (cx, tip)], '#1a6fd6'),
        ([(cx + s * 0.45, girdle), (cx + s, girdle), (cx, tip)], '#0f4cb0'),
    ]
    for poly, col in F:
        fd = sd_poly(c, poly)
        t = clamp01((c.Y - top) / (tip - top))
        base = rgb(col)
        shade = mix(base, base * 0.62, t[..., None] * 0.7)
        # inner light from the upper-left + lower caustic
        lit_ = np.exp(-(((c.X - (cx - s * 0.3)) / s) ** 2 + ((c.Y - top) / (s * 0.7)) ** 2))
        shade = shade + lit_[..., None] * 0.25
        c.over(clamp01(shade), c.cover(fd) * c.cover(d))
    # facet edge lines
    for poly, _ in F:
        fd = sd_poly(c, poly)
        c.over(WHITE, c.cover(np.abs(fd) - 0.5) * c.cover(d) * 0.35)
    c.over(WHITE, c.cover(np.abs(d + 0.8) - 0.9) * 0.7)
    # glints
    hl = sd_poly(c, [(cx - tw * 0.85, top + 2), (cx - tw * 0.4, top + 2), (cx - s * 0.6, girdle - 1)])
    c.over(WHITE, c.cover(hl, 1.5) * 0.7)
    sparkle(c, cx + tw * 0.55, top + s * 0.08, s * 0.5, 0.95)
    return d


def icon_shard():
    c = Canvas(96, 96, 3)
    draw_gem(c, 48, 40, 36)
    fade_edges(c, 8)
    return c.image()


def draw_mini_beacon(c, lit):
    cx = 48
    if lit:   # halo behind everything
        c.glow(sd_circle(c, cx, 36, 25), GLOW, 9, 0.6)
    # stepped ceramic pedestal
    base = rrect(c, 20, 76, 76, 91, 6)
    paint_shaded(c, base, ceramic, bevel=5)
    band = op_inter(base, np.abs(c.Y - 84) - 2.6)
    c.over(rgb('#38c8f0') if not lit else rgb('#46ecff'), c.cover(band) * 0.95)
    if lit:
        c.glow(band, GLOW, 3, 0.4)
    mid = rrect(c, 29, 63, 67, 78, 5)
    paint_shaded(c, mid, ceramic, bevel=5)
    band2 = op_inter(mid, np.abs(c.Y - 70) - 1.8)
    c.over(rgb('#38c8f0') if not lit else rgb('#46ecff'), c.cover(band2) * 0.9)
    if lit:
        c.glow(band2, GLOW, 3, 0.35)
    # chrome cup + prongs
    cup = sd_ellipse(c, cx, 62, 19, 6.5)
    paint_shaded(c, cup, chrome, bevel=4)
    R = 25
    oy = 36
    if lit:
        glass_orb(c, cx, oy, R, lit=1.0, halo=False)
    else:
        glass_orb(c, cx, oy, R, lit=0.0, tint=('#f4f9ff', '#b9cfe6', '#7d97bd'), alpha=0.9)
    for sx in (-1, 1):
        pr = sd_capsule(c, cx + sx * 15, 61, cx + sx * 23, 38, 2.8, 1.6)
        paint_shaded(c, pr, chrome, bevel=2)


def icon_beacon_off():
    c = Canvas(96, 96, 3)
    draw_mini_beacon(c, False)
    fade_edges(c)
    return c.image()


def icon_beacon_on():
    c = Canvas(96, 96, 3)
    draw_mini_beacon(c, True)
    fade_edges(c, 10)
    return c.image()


def icon_pause():
    c = Canvas(96, 96, 3)
    cx = cy = 48
    r = 40
    d = sd_circle(c, cx, cy, r)
    c.shadow(sd_circle(c, cx, cy + 3, r), 5, 0.25, SHADOW_COL)
    t = clamp01((c.Y - (cy - r)) / (2 * r))
    col = gradient_map(t, [(0.0, rgb('#a8f5ff')), (0.55, rgb('#4cc4f6')), (1.0, rgb('#1590e0'))])
    c.over(col, c.cover(d))
    caus = np.exp(-(((c.X - cx) / (r * 0.6)) ** 2 + ((c.Y - (cy + r * 0.6)) / (r * 0.25)) ** 2))
    c.over(rgb('#c8fdff'), caus * c.cover(d) * 0.55)
    inner_shadow(c, d, 7, 0.3, tuple(rgb('#0a5fb0')))
    # pause bars (white ceramic, slight bevel + shadow)
    for bx in (-11, 11):
        bar = sd_box(c, cx + bx, cy + 1, 6.5, 17, 4)
        c.shadow(sd_box(c, cx + bx + 1, cy + 3, 6.5, 17, 4), 3, 0.35, (0.03, 0.25, 0.5))
        paint_shaded(c, bar, ceramic, bevel=4)
    # gloss on top half
    hl = sd_ellipse(c, cx, cy - r * 0.48, r * 0.72, r * 0.42)
    c.over(WHITE, c.cover(op_inter(hl, d + 3), 2) * 0.5 * smoothstep(cy, cy - r, c.Y))
    c.over(WHITE, c.cover(np.abs(d + 1.5) - 1.5))
    return c.image()


# ----------------------------------------------------------------------------
# Logo
# ----------------------------------------------------------------------------

def text_mask(text, size, ss, pad):
    """Rasterise text at super-sampled resolution -> (alpha array, bbox)."""
    font = ImageFont.truetype(FONT, size * ss)
    l, t, r, b = font.getbbox(text)
    w, h = r - l + 2 * pad * ss, b - t + 2 * pad * ss
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).text((pad * ss - l, pad * ss - t), text, font=font, fill=255)
    return im


def mask_sdf(mask_img, ss, max_r):
    """Approximate signed distance (final px) from an L-mode mask via a
    stack of blurred thresholds (good enough for outlines and bevels)."""
    a = np.asarray(mask_img, float) / 255.0
    # Use blur-and-erfinv trick: blurred edge follows normal CDF.
    from tiles import erfinv
    sig = max_r * ss / 2.2
    b = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(sig)), float) / 255.0
    b = np.clip(b, 1e-4, 1 - 1e-4)
    return -(sig / ss) * math.sqrt(2) * erfinv(2 * b - 1)


def blur_field(a, r, ss):
    im = Image.fromarray((clamp01(a) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r * ss)), float) / 255.0


def logo():
    W, H = 1400, 420
    ss = 2
    c = Canvas(W, H, ss)
    text = 'AquaScape'
    size = 228
    im = text_mask(text, size, ss, 0)
    tw, th = im.size[0] / ss, im.size[1] / ss
    ox, oy = (W - tw) / 2 - 10, (H - th) / 2 - 18
    full = Image.new('L', (W * ss, H * ss), 0)
    full.paste(im, (int(ox * ss), int(oy * ss)))
    A = np.asarray(full, float) / 255.0
    sdf_small = mask_sdf(full, ss, 6)          # accurate near the glyph edge
    sdf_big = mask_sdf(full, ss, 24)           # smooth, rounded, for outlines
    y0, y1 = oy + th * 0.02, oy + th * 0.98

    # --- orbit swoosh (tilted ellipse) ----------------------------------------
    scx, scy, srx, sry, rot = W / 2 + 10, H / 2 + 38, 640, 112, math.radians(-7)
    dx, dy = c.X - scx, c.Y - scy
    ux = dx * math.cos(rot) + dy * math.sin(rot)
    uy = -dx * math.sin(rot) + dy * math.cos(rot)
    k = np.hypot(ux / srx, uy / sry)
    ring = np.abs(k - 1) * sry
    ang = np.arctan2(uy / sry, ux / srx)              # 0 = right, +90 = bottom
    span_mid, span_half = math.radians(68), math.radians(122)
    da = np.angle(np.exp(1j * (ang - span_mid)))
    prof = clamp01(1 - np.abs(da) / span_half)      # 1 mid .. 0 at the ends
    thick = 0.4 + 11 * prof ** 0.8
    sw = ring - thick
    vis = (prof > 0).astype(float)
    front = (uy > -10).astype(float)
    sw_col = gradient_map(prof, [(0, rgb('#5fe0ff')), (0.6, rgb('#bffaff')), (1, rgb('#ffffff'))])

    def draw_swoosh(mask):
        c.glow(sw, rgb('#38c8f0'), 9, 0.35 * prof * mask)
        c.over(rgb('#1f8fe0'), c.cover(sw - 1.6) * vis * mask * 0.85)
        c.over(sw_col, c.cover(sw) * vis * mask)
        core = ring - thick * 0.3
        c.over(WHITE, c.cover(core) * vis * mask * prof)

    draw_swoosh(1 - front)

    # --- outer glow + drop shadow ---------------------------------------------
    outline = sdf_big - 13
    ocov = c.cover(outline)
    c.add(rgb('#9ff8ff'), blur_field(ocov, 14, ss) * 0.45)
    sh = blur_field(ocov, 7, ss)
    sh = np.roll(sh, int(9 * ss), axis=0)
    c.over(rgb('#08306e'), sh * 0.42)

    # --- deep blue outer stroke + thick white bevelled outline ---------------
    c.over(rgb('#1764c8'), c.cover(outline - 3.2))
    on = normals(c, height_bevel(outline, 7))
    ocol = mat_plastic(on, '#ffffff', '#a6c4e8', gloss=0.9)
    c.over(ocol, ocov)
    # thin aqua inner line between outline and fill
    c.over(rgb('#2fb8f0'), c.cover(sdf_small - 2.0))

    # --- glossy gradient fill ----------------------------------------------
    fill = sdf_small + 1.0
    t = clamp01((c.Y - y0) / (y1 - y0))
    fcol = gradient_map(t, [(0.0, rgb('#b8fbff')), (0.25, rgb('#4fe0ff')),
                            (0.55, rgb('#169cf2')), (0.8, rgb('#0b5ad6')), (1.0, rgb('#0a3aa8'))])
    fn = normals(c, height_bevel(fill, 6))
    fcol = fcol * (0.86 + 0.18 * lambert(fn))[..., None] + spec(fn, 70)[..., None] * 0.55
    # inner caustic glow along the bottom of each glyph
    caus = smoothstep(0.72, 1.0, t) * smoothstep(-1, -10, fill)
    fcol = mix(fcol, rgb('#5ff3ff'), (caus * 0.55)[..., None])
    c.over(clamp01(fcol), c.cover(fill))
    inner_shadow(c, fill, 5, 0.3, tuple(rgb('#062a7a')))
    # glossy highlight over the top half (gently curved horizon)
    xm = (c.X - W / 2) / (W / 2)
    horizon = y0 + (y1 - y0) * (0.50 - 0.05 * xm * xm)
    inside = smoothstep(-2.5, -6.5, fill)
    gloss = smoothstep(horizon + 0.8, horizon - 0.8, c.Y) * inside
    c.over(WHITE, gloss * (0.30 + 0.5 * smoothstep(horizon, y0 + 10, c.Y)))
    # bright rim highlight on upper-left edges
    rimw = clamp01(-fn[..., 1] * 2.0 - fn[..., 0] * 0.8)
    c.over(WHITE, c.cover(np.abs(fill + 2.4) - 0.9) * rimw * 0.85)

    # --- front half of the swoosh over the text -----------------------------
    draw_swoosh(front)

    # bubbles + sparkles
    end = math.radians(-50)
    bx = scx + srx * math.cos(end) * math.cos(rot) - sry * math.sin(end) * math.sin(rot)
    by = scy + srx * math.cos(end) * math.sin(rot) + sry * math.sin(end) * math.cos(rot)
    draw_bubble(c, bx + 22, by - 24, 30)
    draw_bubble(c, bx + 52, by - 78, 13)
    draw_bubble(c, 92, 338, 16)
    draw_bubble(c, 60, 300, 8)
    sparkle(c, ox + 70, oy + 18, 34, 1.0)
    sparkle(c, ox + tw * 0.53, oy + 4, 20, 0.85)
    sparkle(c, scx - 250, scy + sry * 0.98, 26, 0.9)
    fade_edges(c, 8)
    return c.image()


def title_bg():
    from ui_scene import scene
    return scene(False)


def complete_bg():
    from ui_scene import scene
    return scene(True)


# ----------------------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------------------
JOBS = {
    'panel': panel, 'button': button, 'button_hover': button_hover, 'pill': pill,
    'icon_bubble': icon_bubble, 'icon_shard': icon_shard,
    'icon_beacon_off': icon_beacon_off, 'icon_beacon_on': icon_beacon_on,
    'icon_pause': icon_pause, 'logo': logo,
    'title_bg': title_bg, 'complete_bg': complete_bg,
}


def _job(name):
    META.clear()
    img = JOBS[name]()
    save(img, f'UI/{name}.png')
    check_padding(img, name) if name not in ('panel', 'button', 'button_hover', 'pill', 'title_bg', 'complete_bg') else None
    return name, dict(META), img.size


def main():
    from multiprocessing import Pool
    names = sys.argv[1:] or list(JOBS)
    with Pool() as p:
        res = p.map(_job, names)
    meta_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_meta_ui.json')
    meta = {}
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path))
    for name, m, size in res:
        meta.update(m)
        print(name, size)
    json.dump(meta, open(meta_path, 'w'), indent=2)


if __name__ == '__main__':
    main()
