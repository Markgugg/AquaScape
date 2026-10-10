"""
props.py - world props for AquaScape (palms, bushes, rocks, Glass City
decor, puzzle objects, the Aqua Beacon, ...).

Usage:  python3 props.py            # render everything
        python3 props.py palm_1 cube  # render a subset (also writes previews)

Every sprite stands on its base at the bottom of the image. The pivot written
to _meta_props.json is the ground contact point (normalised, 0,0 = bottom-left).
"""
import json
import math
import os
import sys
import numpy as np
from PIL import Image
from aqua import *
from artkit import *

HERE = os.path.dirname(os.path.abspath(__file__))
PROPS = {}


def prop(name):
    def deco(fn):
        PROPS[name] = fn
        return fn
    return deco


def pivot(c, x, y):
    return [round(x / c.w, 4), round(1 - y / c.h, 4)]


# ============================================================================
# Foliage helpers
# ============================================================================
LEAF_LIGHT = rgb('#a6ef6a')
LEAF_MID = rgb('#4fcf58')
LEAF_DARK = rgb('#178a45')
LEAF_DEEP = rgb('#0b5d3c')


def leaf_colors(t, across, dark=0.0):
    """Glossy leaf ramp: t along the leaf, across = 0 midrib .. 1 edge."""
    col = gradient_map(t, [(0.0, rgb('#0f7a40')), (0.3, rgb('#2fb24e')), (0.65, rgb('#5cd45a')),
                           (1.0, rgb('#26994a'))])
    col = mix(col, LEAF_DEEP, (across ** 2 * 0.35)[..., None])
    return mix(col, LEAF_DEEP, dark)


def frond(c, base, ang, length, width, droop=0.25, lift=0.35, dark=0.0,
          leaflets=17, fold=1.0, seed=0):
    """Palm frond: separate pointed leaflets along a drooping arched curve.
    ang in degrees (0 = right, 90 = down in image space)."""
    a = math.radians(ang)
    dx, dy = math.cos(a), math.sin(a)
    bx, by = base
    # control point lifted up (fronds arch up then droop down)
    p1 = (bx + dx * length * 0.55, by + dy * length * 0.55 - length * lift)
    p2 = (bx + dx * length, by + dy * length + length * droop - length * lift * 0.3)
    pts = bezier(base, p1, p2, 30)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    L = Layer(c, min(xs) - width - 6, min(ys) - width - 6,
              max(xs) - min(xs) + 2 * width + 12, max(ys) - min(ys) + 2 * width + 12)
    dist, t, s = spine(L, pts)
    arc = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
    prof = np.sin(np.pi * clamp01(t) ** 0.8) ** 0.6 * width * (1 - 0.2 * t)
    prof = np.maximum(prof, 0.01)
    au = np.abs(s) / prof
    # leaflets swept toward the tip; each a pointed blade (gap grows outward)
    phase = t * leaflets - au * 1.1 + (s > 0) * 0.5
    fr = phase - np.floor(phase)
    spacing = arc / leaflets
    half = 0.5 * (1 - clamp01(au) ** 2.2) * 0.94 + 0.05
    blade_sdf = (np.abs(fr - 0.5) - half) * spacing * 0.9
    sdf = np.maximum(dist - prof, np.where(au < 0.18, -1, blade_sdf))
    cov = L.cover(sdf)
    across = clamp01(au)
    col = leaf_colors(t, across, dark)
    # fold: one half of the frond lit, the other in shade
    side = np.sign(s) * np.sign(-dx + 1e-3) * fold
    col = col * (1.0 + 0.10 * side)[..., None]
    # each leaflet has a crease: one side light, the other darker + gloss
    crease = (fr - 0.5) / (half + 1e-3)
    col = col * (1.0 + 0.16 * np.clip(crease, -1, 1))[..., None]
    gloss = np.exp(-((crease - 0.45) / 0.3) ** 2) * (1 - across) ** 0.7 * smoothstep(0.05, 0.3, t)
    col = col + (gloss * 0.36 * (1 - dark))[..., None] * rgb('#e8ffb0')
    L.over(clamp01(col), cov)
    # midrib: pale yellow-green line with a soft dark side
    rib_w = 0.8 + 2.0 * (1 - t)
    rib = dist - rib_w * (t < 0.97)
    L.over(rgb('#d6f78a'), L.cover(rib) * 0.75 * cov)
    L.over(LEAF_DEEP, L.cover(np.abs(s + rib_w + 1.0) - 0.7) * 0.3 * cov)
    L.commit()


def palm(c, base, top, trunk_w=(21, 13), fronds=(), coconuts=(), seed=0):
    """Curved ringed trunk from base to top (crown position)."""
    bx, by = base
    tx, ty = top
    mid = (bx + (tx - bx) * 0.15 + (tx - bx) * 0.25, (by + ty) / 2)
    bend = getattr(palm, 'bend', 0.0)
    pts = bezier(base, (bx + (tx - bx) * 0.05 - (tx - bx) * bend, by - (by - ty) * 0.55), top, 30)
    L = Layer(c, min(bx, tx) - 80, ty - 20, abs(tx - bx) + 160, by - ty + 40)
    dist, t, s = spine(L, pts)
    w = trunk_w[0] + (trunk_w[1] - trunk_w[0]) * t
    length = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                 for i in range(len(pts) - 1))
    rings = length / 17.0
    ph = t * rings
    fr = ph - np.floor(ph)
    # each ring segment bulges a little and its lower lip overlaps the next
    bulge = 1.0 + 0.09 * np.sin(np.pi * fr) - 0.05 * (fr < 0.12)
    w_eff = w * bulge
    sdf = np.maximum(dist - w_eff, L.Y - (by - 4))
    u = np.clip(s / np.maximum(w_eff, 1e-3), -1, 1)
    nz = np.sqrt(1 - u * u)
    light = clamp01(0.5 - 0.55 * u + 0.25 * nz)
    base_col = gradient_map(light, [(0.0, rgb('#8a5a38')), (0.45, rgb('#c48d5a')),
                                    (0.8, rgb('#e9c08a')), (1.0, rgb('#fbe3b8'))])
    # segment shading: top of every ring lighter, bottom darker
    seg = gradient_map(fr, [(0.0, rgb('#6e4428')), (0.15, rgb('#d9b07a')), (0.6, rgb('#f2d3a0')),
                            (1.0, rgb('#a87447'))])
    col = base_col * (0.55 + 0.6 * seg)
    # ring lines
    col = mix(col, rgb('#5a3620'), (smoothstep(0.1, 0.0, fr) * 0.75)[..., None])
    # glossy spec stripe on the lit side
    hl = np.exp(-((u + 0.45) / 0.16) ** 2) * (0.4 + 0.6 * smoothstep(0.1, 0.7, fr))
    col = col + hl[..., None] * 0.35
    # darken base where it meets the ground, darken top under the crown
    col = col * (1 - 0.25 * smoothstep(0.12, 0.0, t))[..., None]
    col = col * (1 - 0.35 * smoothstep(0.85, 1.0, t))[..., None]
    cov = L.cover(sdf)
    # flared root base
    root = sd_ellipse(L, bx, by - 6, trunk_w[0] * 1.35, 9)
    rn = sphere_normals(L, bx, by - 4, trunk_w[0] * 1.45, 10)
    rcol = mix(rgb('#9c6a42'), rgb('#f0cc96'), lambert(rn)[..., None]) + spec(rn, 30)[..., None] * 0.2
    L.over(clamp01(rcol), L.cover(root))
    L.over(clamp01(col), cov)
    L.commit()


def coconut(c, x, y, r):
    d = sd_circle(c, x, y, r)
    n = sphere_normals(c, x, y, r)
    l = lambert(n)
    col = gradient_map(l, [(0.0, rgb('#4a2a18')), (0.5, rgb('#8c5426')), (1.0, rgb('#d99a52'))])
    col = col + spec(n, 40)[..., None] * 0.7
    c.over(clamp01(col), c.cover(d))
    inner_shadow(c, d, 3, 0.3, (0.2, 0.1, 0.05))


def draw_palm(variant):
    W, H = 400, 450
    c = Canvas(W, H, ss=3)
    flip = 1 if variant == 1 else -1
    if variant == 1:
        bx, by = W / 2 - 34, H - 22
        tx, ty = W / 2 + 18, 176
    else:
        bx, by = W / 2 + 40, H - 22
        tx, ty = W / 2 - 22, 160
    contact_shadow(c, bx, by - 2, 62, 16, 0.32)
    palm(c, (bx, by), (tx, ty), trunk_w=(20, 12))
    crown = (tx, ty - 4)
    # (angle, length, width, droop, lift, darkness); angles for variant 1
    back = [(-165, 150, 26, 0.45, 0.30, 0.38), (-128, 128, 26, 0.32, 0.34, 0.42),
            (-90, 112, 24, 0.22, 0.36, 0.45), (-52, 128, 26, 0.32, 0.34, 0.42),
            (-15, 152, 26, 0.45, 0.30, 0.38)]
    front = [(196, 168, 30, 0.62, 0.26, 0.10), (-16 + 360, 172, 30, 0.62, 0.26, 0.05),
             (152, 140, 30, 0.55, 0.24, 0.0), (28, 142, 30, 0.55, 0.24, 0.0),
             (118, 104, 26, 0.55, 0.20, 0.0), (64, 108, 26, 0.55, 0.20, 0.0)]
    if variant == 2:
        back = [(-172, 156, 26, 0.5, 0.28, 0.38), (-140, 124, 25, 0.32, 0.34, 0.42),
                (-100, 106, 24, 0.2, 0.36, 0.45), (-62, 120, 26, 0.3, 0.34, 0.42),
                (-24, 146, 26, 0.45, 0.30, 0.38)]
        front = [(188, 176, 30, 0.66, 0.26, 0.08), (352, 160, 30, 0.58, 0.26, 0.05),
                 (160, 132, 30, 0.6, 0.24, 0.0), (20, 150, 30, 0.6, 0.24, 0.0),
                 (126, 98, 26, 0.6, 0.2, 0.0), (80, 116, 27, 0.6, 0.2, 0.0)]
    rng = np.random.default_rng(variant * 7)
    for ang, ln, wd, dr, lf, dk in back:
        frond(c, crown, ang if flip == 1 else 180 - ang, ln, wd, droop=dr, lift=lf, dark=dk)
    # dark crown core so gaps between fronds read as depth
    core = sd_ellipse(c, crown[0], crown[1] + 4, 26, 16)
    c.shadow(core, 10, 0.55, (0.03, 0.25, 0.18))
    for ang, ln, wd, dr, lf, dk in front:
        frond(c, crown, ang if flip == 1 else 180 - ang, ln, wd, droop=dr, lift=lf, dark=dk)
    # coconuts hang just under the crown
    for dx, dy, r in [(-14, 14, 13), (13, 15, 13), (-1, 25, 12.5)]:
        coconut(c, crown[0] + dx * flip, crown[1] + dy, r)
    # crown cap: glossy leaf-base knot
    cap = sd_ellipse(c, crown[0], crown[1] - 2, 13, 8)
    cn = sphere_normals(c, crown[0], crown[1] - 2, 13, 8)
    c.over(clamp01(mix(LEAF_DARK, LEAF_LIGHT, lambert(cn)[..., None]) + spec(cn, 30)[..., None] * 0.4),
           c.cover(cap))
    return c.image(), {'pivot': pivot(c, bx, by)}


@prop('palm_1')
def palm_1():
    return draw_palm(1)


@prop('palm_2')
def palm_2():
    return draw_palm(2)


def leaf(c, base, ang, length, width, bend=0.25, dark=0.0, light=0.0,
         hue=None, rib=True):
    """Simple glossy pointed leaf (used by bushes, flowers, vines, ferns)."""
    a = math.radians(ang)
    dx, dy = math.cos(a), math.sin(a)
    bx, by = base
    # bend the leaf sideways (perpendicular) and slightly down
    px, py = -dy, dx
    p1 = (bx + dx * length * 0.5 + px * length * bend * 0.5, by + dy * length * 0.5 + py * length * bend * 0.5)
    p2 = (bx + dx * length + px * length * bend * 0.2, by + dy * length + py * length * bend * 0.2 + length * 0.05)
    pts = bezier(base, p1, p2, 14)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = width + 4
    L = Layer(c, min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)
    dist, t, s = spine(L, pts)
    prof = np.sin(np.pi * clamp01(t) ** 0.85) ** 0.8 * width
    sdf = dist - prof
    au = clamp01(np.abs(s) / np.maximum(prof, 0.1))
    stops = hue or [(0.0, LEAF_DARK), (0.4, LEAF_MID), (1.0, rgb('#7ee36a'))]
    col = gradient_map(t * 0.6 + 0.4 * (1 - au), stops)
    # leaf halves: lit half / shaded half
    side = np.sign(s) * (1 if dx < 0.3 else -1)
    col = col * (1 + 0.12 * side)[..., None]
    col = mix(col, LEAF_DEEP, (au ** 3 * 0.35 + dark)[..., None] if dark else (au ** 3 * 0.35)[..., None])
    col = mix(col, rgb('#d9ff9a'), light)
    # glossy highlight streak on the lit half
    gl = np.exp(-((au - 0.45) / 0.22) ** 2) * (side > 0) * smoothstep(0.1, 0.4, t) * smoothstep(0.95, 0.6, t)
    col = col + (gl * 0.35 * (1 - dark))[..., None]
    L.over(clamp01(col), L.cover(sdf))
    if rib:
        L.over(rgb('#d6f78a'), L.cover(dist - 0.6 - 0.9 * (1 - t)) * L.cover(sdf + 1) * 0.6 * (1 - dark))
    L.commit()


def blob_sdf(c, cx, cy, r, lobes=7, amp=0.07, phase=0.0, squash=0.85):
    """Rounded leafy blob: circle with scalloped edge."""
    dx, dy = c.X - cx, (c.Y - cy) / squash
    th = np.arctan2(dy, dx)
    rr = r * (1 + amp * (np.abs(np.sin(th * lobes / 2 + phase)) * 2 - 1))
    return (np.hypot(dx, dy) - rr) * squash


def leafy_blob(c, cx, cy, r, seed, dark=0.0, squash=0.85, n_leaves=9):
    """Glossy shaded foliage blob with individual leaves on its surface."""
    rng = np.random.default_rng(seed)
    L = Layer(c, cx - r * 1.5, cy - r * 1.5, r * 3, r * 3)
    d = blob_sdf(L, cx, cy, r, lobes=9, amp=0.06, phase=rng.random() * 3, squash=squash)
    n = sphere_normals(L, cx, cy, r * 1.05, r * squash * 1.05)
    l = lambert(n)
    col = gradient_map(l, [(0.0, LEAF_DEEP), (0.35, LEAF_DARK), (0.7, LEAF_MID), (1.0, rgb('#a6ef6a'))])
    col = mix(col, LEAF_DEEP, dark)
    col = col + spec(n, 18)[..., None] * 0.25 * (1 - dark)
    L.over(clamp01(col), L.cover(d))
    inner_shadow(L, d, r * 0.25, 0.25, (0.02, 0.25, 0.15))
    L.commit()
    # leaves radiating over the surface (upper ones lighter)
    for k in range(n_leaves):
        a = rng.uniform(-math.pi, math.pi * 0.15) if k < n_leaves - 2 else rng.uniform(0, math.pi)
        rad = rng.uniform(0.25, 0.85) * r
        lx, ly = cx + math.cos(a) * rad * 0.9, cy + math.sin(a) * rad * squash * 0.9
        ang = math.degrees(math.atan2(ly - cy, lx - cx)) + rng.uniform(-25, 25)
        up = clamp01(np.array(0.5 - math.sin(a) * 0.5))
        leaf(c, (lx - math.cos(math.radians(ang)) * r * 0.25, ly - math.sin(math.radians(ang)) * r * 0.25),
             ang, r * rng.uniform(0.55, 0.75), r * rng.uniform(0.17, 0.22), bend=rng.uniform(-0.3, 0.3),
             dark=float(dark * 0.8 + (1 - up) * 0.15), light=float(up * 0.15), rib=True)


def hibiscus(c, x, y, r, rot=0.0, col=('#ffd1ec', '#ff6fb8', '#d11f7a'), squash=0.8, center='#ffe066'):
    """Five-petal flower seen from slightly above."""
    L = Layer(c, x - r * 1.4, y - r * 1.4, r * 2.8, r * 2.8)
    dx, dy = L.X - x, (L.Y - y) / squash
    th = np.arctan2(dy, dx) - rot
    rho = np.hypot(dx, dy)
    # petal shape: radius modulated by 5 rounded lobes
    lobe = np.abs(np.cos(th * 2.5))
    pr = r * (0.62 + 0.38 * lobe ** 0.6)
    sdf = (rho - pr) * squash
    t = clamp01(rho / r)
    pc = gradient_map(t, [(0.0, rgb(col[2])), (0.35, rgb(col[1])), (0.85, rgb(col[0])), (1.0, rgb('#ffffff'))])
    # petal separation lines + ripple veins
    sep = smoothstep(0.12, 0.0, lobe) * smoothstep(0.2, 0.5, t)
    pc = mix(pc, rgb(col[2]), (sep * 0.5)[..., None])
    vein = (np.sin(th * 30) * 0.5 + 0.5) * smoothstep(0.2, 0.8, t) * 0.08
    pc = pc * (1 - vein)[..., None]
    # upper-left lit, lower-right shaded
    lit = clamp01(0.5 - (dx * 0.6 + dy * 0.8) / (r * 2))
    pc = pc * (0.85 + 0.3 * lit)[..., None]
    L.over(clamp01(pc), L.cover(sdf))
    # glossy sheen on upper petals
    hl = sd_ellipse(L, x - r * 0.3, y - r * 0.45 * squash, r * 0.45, r * 0.22)
    L.over(WHITE, L.cover(op_inter(hl, sdf + 1), 3) * 0.45)
    # stamen
    st = sd_circle(L, x, y, r * 0.16)
    sn = sphere_normals(L, x, y, r * 0.16)
    L.over(clamp01(mix(rgb('#e09a1a'), rgb(center), lambert(sn)[..., None]) + spec(sn, 30)[..., None] * 0.6),
           L.cover(st))
    L.commit()


def plumeria(c, x, y, r, rot=0.0, squash=0.8):
    """White five-petal flower with a yellow heart."""
    L = Layer(c, x - r * 1.4, y - r * 1.4, r * 2.8, r * 2.8)
    for k in range(5):
        a = rot + k / 5 * 2 * math.pi
        px, py = x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.5 * squash
        d = sd_ellipse(L, px, py, r * 0.52, r * 0.34) if abs(math.cos(a)) > 0.7 else sd_ellipse(L, px, py, r * 0.38, r * 0.45 * squash)
        t = clamp01(np.hypot(L.X - x, (L.Y - y) / squash) / r)
        pc = gradient_map(t, [(0.0, rgb('#ffd34d')), (0.35, rgb('#fff3c4')), (0.6, rgb('#ffffff')), (1.0, rgb('#e8f0fb'))])
        pc = pc * (0.88 + 0.12 * (math.sin(-a) * 0.5 + 0.5))
        L.over(clamp01(pc), L.cover(d))
        inner_shadow(L, d, 2.5, 0.25, (0.6, 0.65, 0.8))
    L.over(rgb('#ffcf3a'), L.cover(sd_circle(L, x, y, r * 0.14)))
    L.commit()


@prop('bush_1')
def bush_1():
    return draw_bush(1)


@prop('bush_2')
def bush_2():
    return draw_bush(2)


def draw_bush(variant):
    W, H = 200, 160
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 16
    contact_shadow(c, cx, by - 2, 92, 18, 0.30)
    rng = np.random.default_rng(variant * 13)
    # back row, then front row (lower = closer)
    blobs = [(-38, -62, 36, 0.15), (30, -66, 38, 0.15), (-2, -84, 34, 0.1),
             (-56, -34, 32, 0.0), (52, -36, 34, 0.0), (0, -46, 42, 0.0)]
    if variant == 2:
        blobs = [(-30, -70, 36, 0.15), (34, -58, 34, 0.15), (-60, -36, 30, 0.0),
                 (58, -30, 30, 0.0), (-8, -44, 44, 0.0)]
    for i, (dx, dy, r, dk) in enumerate(blobs):
        leafy_blob(c, cx + dx, by + dy, r, seed=variant * 100 + i, dark=dk, n_leaves=8)
    if variant == 2:
        for (fx, fy, fr, rot) in [(-34, -76, 15, 0.3), (30, -60, 13, 1.1), (-52, -38, 12, 0.6),
                                  (6, -36, 15, 2.0), (56, -32, 11, 0.2)]:
            hibiscus(c, cx + fx, by + fy, fr, rot)
    return c.image(), {'pivot': pivot(c, cx, by)}


def draw_flowers(variant):
    W, H = 128, 112
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 12
    contact_shadow(c, cx, by - 2, 50, 11, 0.28)
    rng = np.random.default_rng(variant * 5)
    for k, ang in enumerate([-160, -125, -95, -60, -25, -140, -40, -80]):
        ln = 44 if k < 5 else 34
        leaf(c, (cx + rng.uniform(-6, 6), by - 4), ang + rng.uniform(-8, 8), ln, 9,
             bend=0.35 * (1 if ang < -90 else -1), dark=0.15 if k < 5 else 0.0)
    if variant == 1:
        for fx, fy, fr, rot in [(-24, -46, 17, 0.2), (20, -56, 18, 1.0), (-2, -30, 15, 2.2)]:
            hibiscus(c, cx + fx, by + fy, fr, rot)
    else:
        for fx, fy, fr, rot in [(-26, -40, 13, 0.1), (0, -60, 14, 0.7), (24, -42, 13, 1.4), (2, -28, 12, 0.4)]:
            plumeria(c, cx + fx, by + fy, fr, rot)
        hibiscus(c, cx - 4, by - 46, 10, 1.2)
    return c.image(), {'pivot': pivot(c, cx, by)}


@prop('flowers_1')
def flowers_1():
    return draw_flowers(1)


@prop('flowers_2')
def flowers_2():
    return draw_flowers(2)


@prop('fern_1')
def fern_1():
    W, H = 180, 150
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 14
    contact_shadow(c, cx, by - 2, 64, 13, 0.30)
    base = (cx, by - 6)
    for ang, ln, dk in [(-150, 82, 0.35), (-118, 92, 0.35), (-62, 92, 0.35), (-30, 82, 0.35),
                        (-170, 70, 0.1), (-10, 70, 0.1), (-135, 88, 0.0), (-45, 88, 0.0), (-90, 80, 0.05)]:
        frond(c, base, ang, ln, 17, droop=0.55, lift=0.5, dark=dk + 0.12, leaflets=11)
    return c.image(), {'pivot': pivot(c, cx, by)}


def draw_rock(variant):
    W, H = (150, 120) if variant == 1 else (128, 96)
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 12
    if variant == 1:
        contact_shadow(c, cx, by - 3, 68, 15, 0.32)
        d = op_smooth_union(sd_ellipse(c, cx - 8, by - 40, 46, 38), sd_ellipse(c, cx + 24, by - 26, 34, 24), 14)
        d = op_smooth_union(d, sd_ellipse(c, cx - 36, by - 18, 24, 16), 10)
        top, mx = by - 78, cx - 6
    else:
        contact_shadow(c, cx, by - 3, 58, 13, 0.32)
        d = op_smooth_union(sd_ellipse(c, cx + 6, by - 27, 42, 27), sd_ellipse(c, cx - 26, by - 16, 22, 15), 10)
        top, mx = by - 54, cx + 4
    d = np.maximum(d, c.Y - (by - 1))  # flat base
    n = normals(c, height_bevel(d, 34))
    l = lambert(n)
    # pale warm stone: cream top, blue-grey underside, soft bounce light at the base
    col = gradient_map(l, [(0.0, rgb('#7d8fae')), (0.35, rgb('#b9c3d3')), (0.7, rgb('#ece8de')),
                           (1.0, rgb('#fffdf6'))])
    col = col + spec(n, 40)[..., None] * 0.45
    bounce = smoothstep(by - 18, by, c.Y) * 0.25
    col = mix(col, rgb('#9fe6f0'), bounce[..., None])
    noise = value_noise(c.X.shape[1], c.X.shape[0], 24 * c.ss, seed=variant)
    col = col * (0.95 + 0.07 * noise)[..., None]
    c.over(clamp01(col), c.cover(d))
    # moss cap: wavy lower edge, slightly raised, fuzzy rim
    wave = (np.sin((c.X - mx) * 0.21 + variant) * 4 + np.sin((c.X - mx) * 0.53) * 2.5)
    reach = (by - top) * 0.42
    edge = c.Y - (top + reach + wave - np.abs(c.X - mx) * 0.18)
    fuzz = value_noise(c.X.shape[1], c.X.shape[0], 3 * c.ss, seed=variant + 9, octaves=2)
    msdf = np.maximum(d + 1.5, edge + (fuzz - 0.5) * 3)
    mn = normals(c, height_bevel(d, 34) + height_bevel(msdf, 4))
    ml = lambert(mn)
    mcol = gradient_map(ml * 0.8 + fuzz * 0.2, [(0.0, rgb('#1f8a44')), (0.45, rgb('#48c455')),
                                                (0.8, rgb('#8ee36a')), (1.0, rgb('#d4ff9a'))])
    mcol = mcol + spec(mn, 25)[..., None] * 0.2
    # shadow the moss casts on the stone
    c.over(rgb('#56708f'), c.cover(msdf - 3, 3) * (1 - c.cover(msdf)) * c.cover(d) * 0.25 * (c.Y > top + reach * 0.5))
    c.over(clamp01(mcol), c.cover(msdf))
    inner_shadow(c, d, 7, 0.18, (0.25, 0.35, 0.5))
    # glossy highlights
    sheen(c, d, cx - 22, top + reach + 10, 10, 5, 0.55, 3)
    sheen(c, msdf, mx - 14, top + 10, 12, 4, 0.35, 3)
    return c.image(), {'pivot': pivot(c, cx, by)}


@prop('rock_1')
def rock_1():
    return draw_rock(1)


@prop('rock_2')
def rock_2():
    return draw_rock(2)


# ============================================================================
# Glass City kit: 3/4-view cylinders, rings, gems, fades
# ============================================================================
K = 0.42   # ellipse ratio of horizontal circles in the 3/4 view

CHROME_U = [(0.0, rgb('#5d7799')), (0.10, rgb('#c9dcf0')), (0.2, rgb('#ffffff')), (0.32, rgb('#d7e9f8')),
            (0.45, rgb('#86a3c6')), (0.56, rgb('#38557f')), (0.68, rgb('#9fc0e0')), (0.80, rgb('#ffffff')),
            (0.92, rgb('#a9c2dd')), (1.0, rgb('#6b85a6'))]


def chrome_u(u):
    """Chrome look for a vertical cylinder as a function of lateral u (-1..1)."""
    return gradient_map(u * 0.5 + 0.5, CHROME_U)


def cyl_normals(c, cx, w):
    u = np.clip((c.X - cx) / w, -1, 1)
    nz = np.sqrt(1 - u * u)
    return np.dstack([u, np.zeros_like(u), nz]), u


def cyl_sdf(c, cx, y_top, y_bot, w, k=K):
    """Silhouette of a vertical cylinder body (top face drawn separately)."""
    body = sd_box(c, cx, (y_top + y_bot) / 2, w, (y_bot - y_top) / 2)
    return op_union(body, sd_ellipse(c, cx, y_bot, w, w * k), sd_ellipse(c, cx, y_top, w, w * k))


def top_normals(c, cx, cy, w, k=K, dome=0.35):
    dx = (c.X - cx) / w
    dy = (c.Y - cy) / (w * k)
    n = np.dstack([dx * dome, dy * dome * 0.6 - 0.45, np.ones_like(dx)])
    return n / np.linalg.norm(n, axis=2, keepdims=True)


def ceramic_cyl(c, cx, y_top, y_bot, w, k=K, top=True, base='#f7fbff', shade='#9fb6d8'):
    d = cyl_sdf(c, cx, y_top, y_bot, w, k)
    n, u = cyl_normals(c, cx, w)
    col = mat_plastic(n, base, shade, gloss=0.6)
    # vertical sheen stripe
    col = col + (np.exp(-((u + 0.5) / 0.18) ** 2) * 0.25)[..., None]
    c.over(clamp01(col), c.cover(d))
    if top:
        td = sd_ellipse(c, cx, y_top, w, w * k)
        tn = top_normals(c, cx, y_top, w, k)
        c.over(mat_plastic(tn, '#ffffff', '#c3d3ea', gloss=0.7), c.cover(td))
        c.over(WHITE, c.cover(np.abs(td + 1.0) - 0.8) * 0.6)
    return d


def chrome_cyl(c, cx, y_top, y_bot, w, k=K, top=True):
    d = cyl_sdf(c, cx, y_top, y_bot, w, k)
    u = np.clip((c.X - cx) / w, -1, 1)
    col = chrome_u(u)
    # the lower edge curves, so bend the reflection a little with height
    c.over(col, c.cover(d))
    if top:
        td = sd_ellipse(c, cx, y_top, w, w * k)
        tn = top_normals(c, cx, y_top, w, k, dome=0.8)
        c.over(chrome(tn), c.cover(td))
    return d


def chrome_ring(c, cx, cy, w, thick, k=K, lip=None):
    """Chrome band around a cylinder at height cy: front strip + thin top lip."""
    d = band_sdf(c, cx, cy - thick, cy + thick, w, k)
    u = np.clip((c.X - cx) / w, -1, 1)
    arc = w * k * np.sqrt(1 - u * u)
    yy = clamp01((c.Y - (cy - thick + arc)) / (2 * thick))
    col = chrome_u(u * 0.85)
    col = col * (1.12 - 0.4 * yy)[..., None]
    c.over(clamp01(col), c.cover(d))
    # bright top lip (a thin elliptical rim)
    lip = lip or min(thick * 1.2, w * 0.25)
    td = np.abs(sd_ellipse(c, cx, cy - thick, w - lip / 2, (w - lip / 2) * k)) - lip / 2
    t = clamp01((c.Y - (cy - thick - w * k)) / (2 * w * k))
    back = smoothstep(cy - thick + 1, cy - thick - 1, c.Y)
    c.over(mix(rgb('#ffffff'), rgb('#9fb8d6'), t[..., None]), c.cover(td) * (0.95 - 0.45 * back))
    return d


def band_sdf(c, cx, y_top, y_bot, w, k=K):
    """Front face strip of a cylinder between two heights (no top face)."""
    u = np.clip((c.X - cx) / w, -1, 1)
    arc = w * k * np.sqrt(1 - u * u)
    return op_inter(np.abs(c.X - cx) - w,
                    op_inter((y_top + arc) - c.Y, c.Y - (y_bot + arc)))


def glass_cyl(c, cx, y_top, y_bot, w, k=K, alpha=0.72, tint=('#c8f6ff', '#4fd2f5', '#1590d6'),
              floors=0, glow=0.0, band=False):
    """Translucent aqua glass cylinder with fresnel edges and reflection strips."""
    d = band_sdf(c, cx, y_top, y_bot, w, k) if band else cyl_sdf(c, cx, y_top, y_bot, w, k)
    u = np.clip((c.X - cx) / w, -1, 1)
    t = clamp01((c.Y - y_top) / (y_bot - y_top))
    col = gradient_map(t, [(0.0, rgb(tint[0])), (0.35, rgb(tint[1])), (1.0, rgb(tint[2]))])
    fres = np.abs(u) ** 3
    col = mix(col, rgb('#e6fdff'), (fres * 0.6)[..., None])
    a = alpha * (0.75 + 0.25 * fres)
    if glow:
        core = np.exp(-(u / 0.35) ** 2) * glow
        col = col + core[..., None] * rgb('#9ffcff') * 0.6
        a = a + core * 0.2
    cov = c.cover(d)
    c.over(clamp01(col), cov * a)
    # internal floors following the cylinder curvature
    if floors:
        for i in range(1, floors):
            fy = y_top + (y_bot - y_top) * i / floors
            line = np.abs(c.Y - (fy + w * k * np.sqrt(1 - u * u))) - 0.9
            c.over(rgb('#e8fdff'), c.cover(line) * cov * 0.45)
    # reflection strips
    s1 = np.abs(u + 0.55) - 0.10
    s2 = np.abs(u - 0.62) - 0.035
    c.over(WHITE, c.cover(s1 * w, 1.5) * cov * 0.55 * (0.6 + 0.4 * (1 - t)))
    c.over(WHITE, c.cover(s2 * w, 1.0) * cov * 0.45)
    c.over(WHITE, c.cover(np.abs(d + 1.0) - 0.7) * 0.5)
    return d


def fade_edges(c, margin=6):
    """Fade any glow to zero near the borders so nothing gets clipped."""
    wx = smoothstep(0, margin, c.X) * smoothstep(c.w, c.w - margin, c.X)
    wy = smoothstep(0, margin, c.Y) * smoothstep(c.h, c.h - margin, c.Y)
    w = wx * wy
    c.P = c.P * w[..., None]
    c.A = c.A * w


def project(cx, cy, X, Y, Z, tilt=0.5):
    """3D -> screen. Y up, Z toward the viewer (front = lower on screen)."""
    return (cx + X, cy - Y * math.sqrt(1 - tilt * tilt) + Z * tilt)


VIEW = np.array([0.0, 0.5, math.sqrt(0.75)])   # toward the camera (Y up, Z front)
L3 = np.array([-0.5, 0.75, 0.45])
L3 = L3 / np.linalg.norm(L3)


def gem(c, cx, cy, w, h_top, h_bot, sides=8, table=0.45, rot=0.2,
        pal=('#e8fbff', '#5fd8ff', '#1b6fd6', '#0a2f8a'), alpha=0.92, lit=0.0):
    """Faceted gem: table + crown down to the girdle, pavilion to a point."""
    pts_g, pts_t = [], []
    for i in range(sides):
        a = rot + i / sides * 2 * math.pi
        pts_g.append(np.array([math.cos(a) * w, 0.0, math.sin(a) * w]))
        pts_t.append(np.array([math.cos(a) * w * table, h_top, math.sin(a) * w * table]))
    bottom = np.array([0.0, -h_bot, 0.0])
    faces = []
    for i in range(sides):
        j = (i + 1) % sides
        faces.append([pts_t[i], pts_t[j], pts_g[j], pts_g[i]])   # crown
        faces.append([pts_g[i], pts_g[j], bottom])               # pavilion
    faces.append(pts_t)                                          # table
    pal = [rgb(p) for p in pal]
    pad = w + 10
    L = Layer(c, cx - pad, cy - h_top - pad, 2 * pad, h_top + h_bot + 2 * pad)
    drawn = []
    for f in faces:
        ctr = sum(f) / len(f)
        nrm = np.cross(f[1] - f[0], f[2] - f[0])
        nrm = nrm / (np.linalg.norm(nrm) + 1e-9)
        if np.dot(nrm, ctr) < 0:
            nrm = -nrm
        vis = np.dot(nrm, VIEW)
        depth = np.dot(ctr, VIEW)
        drawn.append((depth, vis, nrm, f))
    drawn.sort(key=lambda x: x[0])
    for depth, vis, nrm, f in drawn:
        poly = [project(cx, cy, *p) for p in f]
        d = sd_poly(L, poly)
        diff = max(0.0, float(np.dot(nrm, L3)))
        hv = L3 + VIEW
        hv = hv / np.linalg.norm(hv)
        sp = max(0.0, float(np.dot(nrm, hv))) ** 30
        if vis <= 0:
            # back facets seen through the stone: deep colour
            col = pal[3] * 0.9 + pal[2] * 0.1
            L.over(col, L.cover(d) * 0.9)
            continue
        tone = 0.25 + 0.75 * diff
        col = gradient_map(np.array(tone), [(0.0, pal[3]), (0.4, pal[2]), (0.75, pal[1]), (1.0, pal[0])])
        # gradient inside each facet so it looks like glass, not flat paint
        ys = [p[1] for p in poly]
        g = clamp01((L.Y - min(ys)) / (max(ys) - min(ys) + 1e-3))
        fc = mix(col * 1.12, col * 0.82, g[..., None])
        fc = fc + sp * 0.9 + lit * 0.25
        L.over(clamp01(fc), L.cover(d))
        # bright facet edges
        L.over(rgb('#e9fdff'), L.cover(np.abs(d) - 0.55) * 0.55)
    L.commit()


# ============================================================================
# Puzzle objects
# ============================================================================

@prop('shard')
def shard():
    W, H = 128, 140
    c = Canvas(W, H, ss=3)
    cx, cy = W / 2, 56
    contact_shadow(c, cx, H - 16, 30, 7, 0.28)
    halo(c, sd_circle(c, cx, cy + 6, 26), GLOW, 26, 0.55)
    gem(c, cx, cy, 40, 16, 54, sides=8, table=0.5, rot=0.39,
        pal=('#f2fdff', '#6fe4ff', '#1f7fe6', '#0b2c8f'))
    # inner glow + sparkles
    c.add(rgb('#bff8ff'), np.exp(-(((c.X - cx) / 14) ** 2 + ((c.Y - cy - 10) / 18) ** 2)) * 0.35)
    sparkle(c, cx - 15, cy - 9, 12, 0.9)
    sparkle(c, cx + 16, cy + 18, 7, 0.6)
    fade_edges(c)
    return c.image(), {'pivot': pivot(c, cx, H - 16)}


def crystal(c, cx, cy, s, lit):
    """Floating elongated bipyramid crystal (pylon top)."""
    if lit:
        halo(c, sd_ellipse(c, cx, cy, s * 0.6, s * 1.2), GLOW, s * 1.6, 0.75)
        halo(c, sd_ellipse(c, cx, cy, s * 0.4, s), WHITE, s * 0.5, 0.4)
        pal = ('#ffffff', '#8ff8ff', '#20c4f0', '#0b6fb8')
    else:
        pal = ('#f4f8fc', '#c4d2e4', '#8ea3c2', '#5d7194')
    gem(c, cx, cy, s * 0.62, s * 1.1, s * 1.25, sides=6, table=0.0, rot=0.52, pal=pal, lit=0.4 if lit else 0)
    if lit:
        c.add(rgb('#dffcff'), np.exp(-(((c.X - cx) / (s * 0.3)) ** 2 + ((c.Y - cy) / (s * 0.8)) ** 2)) * 0.6)
        sparkle(c, cx - s * 0.25, cy - s * 0.7, s * 0.5, 0.9)


BAND_ON = ('#d8fbff', '#5fe0ff', '#1aa0e0')
BAND_OFF = ('#d7eef8', '#8fd0ea', '#4f9cc8')


def pedestal(c, cx, by, w, h, band_lit=0.0):
    """White ceramic pedestal (flared foot) with an aqua glass band + chrome ring."""
    ceramic_cyl(c, cx, by - 14, by, w * 1.18)
    ceramic_cyl(c, cx, by - h, by - 14, w)
    glass_cyl(c, cx, by - h * 0.66, by - h * 0.4, w + 0.5, alpha=0.92, glow=band_lit, band=True,
              tint=BAND_ON if band_lit else BAND_OFF)
    chrome_ring(c, cx, by - h, w * 1.08, 3.5)


def draw_pylon(lit):
    W, H = 176, 276
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 16 - 30 * K * 1.18
    contact_shadow(c, cx, by + 4, 58, 20, 0.32)
    pedestal(c, cx, by, 30, 72, band_lit=1.0 if lit else 0.0)
    # top dish of the pedestal + light it receives from the crystal
    ceramic_cyl(c, cx, by - 84, by - 74, 22)
    if lit:
        c.add(GLOW, np.exp(-(((c.X - cx) / 18) ** 2 + ((c.Y - (by - 84)) / 7) ** 2)) * 0.7)
    crystal(c, cx, by - 146, 34, lit)
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, cx, by)}


@prop('pylon_off')
def pylon_off():
    return draw_pylon(False)


@prop('pylon_on')
def pylon_on():
    return draw_pylon(True)


def prong(c, x0, y0, x1, y1, bend, w=4.5):
    """Chrome claw from (x0,y0) curving outward and up to its tip (x1,y1)."""
    pts = bezier((x0, y0), (x1 + bend, (y0 * 0.4 + y1 * 0.6)), (x1, y1), 18)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    L = Layer(c, min(xs) - 14, min(ys) - 14, max(xs) - min(xs) + 28, max(ys) - min(ys) + 28)
    dist, t, s = spine(L, pts)
    ww = w * (1.15 - 0.45 * t)
    d = dist - ww
    u = np.clip(s / ww, -1, 1)
    L.over(chrome_u(u * 0.9 * (1 if bend >= 0 else -1)), L.cover(d))
    tip = sd_circle(L, x1, y1, w * 0.95)
    L.over(chrome(sphere_normals(L, x1, y1, w * 0.95)), L.cover(tip))
    L.commit()


def draw_beacon(lit):
    W, H = 320, 500
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 14 - 100 * K
    contact_shadow(c, cx, by + 6, 136, 52, 0.32, core=0.6)
    band = BAND_ON if lit else BAND_OFF
    # stepped pedestal (bottom step first)
    ceramic_cyl(c, cx, by - 30, by, 100)
    glass_cyl(c, cx, by - 21, by - 9, 100.5, alpha=0.95, glow=0.6 if lit else 0.0, tint=band, band=True)
    chrome_ring(c, cx, by - 30, 100, 2.5)
    ceramic_cyl(c, cx, by - 68, by - 33, 80)
    chrome_ring(c, cx, by - 68, 81, 3)
    ceramic_cyl(c, cx, by - 102, by - 70, 62)
    glass_cyl(c, cx, by - 94, by - 80, 62.5, alpha=0.95, glow=0.8 if lit else 0.0, tint=band, band=True)
    chrome_ring(c, cx, by - 102, 63, 3)
    # slim column of aqua glass with a glowing core
    glass_cyl(c, cx, by - 214, by - 104, 34, alpha=0.82, floors=5, glow=1.0 if lit else 0.15,
              tint=('#e6fdff', '#5fe0ff', '#178fd6') if lit else ('#dff2fb', '#86c9e8', '#3f8fc4'))
    ceramic_cyl(c, cx, by - 128, by - 110, 38, top=False)
    chrome_ring(c, cx, by - 128, 39, 2.5)
    # collar under the orb
    ceramic_cyl(c, cx, by - 236, by - 210, 48)
    chrome_ring(c, cx, by - 236, 50, 4)
    ocy, orr = by - 304, 64
    # back prongs, orb, front prongs
    for dx, bend in [(-1, -1), (1, 1)]:
        prong(c, cx + dx * 26, by - 240, cx + dx * 40, ocy - 22, dx * 34, 5)
    if lit:
        halo(c, sd_circle(c, cx, ocy, orr), GLOW, 90, 0.7, power=2.2)
        halo(c, sd_circle(c, cx, ocy, orr), WHITE, 26, 0.35)
    glass_orb(c, cx, ocy, orr, lit=0.75 if lit else 0.0, halo=False,
              tint=('#e9fdff', '#7ff0ff', '#22b4ec') if lit else ('#f2f8fd', '#bcd8ec', '#6f9cc6'),
              alpha=0.85 if lit else 0.55)
    seed_pal = ('#ffffff', '#cffcff', '#5fe8ff', '#20a8e0') if lit else ('#f4f8fc', '#c4d2e4', '#8ea3c2', '#5d7194')
    gem(c, cx, ocy + 6, 15, 20, 24, sides=6, table=0.0, rot=0.52, pal=seed_pal, lit=0.6 if lit else 0)
    if lit:
        c.add(WHITE, np.exp(-(np.hypot(c.X - cx, c.Y - ocy - 4) / 26) ** 2) * 0.55)
        sparkle(c, cx - 30, ocy - 34, 26, 1.0)
        sparkle(c, cx + 46, ocy + 22, 14, 0.7)
        # light spilling onto the collar
        c.add(GLOW, np.exp(-(((c.X - cx) / 40) ** 2 + ((c.Y - (by - 236)) / 10) ** 2)) * 0.5)
    for dx in (-1, 1):
        prong(c, cx + dx * 34, by - 232, cx + dx * 52, ocy + 8, dx * 30, 6)
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, cx, by)}


@prop('beacon_off')
def beacon_off():
    return draw_beacon(False)


@prop('beacon_on')
def beacon_on():
    return draw_beacon(True)


# ============================================================================
# Lights and Glass City decor
# ============================================================================

def pole(c, cx, y_top, y_bot, w):
    """Slim white ceramic pole (cylinder without visible top)."""
    return ceramic_cyl(c, cx, y_top, y_bot, w, top=False)


@prop('lamp')
def lamp():
    W, H = 150, 300
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 14 - 26 * K
    contact_shadow(c, cx, by + 3, 40, 14, 0.32)
    ceramic_cyl(c, cx, by - 14, by, 26)
    chrome_ring(c, cx, by - 14, 22, 3)
    ceramic_cyl(c, cx, by - 30, by - 16, 17)
    pole(c, cx, by - 160, by - 30, 7)
    chrome_cyl(c, cx, by - 104, by - 94, 9.5, top=False)
    chrome_cyl(c, cx, by - 62, by - 54, 9, top=False)
    # cup holding the orb
    chrome_cyl(c, cx, by - 170, by - 158, 13)
    ceramic_cyl(c, cx, by - 176, by - 168, 19)
    oy, r = by - 206, 32
    halo(c, sd_circle(c, cx, oy, r), GLOW, 50, 0.55)
    glass_orb(c, cx, oy, r, lit=0.8, halo=False, tint=('#ffffff', '#c9fbff', '#5fe0ff'))
    c.add(WHITE, np.exp(-(np.hypot(c.X - cx, c.Y - oy) / 14) ** 2) * 0.6)
    # little chrome finial on top
    chrome_cyl(c, cx, oy - r - 6, oy - r + 2, 5)
    sparkle(c, cx - 14, oy - 14, 12, 0.8)
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, cx, by)}


def draw_lantern(lit):
    W, H = 176, 276
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 14 - 24 * K
    contact_shadow(c, cx, by + 3, 38, 13, 0.32)
    ceramic_cyl(c, cx, by - 12, by, 24)
    chrome_ring(c, cx, by - 12, 18, 2.5)
    pole(c, cx, by - 150, by - 14, 6)
    chrome_cyl(c, cx, by - 96, by - 88, 8, top=False)
    # crescent-moon cradle: a chrome arc wrapping the orb from below
    oy, r = by - 196, 32
    ring_d = op_inter(np.abs(sd_circle(c, cx, oy, r + 6)) - 3.2, (oy - 4) - c.Y)
    if lit:
        halo(c, sd_circle(c, cx, oy, r), rgb('#b9a6ff'), 46, 0.5)
        halo(c, sd_circle(c, cx, oy, r), GLOW, 28, 0.45)
        glass_orb(c, cx, oy, r, lit=0.7, halo=False, tint=('#ffffff', '#d9ccff', '#8f7cf0'),
                  glow_col=rgb('#c8f6ff'))
        c.add(WHITE, np.exp(-(np.hypot(c.X - cx, c.Y - oy) / 13) ** 2) * 0.55)
    else:
        glass_orb(c, cx, oy, r, lit=0.0, halo=False, tint=('#5c6fa8', '#26346e', '#101a44'), alpha=0.92)
    n = normals(c, height_bevel(ring_d, 3))
    c.over(chrome(n), c.cover(ring_d))
    chrome_cyl(c, cx, by - 162, by - 150, 9)
    # tiny chrome finial
    c.over(chrome(sphere_normals(c, cx, oy - r - 8, 5)), c.cover(sd_circle(c, cx, oy - r - 8, 5)))
    if lit:
        sparkle(c, cx - 13, oy - 13, 11, 0.8)
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, cx, by)}


@prop('lantern_off')
def lantern_off():
    return draw_lantern(False)


@prop('lantern_on')
def lantern_on():
    return draw_lantern(True)


def draw_spire(variant):
    W, H = 150, 480
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 14 - 60 * K
    contact_shadow(c, cx, by + 4, 64, 24, 0.32)
    if variant == 1:
        ceramic_cyl(c, cx, by - 30, by, 60)
        chrome_ring(c, cx, by - 30, 60, 3)
        glass_cyl(c, cx, by - 330, by - 34, 50, floors=10, alpha=0.7, glow=0.35)
        for y in (by - 130, by - 230):
            chrome_ring(c, cx, y, 52, 3.5)
        chrome_ring(c, cx, by - 330, 54, 4)
        # ceramic dome cap
        ceramic_cyl(c, cx, by - 352, by - 334, 56)
        dome = op_inter(sd_ellipse(c, cx, by - 352, 46, 40), c.Y - (by - 352))
        dn = sphere_normals(c, cx, by - 352, 46, 40)
        c.over(mat_plastic(dn, '#ffffff', '#a9c0e0', 0.9), c.cover(op_union(dome, sd_ellipse(c, cx, by - 352, 46, 46 * K))))
        tip_y = by - 400
        chrome_cyl(c, cx, tip_y, by - 388, 4, top=False)
        halo(c, sd_circle(c, cx, tip_y - 6, 7), GLOW, 18, 0.7)
        glass_orb(c, cx, tip_y - 6, 8, lit=1.0, halo=False, tint=('#ffffff', '#bff8ff', '#5fe0ff'))
    else:
        ceramic_cyl(c, cx, by - 26, by, 58)
        chrome_ring(c, cx, by - 26, 58, 3)
        glass_cyl(c, cx, by - 160, by - 30, 48, floors=4, alpha=0.72, glow=0.3)
        chrome_ring(c, cx, by - 160, 50, 3.5)
        ceramic_cyl(c, cx, by - 176, by - 164, 44)
        glass_cyl(c, cx, by - 280, by - 178, 36, floors=3, alpha=0.72, glow=0.4)
        chrome_ring(c, cx, by - 280, 38, 3)
        ceramic_cyl(c, cx, by - 292, by - 284, 32)
        glass_cyl(c, cx, by - 350, by - 294, 24, floors=2, alpha=0.75, glow=0.5)
        chrome_ring(c, cx, by - 350, 26, 2.5)
        # pointed ceramic spike
        sp = sd_poly(c, [(cx - 20, by - 352), (cx, by - 412), (cx + 20, by - 352)])
        sp = op_union(sp, sd_ellipse(c, cx, by - 352, 20, 20 * K))
        n = np.dstack([np.clip((c.X - cx) / 20, -1, 1), np.full(c.X.shape, -0.2), np.ones(c.X.shape)])
        n = n / np.linalg.norm(n, axis=2, keepdims=True)
        c.over(mat_plastic(n, '#ffffff', '#9fb6d8', 0.9), c.cover(sp))
        # floating halo ring around the spike
        rd = np.abs(sd_ellipse(c, cx, by - 372, 34, 34 * K)) - 2.2
        halo(c, rd, GLOW, 10, 0.5)
        c.over(rgb('#dffcff'), c.cover(rd))
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, cx, by)}


@prop('spire_1')
def spire_1():
    return draw_spire(1)


@prop('spire_2')
def spire_2():
    return draw_spire(2)


@prop('cube')
def cube():
    W, H = 160, 190
    c = Canvas(W, H, ss=3)
    cx = W / 2
    s = 58                     # half width
    fh = 84                    # front face height (foreshortened)
    depth = 72                 # visible height of the top face
    fy1 = H - 22               # front face bottom
    fy0 = fy1 - fh             # front face top
    ty0 = fy0 - depth
    contact_shadow(c, cx, fy1 - 2, 80, 18, 0.32)
    whole = sd_box(c, cx, (ty0 + fy1) / 2, s, (fy1 - ty0) / 2, 10)
    front = op_inter(whole, fy0 - c.Y)
    top = op_inter(whole, c.Y - fy0)
    # glass faces with soft bevelled (jelly) normals
    fn = normals(c, height_bevel(front, 14))
    tn = normals(c, height_bevel(top, 14))
    tf = clamp01((c.Y - fy0) / fh)
    fcol = gradient_map(tf, [(0.0, rgb('#6fe4ff')), (0.5, rgb('#25b0ec')), (1.0, rgb('#1278cc'))])
    fcol = fcol + spec(fn, 60)[..., None] * 0.6
    c.over(clamp01(fcol), c.cover(front) * (0.66 + 0.2 * tf))
    tt = clamp01((c.Y - ty0) / depth)
    tcol = gradient_map(tt, [(0.0, rgb('#f4feff')), (0.6, rgb('#bdf5ff')), (1.0, rgb('#8ce8ff'))])
    tcol = tcol + spec(tn, 60)[..., None] * 0.5
    c.over(clamp01(tcol), c.cover(top) * 0.78)
    # glowing core floating inside the volume
    ccy = fy0 + fh * 0.42
    halo(c, sd_circle(c, cx, ccy, 20), GLOW, 36, 0.75)
    glass_orb(c, cx, ccy, 17, lit=1.0, halo=False, tint=('#ffffff', '#bff8ff', '#5fe0ff'))
    # back edges seen through the glass
    c.over(rgb('#d8fbff'), c.cover(np.abs(c.Y - (fy1 - depth * 0.62)) - 0.8) * c.cover(front + 10) * 0.35)
    c.over(rgb('#ffffff'), c.cover(np.abs(c.Y - (ty0 + 8)) - 0.7) * c.cover(top + 10) * 0.25)
    # reflection streaks
    diag = (c.X - cx) + (c.Y - fy0) * 0.8
    c.over(WHITE, c.cover(np.abs(diag + 30) - 8, 1.5) * c.cover(front + 6) * 0.3)
    c.over(WHITE, c.cover(np.abs(diag + 50) - 2.5) * c.cover(front + 6) * 0.35)
    tdiag = (c.X - cx) * 0.9 + (c.Y - ty0) * 1.4
    c.over(WHITE, c.cover(np.abs(tdiag + 4) - 9, 1.5) * c.cover(top + 6) * 0.45)
    # white chrome frame on every edge
    frame = op_sub(whole, sd_box(c, cx, (ty0 + fy1) / 2, s - 6, (fy1 - ty0) / 2 - 6, 5))
    for fr in (frame,):
        n = normals(c, height_bevel(fr, 3.5))
        c.over(mat_plastic(n, '#ffffff', '#8fb3dc', 1.0), c.cover(fr))
    edge = op_inter(np.abs(c.Y - fy0) - 2.2, np.abs(c.X - cx) - s + 1)
    c.over(rgb('#2a6fb0'), c.cover(np.abs(c.Y - (fy0 + 3)) - 0.8) * c.cover(front) * 0.5)
    c.over(WHITE, c.cover(edge))
    sparkle(c, cx - s + 12, ty0 + 9, 13, 0.9)
    fade_edges(c, 3)
    return c.image(), {'pivot': pivot(c, cx, fy1 - 2)}


def draw_pad(lit):
    W, H = 164, 124
    c = Canvas(W, H, ss=3)
    cx, cy = W / 2, H / 2 - 6
    rx, ry = 62, 40
    lip = 8
    contact_shadow(c, cx, cy + lip + 4, rx + 8, ry + 8, 0.25, core=0.8)
    # front lip (ceramic side) then the top ring
    side = op_union(sd_ellipse(c, cx, cy + lip, rx, ry), sd_box(c, cx, cy + lip / 2, rx, lip / 2))
    u = np.clip((c.X - cx) / rx, -1, 1)
    scol = mat_plastic(np.dstack([u, np.zeros_like(u) + 0.3, np.sqrt(1 - u * u) + 0.2]) /
                       np.linalg.norm(np.dstack([u, np.zeros_like(u) + 0.3, np.sqrt(1 - u * u) + 0.2]), axis=2, keepdims=True),
                       '#e8f0fa', '#8ea6c8', 0.5)
    c.over(scol, c.cover(side))
    if lit:
        c.over(rgb('#5fe0ff'), c.cover(np.abs(sd_ellipse(c, cx, cy + lip * 0.55, rx, ry)) - 1.2) * c.cover(side) * (c.Y > cy) * 0.9)
    top = sd_ellipse(c, cx, cy, rx, ry)
    tn = top_normals(c, cx, cy, rx, ry / rx, dome=0.25)
    c.over(mat_plastic(tn, '#ffffff', '#b3c6e2', 0.7), c.cover(top))
    # chrome inner ring + glass center
    ring = np.abs(sd_ellipse(c, cx, cy + 1, rx * 0.74, ry * 0.74)) - 3
    c.over(chrome(normals(c, height_bevel(ring, 3))), c.cover(ring))
    g = sd_ellipse(c, cx, cy + 1, rx * 0.68, ry * 0.68)
    t = clamp01((c.Y - (cy - ry * 0.7)) / (ry * 1.4))
    if lit:
        halo(c, top, GLOW, 18, 0.5)
        gcol = gradient_map(t, [(0.0, rgb('#ffffff')), (0.4, rgb('#9ffcff')), (1.0, rgb('#20c4f0'))])
        c.over(gcol, c.cover(g))
        c.add(WHITE, np.exp(-(((c.X - cx) / 22) ** 2 + ((c.Y - cy) / 14) ** 2)) * c.cover(g) * 0.6)
        # concentric light rings
        for k in (0.35, 0.55):
            c.over(WHITE, c.cover(np.abs(sd_ellipse(c, cx, cy + 1, rx * k, ry * k)) - 1.0) * 0.6)
    else:
        gcol = gradient_map(t, [(0.0, rgb('#4f8fbf')), (0.6, rgb('#8fc4e4')), (1.0, rgb('#c9e8f8'))])
        c.over(gcol, c.cover(g))
        c.over(rgb('#cfe9ff'), c.cover(np.abs(sd_ellipse(c, cx, cy + 1, rx * 0.4, ry * 0.4)) - 0.9) * 0.4)
    inner_shadow(c, g, 6, 0.35, (0.05, 0.2, 0.45))
    sheen(c, g, cx - rx * 0.25, cy - ry * 0.35, rx * 0.25, ry * 0.12, 0.6, 3)
    c.over(WHITE, c.cover(np.abs(top + 1.2) - 0.9) * 0.7 * (c.Y < cy))
    fade_edges(c, 3)
    return c.image(), {'pivot': pivot(c, cx, cy + lip / 2)}


@prop('pad_off')
def pad_off():
    return draw_pad(False)


@prop('pad_on')
def pad_on():
    return draw_pad(True)


@prop('gate')
def gate():
    W, H = 148, 232
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 16
    contact_shadow(c, cx, by, 72, 12, 0.30)
    x0, x1 = cx - 56, cx + 56
    ptop = by - 176
    # energy-glass panel
    panel = sd_box(c, cx, (ptop + 8 + by - 6) / 2, 52, (by - 6 - ptop - 8) / 2, 4)
    t = clamp01((c.Y - ptop) / (by - ptop))
    col = gradient_map(t, [(0.0, rgb('#c8fbff')), (0.5, rgb('#5fe0ff')), (1.0, rgb('#22a8ea'))])
    # hex-ish scan pattern
    scan = 0.5 + 0.5 * np.sin((c.Y) * 0.5)
    col = col * (0.94 + 0.08 * scan)[..., None]
    halo(c, panel, GLOW, 12, 0.35)
    c.over(col, c.cover(panel) * 0.6)
    diag = (c.X - cx) * 0.8 + (c.Y - ptop)
    c.over(WHITE, c.cover(np.abs(diag - 40) - 9, 2) * c.cover(panel) * 0.3)
    c.over(WHITE, c.cover(np.abs(diag - 64) - 2.5) * c.cover(panel) * 0.35)
    c.over(rgb('#e6fdff'), c.cover(np.abs(panel + 1.2) - 1.2) * 0.9)
    # chrome posts
    for x in (x0, x1):
        chrome_cyl(c, x, ptop, by, 9)
        ceramic_cyl(c, x, by - 10, by, 12)
        chrome_ring(c, x, by - 90, 10, 2)
        glass_orb(c, x, ptop - 9, 9, lit=1.0, halo=False, tint=('#ffffff', '#bff8ff', '#5fe0ff'))
        halo(c, sd_circle(c, x, ptop - 9, 9), GLOW, 14, 0.5)
    fade_edges(c, 3)
    return c.image(), {'pivot': pivot(c, cx, by)}


# ============================================================================
# Arch, clam, jelly, portal, night flora
# ============================================================================

def vine_along(c, pts, seed, leaf_every=16, flowers=(), leaf_len=20, leaf_w=7):
    """Green vine stem along pts with alternating leaves and optional flowers."""
    rng = np.random.default_rng(seed)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    L = Layer(c, min(xs) - 10, min(ys) - 10, max(xs) - min(xs) + 20, max(ys) - min(ys) + 20)
    dist, t, s = spine(L, pts)
    d = dist - 3.2
    u = np.clip(s / 3.2, -1, 1)
    col = gradient_map(clamp01(0.5 - 0.5 * u), [(0.0, LEAF_DEEP), (0.6, LEAF_DARK), (1.0, LEAF_MID)])
    L.over(col, L.cover(d))
    L.commit()
    total = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
    n = int(total / leaf_every)
    acc, k, side = 0.0, 0, 1
    for i in range(len(pts) - 1):
        seg = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        acc += seg
        if acc >= leaf_every:
            acc = 0
            ang = math.degrees(math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0]))
            leaf(c, pts[i], ang + side * rng.uniform(45, 75), leaf_len * rng.uniform(0.8, 1.15),
                 leaf_w, bend=0.3 * side, dark=0.05)
            side = -side
    for (i, r, rot) in flowers:
        hibiscus(c, pts[i][0], pts[i][1], r, rot)


@prop('arch')
def arch():
    W, H = 420, 440
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 14 - 34 * K
    px = 148                  # pillar offset from centre
    acy = by - 200            # arch circle centre
    contact_shadow(c, cx - px, by + 3, 44, 16, 0.32)
    contact_shadow(c, cx + px, by + 3, 44, 16, 0.32)
    # arch band: thick rounded ring (upper half) joining the pillar tops
    R = px
    band = op_inter(np.abs(sd_circle(c, cx, acy, R)) - 22, c.Y - acy - 2)
    n = normals(c, height_bevel(band, 14))
    c.over(mat_plastic(n, '#f7fbff', '#9fb6d8', 0.9), c.cover(band))
    inner_shadow(c, band, 6, 0.15)
    # chrome + aqua glass inlay along the band
    inlay = op_inter(np.abs(sd_circle(c, cx, acy, R)) - 5, c.Y - acy)
    c.over(chrome(normals(c, height_bevel(inlay, 4))), c.cover(inlay))
    gl = op_inter(np.abs(sd_circle(c, cx, acy, R)) - 2.2, c.Y - acy)
    c.over(rgb('#5fe0ff'), c.cover(gl) * 0.95)
    halo(c, gl, GLOW, 6, 0.3)
    # pillars
    for x in (cx - px, cx + px):
        ceramic_cyl(c, x, by - 22, by, 34)
        chrome_ring(c, x, by - 22, 34, 2.5)
        ceramic_cyl(c, x, acy + 4, by - 24, 24, top=False)
        glass_cyl(c, x, by - 120, by - 100, 24.5, alpha=0.95, band=True, glow=0.4, tint=BAND_ON)
        chrome_ring(c, x, acy + 14, 28, 3)
        ceramic_cyl(c, x, acy + 2, acy + 10, 30, top=False)
    # keystone orb
    ky = acy - R - 2
    ceramic_cyl(c, cx, ky - 6, ky + 14, 22)
    halo(c, sd_circle(c, cx, ky - 26, 20), GLOW, 26, 0.5)
    glass_orb(c, cx, ky - 26, 20, lit=0.6, halo=False)
    # vines: up the left pillar, over the arch, down the right side
    pts = []
    for i in range(60):
        a = math.pi + i / 59 * math.pi * 0.62
        rr = R + 18 * math.sin(i * 0.55) + 4
        pts.append((cx + math.cos(a) * rr, acy + math.sin(a) * rr))
    left = [(cx - px + 22 * math.sin(i * 0.6), by - 30 - i * (by - 30 - acy) / 20) for i in range(21)]
    vine_along(c, left + pts[1:], 3, leaf_every=14, flowers=[(14, 13, 0.3), (40, 15, 1.2), (60, 12, 0.5)])
    right = []
    for i in range(30):
        a = -math.pi * 0.05 - i / 29 * math.pi * 0.42
        rr = R + 16 * math.sin(i * 0.7 + 1)
        right.append((cx + math.cos(a) * rr, acy + math.sin(a) * rr))
    right = right[::-1] + [(cx + px + 20 * math.sin(i * 0.7), acy + i * 6) for i in range(1, 16)]
    vine_along(c, right, 8, leaf_every=14, flowers=[(6, 14, 2.0), (30, 12, 0.7)])
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, cx, by)}


IRIDESCENT = [(0.0, rgb('#ffe3f4')), (0.25, rgb('#e6dcff')), (0.5, rgb('#d4f6ff')),
              (0.75, rgb('#e2ffef')), (1.0, rgb('#ffe3f4'))]


def shell_fan(c, hx, hy, R, spread, squash, ribs=9, flip=False):
    """Scalloped fan shell from hinge (hx,hy) opening downward (or upward if flip).
    Returns (sdf, rib_field, radial t, angle)."""
    dx = c.X - hx
    dy = (c.Y - hy) / squash * (-1 if flip else 1)
    th = np.arctan2(dx, dy)                # 0 = straight away from the hinge
    rho = np.hypot(dx, dy)
    rib = np.cos(th / spread * ribs * math.pi / 2) ** 2
    edge = R * (1 - 0.06 * (1 - rib)) * (1 - 0.10 * (th / spread) ** 4)
    sdf = op_inter(rho - edge, (np.abs(th) - spread) * rho)
    sdf = op_smooth_union(sdf * squash, sd_ellipse(c, hx, hy, R * 0.32, R * 0.16), 6)   # hinge ears
    return sdf, rib, clamp01(rho / edge), th


def pearly(c, sdf, rib, t, th, light=1.0, dome=None):
    """Pearly white shell surface with ribs and an iridescent sheen."""
    irid = gradient_map((th * 0.35 + t * 0.8 + 0.1) % 1.0, IRIDESCENT)
    base = mix(rgb('#ffffff'), irid, 0.85)
    shade = 0.8 + 0.2 * rib - 0.1 * t
    if dome is not None:
        shade = shade * (0.72 + 0.38 * lambert(dome))
    col = base * shade[..., None] * light
    col = col + (np.exp(-((t - 0.4) / 0.2) ** 2) * 0.12 * rib)[..., None]
    col = mix(col, rgb('#9aa8d8'), (smoothstep(0.8, 1.0, t) * 0.3)[..., None])
    c.over(clamp01(col), c.cover(sdf))
    c.over(rgb('#a99ad0'), c.cover(sdf + 2) * smoothstep(0.2, 0.0, rib) * smoothstep(0.12, 0.35, t) * 0.5)
    c.over(WHITE, c.cover(np.abs(sdf + 1.2) - 0.9) * 0.7)


def draw_clam(open_):
    W, H = 184, 190 if open_ else 150
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 18
    contact_shadow(c, cx, by - 6, 84, 20, 0.32)
    R, spread = 82, 1.2
    if not open_:
        hy = by - 92
        # lower shell lip peeks out below the top shell
        low, rb, tb, thb = shell_fan(c, cx, hy + 4, R + 2, spread, 0.95)
        pearly(c, low, rb, tb, thb, light=0.8)
        top_s, rib, t, th = shell_fan(c, cx, hy - 4, R, spread, 0.92)
        seam = op_inter(np.abs(top_s) - 1.5, -low - 1)
        halo(c, seam, GLOW, 10, 0.8)
        c.over(rgb('#dffcff'), c.cover(seam))
        dome = sphere_normals(c, cx, hy + 30, R * 1.1, R * 0.8)
        pearly(c, top_s, rib, t, th, dome=dome)
        c.over(chrome(sphere_normals(c, cx, hy - 6, 14, 9)), c.cover(sd_ellipse(c, cx, hy - 6, 14, 9)))
        sheen(c, top_s, cx - 24, hy + 26, 22, 10, 0.6, 5)
        sparkle(c, cx + 30, hy + 44, 10, 0.7)
        fade_edges(c, 3)
        return c.image(), {'pivot': pivot(c, cx, by - 6)}
    # open: top shell lifted back (we see its inner face), bowl with glowing interior in front
    hy = by - 86
    up, rib_u, t_u, th_u = shell_fan(c, cx, hy, R * 0.95, spread, 0.62, flip=True)
    halo(c, up, GLOW, 12, 0.4)
    pearly(c, up, rib_u, t_u, th_u, light=0.92)
    c.add(rgb('#9ffcff'), c.cover(up) * (1 - t_u) * 0.4)
    low, rib, t, th = shell_fan(c, cx, hy, R + 2, spread, 0.95)
    pearly(c, low, rib, t, th, light=0.95)
    # interior: glowing aqua bowl inset from the rim
    inner = low + 8
    ti = clamp01((c.Y - hy) / 70)
    icol = gradient_map(ti, [(0.0, rgb('#0b5fae')), (0.5, rgb('#1fa8e8')), (1.0, rgb('#8ff0ff'))])
    icol = mix(icol, rgb('#ffffff'), (rib * 0.12)[..., None])
    c.over(icol, c.cover(inner) * 0.95)
    inner_shadow(c, inner, 12, 0.4, (0.05, 0.3, 0.55))
    # pearl with glow
    py = hy + 36
    halo(c, sd_circle(c, cx, py, 17), GLOW, 30, 0.75)
    pn = sphere_normals(c, cx, py, 17)
    pc = mix(rgb('#dfe6ff'), rgb('#ffffff'), lambert(pn)[..., None]) + spec(pn, 40)[..., None] * 0.8
    pc = mix(pc, gradient_map((pn[..., 0] * 0.5 + 0.5), IRIDESCENT), 0.35)
    c.over(clamp01(pc), c.cover(sd_circle(c, cx, py, 17)))
    sparkle(c, cx - 7, py - 8, 14, 0.9)
    c.over(chrome(sphere_normals(c, cx, hy, 14, 8)), c.cover(sd_ellipse(c, cx, hy, 14, 8)))
    fade_edges(c, 3)
    return c.image(), {'pivot': pivot(c, cx, by - 6)}


@prop('bubble_clam_closed')
def clam_closed():
    return draw_clam(False)


@prop('bubble_clam_open')
def clam_open():
    return draw_clam(True)


def draw_jelly(frame):
    W, H = 128, 160
    c = Canvas(W, H, ss=3)
    ph = frame / 4 * 2 * math.pi
    p = math.sin(ph)
    cx, cy = W / 2, 52 - p * 2
    rx, ry = 40 * (1 + 0.07 * p), 34 * (1 - 0.07 * p)
    body_a = 0.75
    # tentacles (behind the bell)
    for k, x in enumerate([-24, -10, 6, 20]):
        pts = []
        for i in range(16):
            tt = i / 15
            yy = cy + ry * 0.35 + tt * (70 + 6 * math.cos(ph + k))
            xx = cx + x * (1 + 0.08 * p) + math.sin(tt * 5 + ph + k * 1.3) * 6 * tt
            pts.append((xx, yy))
        Lr = Layer(c, cx - 60, cy, 120, 110)
        dist, t, s = spine(Lr, pts)
        d = dist - (3.0 * (1 - t) + 0.8)
        col = gradient_map(t, [(0.0, rgb('#ff9be0')), (1.0, rgb('#b48cff'))])
        Lr.over(col, Lr.cover(d) * (0.8 - 0.5 * t))
        Lr.commit()
    # frilly oral arms (short, wavy, lighter)
    for x in (-8, 8):
        pts = [(cx + x + math.sin(i * 0.8 + ph) * 4, cy + ry * 0.4 + i * 3.4) for i in range(12)]
        Lr = Layer(c, cx - 40, cy, 80, 80)
        dist, t, s = spine(Lr, pts)
        frill = 4.5 * (1 - t * 0.6) * (0.75 + 0.25 * np.sin(t * 30))
        Lr.over(rgb('#ffc4ee'), Lr.cover(dist - frill) * 0.75)
        Lr.commit()
    # bell: dome with scalloped skirt
    dx, dy = (c.X - cx) / rx, (c.Y - cy) / ry
    dome = sd_ellipse(c, cx, cy, rx, ry)
    skirt_y = cy + ry * 0.38 + 3 * np.abs(np.sin((c.X - cx) / rx * math.pi * 3))
    bell = op_inter(dome, c.Y - skirt_y)
    n = sphere_normals(c, cx, cy, rx, ry)
    t = clamp01((c.Y - (cy - ry)) / (ry * 1.4))
    col = gradient_map(t, [(0.0, rgb('#ffd6f3')), (0.5, rgb('#e48cf0')), (1.0, rgb('#9b6cf0'))])
    fres = (1 - n[..., 2]) ** 2
    col = mix(col, rgb('#fff0fb'), (fres * 0.5)[..., None])
    halo(c, bell, rgb('#d9a6ff'), 10, 0.25)
    c.over(clamp01(col), c.cover(bell) * (body_a + 0.2 * fres))
    # glowing cyan core
    core = sd_ellipse(c, cx, cy + 2, rx * 0.42, ry * 0.36)
    halo(c, core, GLOW, 10, 0.6)
    c.over(mix(rgb('#5fe0ff'), rgb('#e9ffff'), clamp01(1 - np.hypot((c.X - cx) / (rx * 0.42), (c.Y - cy - 2) / (ry * 0.36)))[..., None]),
           c.cover(core) * 0.85)
    # spots
    for sx, sy, sr in [(-22, -14, 3.5), (-6, -24, 3), (14, -20, 3.5), (26, -4, 3), (-28, 4, 2.6)]:
        d = sd_circle(c, cx + sx * rx / 40, cy + sy * ry / 34, sr)
        c.over(rgb('#9ffcff'), c.cover(d) * 0.85)
        halo(c, d, GLOW, 4, 0.4)
    # cute face
    for ex in (-10, 10):
        e = sd_ellipse(c, cx + ex, cy + 12, 3.2, 4.2)
        c.over(rgb('#2a1a5e'), c.cover(e))
        c.over(WHITE, c.cover(sd_circle(c, cx + ex - 1, cy + 10.5, 1.3)))
        c.over(rgb('#ff7fc8'), c.cover(sd_ellipse(c, cx + ex * 1.9, cy + 18, 4, 2), 2) * 0.5)
    # rim + top highlight
    c.over(WHITE, c.cover(np.abs(bell + 1.0) - 0.8) * 0.5)
    sheen(c, bell, cx - rx * 0.35, cy - ry * 0.55, rx * 0.32, ry * 0.18, 0.75, 3)
    c.over(WHITE, c.cover(sd_circle(c, cx + rx * 0.45, cy - ry * 0.45, 2.2)) * 0.9)
    fade_edges(c, 3)
    return c.image(), {}


for _i in range(4):
    PROPS[f'jelly_{_i}'] = (lambda i: (lambda: draw_jelly(i)))(_i)


def draw_portal(lit):
    W, H = 360, 330
    c = Canvas(W, H, ss=2)
    cx, cy = W / 2, H - 136
    rx, ry = 156, 92
    lip = 20
    contact_shadow(c, cx, cy + lip + 6, rx + 18, ry + 18, 0.3, core=0.85)
    # outer rim side (front face)
    side = op_union(sd_ellipse(c, cx, cy + lip, rx, ry), sd_box(c, cx, cy + lip / 2, rx, lip / 2))
    u = np.clip((c.X - cx) / rx, -1, 1)
    nn = np.dstack([u, np.full(u.shape, 0.25), np.sqrt(1 - u * u) + 0.3])
    nn = nn / np.linalg.norm(nn, axis=2, keepdims=True)
    c.over(mat_plastic(nn, '#eef4fb', '#8ea6c8', 0.6), c.cover(side))
    # aqua glass band on the rim side
    arc0 = ry * np.sqrt(1 - u * u)
    bandm = op_inter(np.abs(c.X - cx) - rx, np.abs(c.Y - (cy + lip * 0.55 + arc0)) - 3)
    c.over(rgb('#5fe0ff') if lit else rgb('#8fc4e4'), c.cover(bandm) * 0.95)
    if lit:
        halo(c, bandm, GLOW, 6, 0.4)
    # top of the rim
    top = sd_ellipse(c, cx, cy, rx, ry)
    rim_h = height_bevel(op_sub(top, sd_ellipse(c, cx, cy + 4, rx - 26, ry - 18)), 10)
    c.over(mat_plastic(normals(c, rim_h), '#ffffff', '#a9bedd', 0.9), c.cover(top))
    # chrome trim
    trim = np.abs(sd_ellipse(c, cx, cy + 4, rx - 24, ry - 16)) - 3.5
    c.over(chrome(normals(c, height_bevel(trim, 3.5))), c.cover(trim))
    pool = sd_ellipse(c, cx, cy + 4, rx - 28, ry - 20)
    prx, pry = rx - 28, ry - 20
    t = clamp01((c.Y - (cy + 4 - pry)) / (2 * pry))
    dx, dy = (c.X - cx) / prx, (c.Y - cy - 4) / pry
    rr = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    if not lit:
        col = gradient_map(t, [(0.0, rgb('#030a24')), (0.6, rgb('#0b2552')), (1.0, rgb('#174a7a'))])
        c.over(col, c.cover(pool))
        # still moon reflection + faint ripples
        m = sd_ellipse(c, cx + 24, cy - 8, 20, 7)
        c.over(rgb('#c9d8ff'), c.cover(m, 4) * 0.35)
        for k in (0.45, 0.7):
            c.over(rgb('#5f8fc4'), c.cover(np.abs(rr - k) * pry - 0.8) * 0.25)
        inner_shadow(c, pool, 14, 0.5, (0.0, 0.02, 0.1))
    else:
        swirl = np.sin(ang * 3 + rr * 9) * 0.5 + 0.5
        col = gradient_map(clamp01(rr), [(0.0, rgb('#ffffff')), (0.14, rgb('#c8fdff')), (0.4, rgb('#3fc8f5')),
                                         (0.72, rgb('#5a4ee8')), (1.0, rgb('#24145e'))])
        col = mix(col, rgb('#d2a6ff'), (swirl * smoothstep(0.25, 0.9, rr) * 0.5)[..., None])
        col = col + (smoothstep(0.75, 1.0, swirl) * (1 - rr) * 0.4)[..., None] * rgb('#dffcff')
        c.over(clamp01(col), c.cover(pool))
        inner_shadow(c, pool, 12, 0.35, (0.15, 0.1, 0.45))
        # light column rising from the pool
        colm = np.exp(-(((c.X - cx) / (prx * 0.55)) ** 2)) * smoothstep(cy - 170, cy, c.Y) * (c.Y < cy + 4)
        c.add(mix(GLOW, rgb('#c9b6ff'), 0.3), colm * 0.45 * (1 - c.cover(pool)) * (1 - c.cover(top) * 0.6))
        m = op_sub(sd_circle(c, cx + 40, cy - 20, 16), sd_circle(c, cx + 47, cy - 25, 14))
        c.over(rgb('#fff8e6'), c.cover(op_inter(m, pool), 2) * 0.9)
        halo(c, op_inter(m, pool), WHITE, 8, 0.4)
        halo(c, pool, GLOW, 22, 0.35)
        rng = np.random.default_rng(4)
        for _ in range(14):
            sx = cx + rng.uniform(-0.8, 0.8) * prx
            sy = cy - rng.uniform(-20, 150)
            sparkle(c, sx, sy, rng.uniform(5, 12), rng.uniform(0.5, 1.0))
    # front highlight on rim
    c.over(WHITE, c.cover(np.abs(top + 1.5) - 1.0) * 0.6 * (c.Y < cy))
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, cx, cy + 4)}


@prop('portal_off')
def portal_off():
    return draw_portal(False)


@prop('portal_on')
def portal_on():
    return draw_portal(True)


@prop('nightflower')
def nightflower():
    W, H = 150, 136
    c = Canvas(W, H, ss=3)
    cx, by = W / 2, H - 14
    contact_shadow(c, cx, by - 2, 56, 12, 0.32)
    night_leaf = [(0.0, rgb('#0b3d4a')), (0.5, rgb('#167a6e')), (1.0, rgb('#2fb59a'))]
    rng = np.random.default_rng(2)
    for k, ang in enumerate([-165, -130, -100, -70, -40, -15, -150, -30, -88]):
        leaf(c, (cx + rng.uniform(-5, 5), by - 4), ang + rng.uniform(-6, 6), 50 if k < 6 else 40, 10,
             bend=0.35 * (1 if ang < -90 else -1), hue=night_leaf)
    # glowing stems + blossoms
    for fx, fy, fr, rot, colr in [(-30, -52, 16, 0.2, 0), (24, -66, 18, 1.0, 1), (0, -40, 15, 2.1, 0),
                                  (40, -36, 12, 0.6, 1)]:
        halo(c, sd_circle(c, cx + fx, by + fy, fr), GLOW if colr == 0 else rgb('#c49bff'), 22, 0.55)
    for fx, fy, fr, rot, colr in [(-30, -52, 16, 0.2, 0), (24, -66, 18, 1.0, 1), (0, -40, 15, 2.1, 0),
                                  (40, -36, 12, 0.6, 1)]:
        pal = ('#f0ffff', '#7ff8ff', '#3a7cf0') if colr == 0 else ('#fbefff', '#c49bff', '#6a3fd6')
        hibiscus(c, cx + fx, by + fy, fr, rot, col=pal, center='#ffffff')
        c.add(WHITE, np.exp(-(np.hypot(c.X - cx - fx, c.Y - by - fy) / (fr * 0.35)) ** 2) * 0.6)
    for sx, sy in [(-48, -80), (8, -96), (52, -70)]:
        sparkle(c, cx + sx, by + sy, 7, 0.8, color=rgb('#dffcff'))
    fade_edges(c, 3)
    return c.image(), {'pivot': pivot(c, cx, by)}


@prop('float_shadow')
def float_shadow():
    W, H = 120, 52
    c = Canvas(W, H, ss=2)
    contact_shadow(c, W / 2, H / 2, 52, 20, 0.45, core=0.0)
    return c.image(), {}


# ============================================================================
# Runner
# ============================================================================

def _job(name):
    img, meta = PROPS[name]()
    save(img, f'Props/{name}.png')
    check_padding(img, name)
    preview(img, 'prop_' + name)
    return name, meta, img.size


def main():
    from multiprocessing import Pool
    names = sys.argv[1:] or list(PROPS)
    with Pool(8) as p:
        res = p.map(_job, names)
    meta_path = os.path.join(HERE, '_meta_props.json')
    meta = {}
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path))
    for name, m, size in res:
        if m:
            meta[f'Props/{name}.png'] = m
        print(f'{name}: {size[0]}x{size[1]}')
    json.dump(meta, open(meta_path, 'w'), indent=1, sort_keys=True)


if __name__ == '__main__':
    main()
