"""
scenery.py - big AquaScape setpieces (floating isle + waterfall, Eden domes,
needle tower, chrome ring, Moonpool crystal, lily pad).

Usage:  python3 scenery.py              # render everything
        python3 scenery.py domes ring   # subset

Writes PNGs to Assets/AquaScape/Art/Scenery/ and merges pivots into
Assets/AquaScape/Art/sprite_meta_scenery.json (paths relative to Art/,
pivot normalised with 0,0 = bottom-left at the ground contact).
"""
import json
import math
import os
import sys
import numpy as np
from PIL import Image
from aqua import *
from artkit import *
import props as P
from props import (leaf, leafy_blob, hibiscus, plumeria, vine_along, ceramic_cyl, chrome_cyl,
                   glass_cyl, band_sdf, gem, fade_edges, K, LEAF_DEEP, LEAF_DARK, LEAF_MID)

HERE = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(ART, 'sprite_meta_scenery.json')
PREV = '/private/tmp/claude-501/-Users-markguggenheim-AquaScape/de2db03f-47af-475d-a625-9aefc8d08a9d/scratchpad/scenery_preview'
JOBS = {}


def job(name):
    def deco(fn):
        JOBS[name] = fn
        return fn
    return deco


def pivot(c, x, y):
    return [round(x / c.w, 4), round(1 - y / c.h, 4)]


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def paste(c, img, x, y, scale=1.0, opacity=1.0, mask=None):
    """Composite a PIL RGBA image with its top-left at final px (x, y)."""
    ss = c.ss
    w = max(1, int(round(img.width * scale * ss)))
    h = max(1, int(round(img.height * scale * ss)))
    im = img.resize((w, h), Image.LANCZOS)
    a = np.asarray(im, float) / 255.0
    X0, Y0 = int(round(x * ss)), int(round(y * ss))
    H, W = c.A.shape
    sx0, sy0 = max(0, -X0), max(0, -Y0)
    ex, ey = min(w, W - X0), min(h, H - Y0)
    if ex <= sx0 or ey <= sy0:
        return
    col = a[sy0:ey, sx0:ex, :3]
    al = a[sy0:ey, sx0:ex, 3] * opacity
    ys, xs = slice(Y0 + sy0, Y0 + ey), slice(X0 + sx0, X0 + ex)
    if mask is not None:
        al = al * mask[ys, xs]
    c.P[ys, xs] = col * al[..., None] + c.P[ys, xs] * (1 - al[..., None])
    c.A[ys, xs] = al + c.A[ys, xs] * (1 - al)


def paste_pivot(c, img_meta, x, y, scale=1.0, opacity=1.0):
    """Paste a (img, meta) sprite so its pivot lands at (x, y)."""
    img, meta = img_meta
    px, py = meta.get('pivot', [0.5, 0.5])
    paste(c, img, x - px * img.width * scale, y - (1 - py) * img.height * scale, scale, opacity)


def composite_canvas(dst, src, mask=None, opacity=1.0):
    a = src.A * opacity
    Pp = src.P * opacity
    if mask is not None:
        a = a * mask
        Pp = Pp * mask[..., None]
    dst.P = Pp + dst.P * (1 - a[..., None])
    dst.A = a + dst.A * (1 - a)


def sd_rot_ellipse(c, cx, cy, rx, ry, rot):
    ca, sa = math.cos(rot), math.sin(rot)
    dx, dy = c.X - cx, c.Y - cy
    lx = dx * ca + dy * sa
    ly = -dx * sa + dy * ca
    k = np.hypot(lx / rx, ly / ry)
    return (k - 1.0) * min(rx, ry), lx, ly


def chrome_hoop(c, cx, cy, rx, ry, thick, rot=0.0, part='front', glow=True):
    """Elliptical chrome torus band (3/4 view). part = 'back' (upper half) or
    'front' (lower half) so a tower can be sandwiched in between."""
    e, lx, ly = sd_rot_ellipse(c, cx, cy, rx, ry, rot)
    d = np.abs(e) - thick
    sel = (ly >= 0) if part == 'front' else (ly < 0)
    blend = smoothstep(-2, 2, ly) if part == 'front' else smoothstep(2, -2, ly)
    a_ = np.clip(e / thick, -1, 1)
    # radial direction in screen space
    gx, gy = (c.X - cx) / rx ** 2, (c.Y - cy) / ry ** 2
    gl = np.hypot(gx, gy) + 1e-9
    nx, ny = gx / gl * a_, gy / gl * a_
    nz = np.sqrt(clamp01(1 - a_ * a_))
    n = np.dstack([nx, ny, nz])
    col = chrome(n)
    if part == 'back':
        col = col * 0.82 + rgb('#2a6f9a') * 0.12
    if glow:
        halo(c, d, GLOW, 10, 0.35 * (blend))
    c.over(clamp01(col), c.cover(d) * blend)
    # aqua inner light strip
    strip = np.abs(e + thick * 0.15) - thick * 0.18
    c.add(rgb('#7ff8ff'), c.cover(strip) * blend * 0.35)
    return d


# ============================================================================
# Floating isle + waterfall
# ============================================================================
ISLE_W, ISLE_H = 800, 960
I_CX, I_TOP, I_RX, I_RY, I_LIP = 400, 290, 330, 132, 34
I_FALL_TOP = I_TOP + I_RY - 4
I_POOL_Y = 890


def isle_under_sdf(c):
    cx = I_CX
    y0 = I_TOP + I_LIP
    lobes = [(cx, y0 + 4, I_RX * 0.985, I_RY * 0.99), (cx - 10, y0 + 70, 270, 120),
             (cx + 14, y0 + 150, 200, 120), (cx - 6, y0 + 235, 135, 110),
             (cx + 4, y0 + 315, 72, 90), (cx, y0 + 380, 26, 50)]
    d = sd_ellipse(c, *lobes[0])
    for lb in lobes[1:]:
        d = op_smooth_union(d, sd_ellipse(c, *lb), 46)
    # only the part below the rim
    return d


@job('floating_isle')
def floating_isle():
    W, H = ISLE_W, ISLE_H
    c = Canvas(W, H, ss=2)
    cx = I_CX
    # faint shadow of the island on the water around the pool
    contact_shadow(c, cx, I_POOL_Y - 6, 230, 60, 0.16, core=0.2)

    # ---- underside (glossy white ceramic rock, layered) -------------------
    L = Layer(c, cx - I_RX - 20, I_TOP - 10, 2 * I_RX + 40, 470)
    d = isle_under_sdf(L)
    nz_ = value_noise(L.X.shape[1], L.X.shape[0], 60 * L.ss, seed=3, octaves=3)
    d = d + (nz_ - 0.5) * 16
    n = normals(L, height_bevel(d, 80))
    col = mat_plastic(n, '#fbfdff', '#93acd2', gloss=0.55)
    # strata: gentle arcs that dip toward the centre (front face of a cone)
    dx = L.X - cx
    q = L.Y - 0.22 * np.sqrt(np.maximum(0, (I_RX * 1.05) ** 2 - dx ** 2)) + (nz_ - 0.5) * 10
    fr = (q / 46.0) % 1.0
    col = col * (1.0 - 0.13 * fr)[..., None]
    col = mix(col, rgb('#ffffff'), (smoothstep(0.08, 0.0, fr) * 0.6)[..., None])
    col = mix(col, rgb('#7d93bf'), (smoothstep(0.88, 1.0, fr) * 0.35)[..., None])
    # aqua bounce light from the water on down-facing surfaces + cool depth
    down = clamp01(n[..., 1])
    depth = smoothstep(I_TOP + 60, I_TOP + 420, L.Y)
    col = mix(col, rgb('#a9c6ea'), (depth * 0.35)[..., None])
    col = mix(col, rgb('#7fe8f8'), (down * 0.55 * depth)[..., None])
    L.over(clamp01(col), L.cover(d))
    # shade right under the grass lip
    L.over(rgb('#4a6f9c'), L.cover(d) * np.exp(-((L.Y - (I_TOP + I_LIP + I_RY * 0.55
                                                     * np.sqrt(clamp01(1 - (dx / I_RX) ** 2)))) / 22) ** 2) * 0.35)
    inner_shadow(L, d, 10, 0.25, (0.25, 0.4, 0.65))
    # glowing aqua veins
    for k, (vx, vy, ln, ang) in enumerate([(-150, 120, 90, 20), (120, 90, 110, -15), (30, 200, 80, 8),
                                           (-60, 260, 60, -25), (170, 170, 60, 30)]):
        a = math.radians(ang)
        pts = [(cx + vx + math.cos(a) * ln * t + 8 * math.sin(t * 7 + k),
                I_TOP + vy + math.sin(a) * ln * t + 6 * math.sin(t * 5 + k)) for t in np.linspace(0, 1, 12)]
        dist, t, s = spine(L, pts)
        vd = op_inter(dist - 2.2 * (1 - t * 0.6), d + 6)
        halo(L, vd, GLOW, 12, 0.5)
        L.over(rgb('#d8ffff'), L.cover(vd))
    L.commit()
    # hanging crystals under the tip
    for gx, gy, gs in [(cx + 2, I_TOP + 430, 16), (cx - 42, I_TOP + 368, 11), (cx + 46, I_TOP + 352, 10)]:
        halo(c, sd_circle(c, gx, gy + 4, gs), GLOW, gs * 2.2, 0.5)
        gem(c, gx, gy, gs * 0.7, gs * 0.6, gs * 1.9, sides=6, table=0.0, rot=0.5,
            pal=('#ffffff', '#8ff8ff', '#20c4f0', '#0b6fb8'), lit=0.3)

    # ---- grassy top -------------------------------------------------------
    # front face of the turf (rounded mossy band)
    fb = band_sdf(c, cx, I_TOP, I_TOP + I_LIP, I_RX)
    u = np.clip((c.X - cx) / I_RX, -1, 1)
    arc = I_RY * np.sqrt(1 - u * u)
    tb = clamp01((c.Y - (I_TOP + arc)) / I_LIP)
    fcol = gradient_map(tb, [(0.0, rgb('#5fd05a')), (0.35, rgb('#2fa54c')), (1.0, rgb('#0f6a44'))])
    fcol = fcol * (0.9 + 0.2 * clamp01(0.5 - u * 0.5))[..., None]
    c.over(clamp01(fcol), c.cover(fb))
    # turf top
    td = sd_ellipse(c, cx, I_TOP, I_RX, I_RY)
    gn = value_noise(c.X.shape[1], c.X.shape[0], 34 * c.ss, seed=11, octaves=4)
    tt = clamp01((c.Y - (I_TOP - I_RY)) / (2 * I_RY))
    lit = clamp01(0.55 - (c.X - cx) / (I_RX * 2.4) - (c.Y - I_TOP) / (I_RY * 3))
    gcol = gradient_map(lit * 0.7 + gn * 0.45, [(0.0, rgb('#1d9248')), (0.4, rgb('#3dbd52')),
                                                 (0.75, rgb('#73dc5c')), (1.0, rgb('#b6f27a'))])
    c.over(clamp01(gcol), c.cover(td))
    inner_shadow(c, td, 26, 0.22, (0.04, 0.35, 0.2))
    sheen(c, td, cx - 110, I_TOP - 60, 150, 45, 0.18, soft=30)
    c.over(rgb('#c8ff9a'), c.cover(np.abs(td + 1.5) - 1.2) * 0.5 * smoothstep(I_TOP + 40, I_TOP - 60, c.Y))

    # ---- spring + stream to the waterfall lip -----------------------------
    pond = sd_ellipse(c, 492, 236, 46, 19)
    ceramic_cyl(c, 492, 232, 240, 52, k=19 / 46 * 0.95)
    sp = bezier((492, 240), (430, 300), (cx, I_FALL_TOP - 30), 24, p3=(cx, I_FALL_TOP + 6))
    dist, t, s = spine(c, sp)
    sw = 9 + 9 * t
    bank = dist - sw - 3.5
    c.over(rgb('#e9f3fb'), c.cover(bank) * c.cover(td + 2))
    wsd = op_union(dist - sw, pond)
    wn = value_noise(c.X.shape[1], c.X.shape[0], 10 * c.ss, seed=4, octaves=2)
    wcol = gradient_map(clamp01(0.5 + s / (2 * sw + 1e-3) * 0.6 + (wn - 0.5) * 0.4),
                        [(0.0, rgb('#e6fdff')), (0.4, rgb('#62d8f5')), (1.0, rgb('#1d8fd0'))])
    c.over(wcol, c.cover(op_inter(wsd, td + 1)))
    c.over(WHITE, c.cover(np.abs(s + sw * 0.35) - 1.2) * c.cover(dist - sw + 3) * 0.55 * (wn > 0.45))
    c.over(WHITE, c.cover(sd_ellipse(c, 480, 230, 20, 5)) * 0.6)

    # ---- overhanging leaves along the front rim --------------------------
    rng = np.random.default_rng(5)
    for k in range(34):
        a = math.pi * (0.03 + 0.94 * k / 33) + rng.uniform(-0.03, 0.03)
        ex, ey = cx + math.cos(a) * I_RX * 0.98, I_TOP + math.sin(a) * I_RY * 0.98 + I_LIP * 0.5
        if abs(ex - cx) < 46:
            continue
        ang = math.degrees(math.atan2(math.sin(a) * 1.0, math.cos(a))) + rng.uniform(-20, 20)
        leaf(c, (ex - math.cos(math.radians(ang)) * 10, ey - 14), ang * 0.6 + 90 * 0.4 + rng.uniform(-10, 10),
             rng.uniform(30, 46), rng.uniform(8, 11), bend=rng.uniform(-0.3, 0.3), dark=0.05)
    # hanging vines from the rim
    for k, (vx, ln) in enumerate([(-250, 120), (-175, 170), (-95, 110), (90, 150), (180, 120), (255, 90)]):
        x0 = cx + vx
        y0 = I_TOP + I_LIP + I_RY * math.sqrt(max(0, 1 - (vx / I_RX) ** 2)) - 6
        pts = [(x0 + 7 * math.sin(t * 4 + k), y0 + ln * t) for t in np.linspace(0, 1, 18)]
        vine_along(c, pts, seed=20 + k, leaf_every=15, leaf_len=16, leaf_w=6,
                   flowers=[(17, 6, 0.4 * k)] if k % 2 == 0 else [])

    # ---- plants on top (back to front) -----------------------------------
    palm1 = P.draw_palm(1)
    palm2 = P.draw_palm(2)
    bush1 = P.draw_bush(1)
    bush2 = P.draw_bush(2)
    fl1 = P.draw_flowers(1)
    fl2 = P.draw_flowers(2)
    items = [  # (y, kind, x, scale)
        (214, palm2, 300, 0.52), (206, palm1, 545, 0.5), (250, bush2, 200, 0.5),
        (236, bush1, 650, 0.45), (272, palm1, 640, 0.56), (300, palm2, 172, 0.58),
        (318, fl1, 300, 0.5), (300, bush1, 450, 0.42), (360, fl2, 560, 0.55),
        (372, bush2, 248, 0.5), (390, fl1, 470, 0.45), (338, fl2, 120, 0.45),
        (340, bush1, 700, 0.42), (396, fl2, 320, 0.42),
    ]
    for y, kind, x, sc in sorted(items, key=lambda it: it[0]):
        paste_pivot(c, kind, x, y, sc)
    for x, y, r, rot in [(360, 270, 9, 0.3), (590, 300, 8, 1.2), (230, 340, 8, 2.0), (520, 390, 7, 0.8)]:
        hibiscus(c, x, y, r, rot)
    # a couple of floating glass bubbles
    for bx, by, br in [(118, 150, 16), (700, 120, 12), (735, 520, 14), (70, 560, 10)]:
        glass_orb(c, bx, by, br, lit=0.0, alpha=0.5, halo=False)
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, I_CX, I_POOL_Y)}


def fall_frame(f, nframes=4):
    W, H = ISLE_W, ISLE_H
    c = Canvas(W, H, ss=2)
    cx = I_CX
    Lx0, Ly0 = cx - 230, I_FALL_TOP - 20
    L = Layer(c, Lx0, Ly0, 460, H - Ly0)
    y0, y1 = I_FALL_TOP, I_POOL_Y - 6
    Pd = 120.0
    ph = f / nframes
    yy = L.Y
    tv = clamp01((yy - y0) / (y1 - y0))
    hw = 34 + 30 * tv ** 1.3 + 8 * smoothstep(0.0, 0.08, tv)
    bend = 6 * np.sin(tv * 3.0)
    ux = (L.X - cx - bend) / hw
    sd = op_inter((np.abs(L.X - cx - bend) - hw), op_inter(y0 - yy, yy - y1 - 30))
    v = (yy - y0) / Pd - ph
    w2 = 2 * math.pi
    s1 = np.sin(ux * 14 + 1.6 * np.sin(w2 * v + ux * 2) + 0.7 * np.sin(w2 * 2 * v + 1.0))
    s2 = np.sin(ux * 31 + 2.2 * np.sin(w2 * v * 1 + 2.1) + ux * 3)
    s3 = np.sin(w2 * 3 * v + ux * 2.4 + 0.8 * np.sin(ux * 5))
    br = clamp01(0.45 + 0.22 * s1 + 0.12 * s2 + 0.18 * np.maximum(s3, 0) ** 2)
    edge = np.abs(ux) ** 4
    col = gradient_map(br, [(0.0, rgb('#3fb8e6')), (0.45, rgb('#8fe8fb')), (0.8, rgb('#e2fbff')), (1.0, WHITE)])
    col = mix(col, WHITE, (edge * 0.6)[..., None])
    alpha = (0.62 + 0.3 * br + 0.1 * edge) * smoothstep(y1 + 30, y1 - 40, yy)
    # soft edges
    cov = L.cover(sd, soft=2.5)
    L.over(clamp01(col), cov * clamp01(alpha))
    # bright lip where the water rolls over the turf edge
    lip = sd_ellipse(L, cx, y0 + 10, 46, 14)
    L.over(WHITE, L.cover(op_inter(lip, sd), 3) * 0.8)
    L.add(rgb('#bffcff'), np.exp(-((L.X - cx) / 60) ** 2 - ((yy - y0 - 6) / 10) ** 2) * 0.25)
    # streak highlights
    hl = np.exp(-((ux + 0.45) / 0.08) ** 2) * (0.5 + 0.5 * s3)
    L.add(WHITE, hl * cov * 0.35)

    # ---- splash pool ------------------------------------------------------
    py = I_POOL_Y
    # expanding ripple rings (loop)
    for j in range(2):
        p = (ph + j / 2) % 1.0
        rx = 70 + 120 * p
        ring = np.abs(sd_ellipse(L, cx, py, rx, rx * 0.34)) - (2.4 - 1.2 * p)
        L.over(WHITE, L.cover(ring, 1.5) * (1 - p) ** 1.2 * 0.75)
    # foam base
    foam = sd_ellipse(L, cx, py, 78, 24)
    L.over(rgb('#e8fbff'), L.cover(foam, 4) * 0.85)
    rng = np.random.default_rng(7)
    for i in range(16):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.2, 1.0)
        fx, fy = cx + math.cos(a) * 70 * rr, py + math.sin(a) * 18 * rr - 6
        r = rng.uniform(9, 18) * (0.85 + 0.25 * math.sin(2 * math.pi * ph + rng.uniform(0, 6.28)))
        bd = sd_circle(L, fx, fy - r * 0.4, r)
        bn = sphere_normals(L, fx, fy - r * 0.4, r)
        bcol = mix(rgb('#a8dff2'), WHITE, (0.4 + 0.6 * lambert(bn))[..., None]) + spec(bn, 30)[..., None] * 0.3
        L.over(clamp01(bcol), L.cover(bd) * 0.92)
    # spray droplets on arcs
    for i in range(14):
        p = (ph + i / 14 * 1.0 + rng.uniform(0, 0.07)) % 1.0
        side = -1 if i % 2 else 1
        sp_ = rng.uniform(40, 110)
        hx = cx + side * (20 + sp_ * p)
        hy = py - 10 - 90 * rng.uniform(0.6, 1.0) * 4 * p * (1 - p)
        dr = rng.uniform(2.5, 4.5) * (1 - 0.5 * p)
        L.over(WHITE, L.cover(sd_circle(L, hx, hy, dr)) * (1 - p) * 0.9)
    # mist puffs drifting up and out (loop)
    for i in range(10):
        p = (ph + i / 10) % 1.0
        side = -1 if i % 2 else 1
        mx = cx + side * (30 + 90 * p) + rng.uniform(-20, 20)
        my = py - 10 - 70 * p + rng.uniform(-10, 10)
        r = 34 + 40 * p
        a = np.exp(-(((L.X - mx) / r) ** 2 + ((L.Y - my) / (r * 0.6)) ** 2)) * math.sin(math.pi * p) * 0.4
        L.over(WHITE, a)
    # mist veil around the base of the column
    L.over(WHITE, np.exp(-(((L.X - cx) / 120) ** 2 + ((L.Y - py + 30) / 50) ** 2)) * 0.35)
    L.commit()
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, I_CX, I_POOL_Y)}


for _f in range(4):
    JOBS[f'floating_isle_fall_{_f}'] = (lambda f=_f: (lambda: fall_frame(f)))()


# ============================================================================
# Eden domes
# ============================================================================
T_ = K
ST_ = math.sqrt(1 - T_ * T_)
LW = np.array([-0.5, 0.75, 0.45])
LW = LW / np.linalg.norm(LW)
VW = np.array([0.0, T_, ST_])


def hex_cells(u, v, S):
    px, py = u / S, v / S
    ax = np.mod(px, 1.0) - 0.5
    ay = np.mod(py, 1.7320508) - 0.8660254
    bx = np.mod(px - 0.5, 1.0) - 0.5
    by = np.mod(py - 0.8660254, 1.7320508) - 0.8660254
    use_a = ax * ax + ay * ay < bx * bx + by * by
    gx = np.where(use_a, ax, bx)
    gy = np.where(use_a, ay, by)
    hd = np.maximum(np.abs(gx) * 0.5 + np.abs(gy) * 0.8660254, np.abs(gx))
    return (px - gx) * S, (py - gy) * S, (0.5 - hd) * S


def dome_geom(c, cx, by, R):
    sx, sy = c.X - cx, c.Y - by
    p2 = sx * sx + sy * sy
    s = np.sqrt(np.maximum(R * R - p2, 0))
    X, Y, Z = sx, -sy * ST_ + s * T_, sy * T_ + s * ST_
    circ = np.sqrt(p2) - R
    ell = sd_ellipse(c, cx, by, R, R * T_)
    sdf = np.maximum(circ, np.minimum(ell, sy))
    return sdf, X, Y, Z


def dome_glass(c, cx, by, R, seed=0):
    sdf, X, Y, Z = dome_geom(c, cx, by, R)
    Np = np.dstack([X, np.maximum(Y, 0), Z]) / R
    colat = np.arccos(np.clip(Y / R, -1, 1))
    lon = np.arctan2(Z, X)
    rho = colat * R
    u, v = rho * np.cos(lon), rho * np.sin(lon)
    S = R / 6.5
    ccx, ccy, edge = hex_cells(u, v, S)
    rc = np.hypot(ccx, ccy)
    lc = np.arctan2(ccy, ccx)
    cl = np.clip(rc / R, 0, math.pi / 2)
    Nc = np.dstack([np.sin(cl) * np.cos(lc), np.cos(cl), np.sin(cl) * np.sin(lc)])
    N = Nc * 0.72 + Np * 0.28
    N = N / (np.linalg.norm(N, axis=2, keepdims=True) + 1e-9)
    ndv = clamp01((N * VW).sum(axis=2))
    Rf = 2 * ndv[..., None] * N - VW
    ry = Rf[..., 1]
    sky = gradient_map(clamp01(ry), [(0.0, rgb('#ffffff')), (0.25, rgb('#c9f3ff')), (0.6, rgb('#7fd6f5')),
                                     (1.0, rgb('#4fb8ec'))])
    gnd = gradient_map(clamp01(-ry), [(0.0, rgb('#bfeff0')), (0.3, rgb('#3aa59a')), (1.0, rgb('#1b5d6a'))])
    env = np.where((ry >= 0)[..., None], sky, gnd)
    # per-panel jitter so some cells catch the light
    h = np.sin(ccx * 12.9898 + ccy * 78.233 + seed) * 43758.5453
    jit = h - np.floor(h)
    fres = 0.1 + 0.9 * (1 - ndv) ** 3
    tint = rgb('#7fe0f2')
    col = mix(tint, env, 0.55 + 0.35 * fres[..., None]) * (0.88 + 0.25 * jit)[..., None]
    up = clamp01(N[..., 1])
    alpha = clamp01(0.2 + 0.6 * fres + 0.22 * (jit > 0.8) * up + 0.12 * up ** 4)
    cov = c.cover(sdf)
    c.over(clamp01(col), cov * alpha)
    N2 = Nc * 0.35 + Np * 0.65
    N2 = N2 / (np.linalg.norm(N2, axis=2, keepdims=True) + 1e-9)
    Rf2 = 2 * clamp01((N2 * VW).sum(axis=2))[..., None] * N2 - VW
    rl = clamp01((Rf2 * LW).sum(axis=2)) * (0.85 + 0.15 * jit)
    sp = rl ** 90 * 0.9 + rl ** 12 * 0.1 + (jit > 0.9) * rl ** 8 * 0.2
    c.add(WHITE, clamp01(sp) * cov)
    # white struts (thin near the limb because of foreshortening)
    lam = clamp01((Np * LW).sum(axis=2))
    scol = mix(rgb('#a9bfdc'), WHITE, (0.45 + 0.55 * lam)[..., None])
    sw = 0.8 + 0.45 * ndv
    c.over(scol, c.cover(edge - sw) * cov * (0.65 + 0.35 * ndv))
    # bright rim + base seam
    c.over(WHITE, c.cover(np.abs(sdf + 1.2) - 1.0) * 0.7)
    return sdf


def dome_vine(c, cx, by, R, lon0, lat1, seed, flowers=True):
    pts = []
    for lat in np.linspace(0.02, lat1, 26):
        lon = lon0 + 0.18 * math.sin(lat * 7 + seed)
        X = R * 1.01 * math.cos(lat) * math.cos(lon)
        Y = R * 1.01 * math.sin(lat)
        Z = R * 1.01 * math.cos(lat) * math.sin(lon)
        pts.append((cx + X, by - Y * ST_ + Z * T_))
    fl = [(12, 8, seed), (22, 7, seed + 1)] if flowers else []
    vine_along(c, pts, seed=seed, leaf_every=11, leaf_len=24, leaf_w=9, flowers=fl)


def round_tree(c, x, by, h, r, seed):
    """Glossy round broadleaf tree."""
    tr = sd_capsule(c, x, by, x + 3, by - h, 6, 4)
    u = np.clip((c.X - x) / 6, -1, 1)
    c.over(gradient_map(clamp01(0.5 - u * 0.5), [(0, rgb('#7a4e30')), (1, rgb('#e2b07a'))]), c.cover(tr))
    leafy_blob(c, x + 3, by - h - r * 0.5, r, seed)
    leafy_blob(c, x - r * 0.5, by - h - r * 0.1, r * 0.7, seed + 1, dark=0.15)
    leafy_blob(c, x + r * 0.6, by - h, r * 0.65, seed + 2)


@job('domes')
def domes():
    W, H = 900, 600
    c = Canvas(W, H, ss=2)
    domes_ = [(450, 400, 250, 1), (210, 462, 150, 2), (690, 470, 168, 3)]   # back to front
    contact_shadow(c, 450, 520, 440, 80, 0.32, core=0.5)
    palm1, palm2 = P.draw_palm(1), P.draw_palm(2)
    # trees behind (seen through the glass)
    paste_pivot(c, palm2, 330, 300, 0.62)
    paste_pivot(c, palm1, 590, 296, 0.6)
    round_tree(c, 120, 360, 40, 46, 41)
    round_tree(c, 800, 380, 44, 42, 43)
    for cx, by, R, sd in domes_:
        ceramic_cyl(c, cx, by, by + 26, R * 1.06)
        # glossy chrome seam ring on the plinth
        P.chrome_ring(c, cx, by + 14, R * 1.065, 2.2)
        # interior planting, clipped to the dome
        inn = Canvas(W, H, ss=2)
        rng = np.random.default_rng(sd)
        # lush floor
        fl = sd_ellipse(inn, cx, by, R * 0.99, R * T_ * 0.99)
        fn = value_noise(inn.X.shape[1], inn.X.shape[0], 20 * inn.ss, seed=sd, octaves=3)
        inn.over(gradient_map(fn, [(0, rgb('#1d8a46')), (0.6, rgb('#3dbd52')), (1, rgb('#8fe36a'))]), inn.cover(fl))
        plants = []
        for k in range(14 if R > 200 else 9):
            a = rng.uniform(math.pi * 1.05, math.pi * 1.95)
            rr = rng.uniform(0.3, 0.8)
            plants.append((by + math.sin(a) * R * T_ * rr, 'b', cx + math.cos(a) * R * rr, R * rng.uniform(0.13, 0.2)))
        if R > 200:
            plants += [(by - 10, 'p2', cx - 95, 0.52), (by + 4, 'p1', cx + 40, 0.66), (by - 24, 't', cx + 150, 46)]
        else:
            plants += [(by - 6, 't', cx + 8, R * 0.3)]
        for k in range(8 if R > 200 else 5):
            a = rng.uniform(0.15, math.pi - 0.15)
            rr = rng.uniform(0.3, 0.8)
            plants.append((by + math.sin(a) * R * T_ * rr, 'b', cx + math.cos(a) * R * rr, R * rng.uniform(0.12, 0.17)))
        for k, (py_, kind, px_, sz) in enumerate(sorted(plants, key=lambda q: q[0])):
            if kind == 'b':
                leafy_blob(inn, px_, py_ - sz * 0.5, sz, sd * 10 + k, dark=0.05)
                if rng.random() < 0.4:
                    hibiscus(inn, px_ + sz * 0.3, py_ - sz * 0.9, max(5, sz * 0.3), rng.uniform(0, 3))
            elif kind == 't':
                round_tree(inn, px_, py_, sz * 0.9, sz, sd * 5 + k)
            else:
                paste_pivot(inn, palm1 if kind == 'p1' else palm2, px_, py_, sz)
        sdf, X, Y, Z = dome_geom(c, cx, by, R)
        inner = c.cover(sdf + 2)
        # tint the interior aqua (seen through glass)
        inn.P = mix(inn.P, rgb('#4fc8e0') * inn.A[..., None], 0.12)
        composite_canvas(c, inn, mask=inner, opacity=1.0)
        dome_glass(c, cx, by, R, seed=sd)
        # vines climbing the glass
        rng2 = np.random.default_rng(sd + 100)
        for j in range(5 if R > 200 else 3):
            lon0 = 0.35 + 2.45 * (j + rng2.uniform(0.1, 0.9)) / (5 if R > 200 else 3)
            dome_vine(c, cx, by, R, lon0, rng2.uniform(0.45, 0.95), seed=sd * 13 + j, flowers=(j % 2 == 0))
        # lush bushes at the base
        for k in range(5):
            a = math.pi * (0.1 + 0.8 * k / 4) + rng2.uniform(-0.1, 0.1)
            bx_ = cx + math.cos(a) * R * 1.02
            by_ = by + 26 + math.sin(a) * R * T_ * 1.02
            leafy_blob(c, bx_, by_ - 10, R * rng2.uniform(0.1, 0.15), sd * 31 + k)
        for k in range(3):
            a = math.pi * (0.2 + 0.6 * k / 2)
            hibiscus(c, cx + math.cos(a) * R * 0.98, by + 14 + math.sin(a) * R * T_, 7, k)
    # sparkles on the glass
    for sx, sy, r in [(380, 210, 14), (170, 345, 9), (630, 340, 10), (520, 180, 8)]:
        sparkle(c, sx, sy, r, 0.9)
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, 450, 528)}


# ============================================================================
# Needle tower
# ============================================================================

def taper_cyl(c, cx, y_top, y_bot, w_top, w_bot, mat='ceramic'):
    t = clamp01((c.Y - y_top) / (y_bot - y_top))
    w = w_top + (w_bot - w_top) * t
    d = op_inter(np.abs(c.X - cx) - w, op_inter(y_top - c.Y, c.Y - y_bot))
    u = np.clip((c.X - cx) / w, -1, 1)
    n = np.dstack([u, np.zeros_like(u), np.sqrt(1 - u * u)])
    col = mat_plastic(n, '#fbfdff', '#9fb6d8', gloss=0.6)
    col = col + (np.exp(-((u + 0.5) / 0.18) ** 2) * 0.22)[..., None]
    c.over(clamp01(col), c.cover(d))
    return d, u, w


@job('needle_tower')
def needle_tower():
    W, H = 320, 1280
    c = Canvas(W, H, ss=2)
    cx, by = W / 2, H - 30
    contact_shadow(c, cx, by, 100, 28, 0.32)
    pod_y = 360
    # back halves of the rings
    rings = [(cx, pod_y + 40, 136, 136 * 0.36, 9, math.radians(-5)),
             (cx, 780, 112, 112 * 0.38, 7.5, math.radians(9))]
    for r in rings:
        chrome_hoop(c, *r[:5], rot=r[5], part='back')
    # flared base
    ceramic_cyl(c, cx, by - 22, by, 78)
    P.chrome_ring(c, cx, by - 22, 80, 3)
    ceramic_cyl(c, cx, by - 60, by - 22, 58)
    glass_cyl(c, cx, by - 52, by - 30, 58.5, alpha=0.9, glow=0.8, band=True,
              tint=('#d8fbff', '#5fe0ff', '#1aa0e0'))
    # sweeping legs
    for side in (-1, 1):
        pts = bezier((cx + side * 54, by - 50), (cx + side * 46, by - 300), (cx + side * 16, by - 560), 30)
        dist, t, s = spine(c, pts)
        w = 11 - 6 * t
        ld = dist - w
        u = np.clip(-s / w * side, -1, 1)
        n = np.dstack([u * (-side) * -1, np.zeros_like(u), np.sqrt(1 - u * u)])
        n = np.dstack([np.clip((c.X - np.mean([p[0] for p in pts])) / 12, -1, 1) * 0 + u * side,
                       np.zeros_like(u), np.sqrt(1 - u * u)])
        col = mat_plastic(n, '#fbfdff', '#93abd0', gloss=0.6)
        c.over(clamp01(col * (0.92 if side > 0 else 1.0)), c.cover(ld))
    # main shaft
    d, u, w = taper_cyl(c, cx, pod_y + 40, by - 58, 13, 30)
    # glowing aqua stripe with light dashes
    stripe = op_inter(np.abs(c.X - cx + 3) - w * 0.2, d)
    halo(c, stripe, GLOW, 8, 0.45)
    dash = (np.sin(c.Y / 9.0) > 0.2)
    c.over(gradient_map(clamp01((c.Y - pod_y) / 800), [(0, rgb('#dffcff')), (1, rgb('#3fc6ee'))]),
           c.cover(stripe) * (0.75 + 0.25 * dash))
    for yy in np.arange(pod_y + 120, by - 120, 120):
        P.chrome_ring(c, cx, yy, float(13 + 17 * (yy - pod_y - 40) / (by - 58 - pod_y - 40)) + 1.5, 2.5)
    # observation pod: underside saucer, glass band, top deck
    und = sd_ellipse(c, cx, pod_y + 46, 96, 40)
    und = op_inter(und, (pod_y + 20) - c.Y)
    nn = sphere_normals(c, cx, pod_y + 20, 100, 70)
    c.over(mat_plastic(nn, '#fbfdff', '#8ea8d0', gloss=0.7), c.cover(und))
    ceramic_cyl(c, cx, pod_y + 10, pod_y + 22, 104)
    glass_cyl(c, cx, pod_y - 26, pod_y + 12, 100, alpha=0.9, glow=0.6, floors=0, band=True)
    # window mullions
    uu = np.clip((c.X - cx) / 100, -1, 1)
    ang = np.arcsin(uu)
    mull = np.abs(np.sin(ang * 9)) - 0.06
    bandd = band_sdf(c, cx, pod_y - 26, pod_y + 12, 100)
    c.over(rgb('#eef8ff'), c.cover(mull * 12) * c.cover(bandd) * 0.8)
    P.chrome_ring(c, cx, pod_y - 26, 108, 4)
    ceramic_cyl(c, cx, pod_y - 50, pod_y - 30, 84)
    glass_orb(c, cx - 30, pod_y - 54, 0.1, halo=False)
    ceramic_cyl(c, cx, pod_y - 70, pod_y - 50, 46)
    P.chrome_ring(c, cx, pod_y - 70, 48, 2.5)
    # needle spire
    sd_, su, sw = taper_cyl(c, cx, 70, pod_y - 70, 2.5, 18)
    for yy, ww in [(pod_y - 120, 14.5), (pod_y - 180, 11.5), (pod_y - 240, 8.5)]:
        glass_cyl(c, cx, yy - 5, yy + 5, ww, alpha=0.95, glow=1.0, band=True,
                  tint=('#ffffff', '#7ff8ff', '#1fb5ea'))
    glass_orb(c, cx, 56, 14, lit=1.0, alpha=0.9)
    sparkle(c, cx, 56, 26, 0.9)
    # front halves of the rings
    for r in rings:
        chrome_hoop(c, *r[:5], rot=r[5], part='front')
    sparkle(c, cx - 70, pod_y + 60, 12, 0.8)
    sparkle(c, cx + 50, 820, 9, 0.7)
    fade_edges(c, 4)
    return c.image(), {'pivot': pivot(c, cx, by)}


# ============================================================================
# Chrome ring (face-on, for x-scale "spin")
# ============================================================================

@job('chrome_ring')
def chrome_ring_sprite():
    W = H = 420
    c = Canvas(W, H, ss=3)
    cx = cy = W / 2
    Rc, r = 168, 22
    rr = np.hypot(c.X - cx, c.Y - cy)
    a_ = (rr - Rc) / r
    d = np.abs(rr - Rc) - r
    halo(c, d, GLOW, 22, 0.55)
    # inner aqua glass band
    gd = np.abs(rr - (Rc - r - 9)) - 9
    gt = clamp01((c.Y - (cy - Rc)) / (2 * Rc))
    gcol = gradient_map(gt, [(0, rgb('#e8fdff')), (0.5, rgb('#5fe0ff')), (1, rgb('#1a9fe0'))])
    ga = clamp01((rr - (Rc - r - 18)) / 18)
    c.over(gcol, c.cover(gd) * (0.55 + 0.35 * np.abs(ga * 2 - 1)))
    c.over(WHITE, c.cover(np.abs(rr - (Rc - r - 1)) - 0.8) * 0.8)
    c.add(rgb('#9ffcff'), c.cover(gd) * 0.25)
    dx, dy = (c.X - cx) / (rr + 1e-6), (c.Y - cy) / (rr + 1e-6)
    ac = np.clip(a_, -1, 1)
    n = np.dstack([dx * ac, dy * ac, np.sqrt(clamp01(1 - ac * ac))])
    col = chrome(n)
    # subtle aqua tint in the dark reflection band
    col = mix(col, rgb('#4fc3e8'), (clamp01(1 - col.mean(axis=2) * 1.4) * 0.5)[..., None])
    c.over(clamp01(col), c.cover(d))
    # bright specular arcs
    highlight_arc(c, cx, cy, Rc + r * 0.45, Rc + r * 0.45, 2.2, 200, 250, 0.9)
    highlight_arc(c, cx, cy, Rc - r * 0.4, Rc - r * 0.4, 1.4, 20, 70, 0.6)
    sparkle(c, cx - 118, cy - 122, 22, 1.0)
    sparkle(c, cx + 135, cy + 98, 13, 0.7)
    fade_edges(c, 4)
    return c.image(), {}


# ============================================================================
# Moonpool crystal cluster
# ============================================================================

@job('crystal_1')
def crystal_1():
    W = H = 240
    c = Canvas(W, H, ss=3)
    cx, cy = W / 2, H / 2 + 4
    vio = ('#fbf0ff', '#c79cff', '#7a44e0', '#2a1278')
    cya = ('#f0ffff', '#8ff8ff', '#22b8ee', '#0b4f9a')
    k = 1.6
    halo(c, sd_ellipse(c, cx, cy, 44 * k, 56 * k), rgb('#b48cff'), 34, 0.5)
    halo(c, sd_ellipse(c, cx, cy, 30 * k, 40 * k), GLOW, 22, 0.45)
    gem(c, cx - 30 * k, cy + 6 * k, 13 * k, 16 * k, 30 * k, sides=6, table=0.0, rot=0.3, pal=cya, lit=0.25)
    gem(c, cx + 30 * k, cy + 12 * k, 12 * k, 14 * k, 26 * k, sides=6, table=0.0, rot=0.8, pal=vio, lit=0.25)
    gem(c, cx, cy - 4 * k, 20 * k, 34 * k, 44 * k, sides=6, table=0.0, rot=0.52, pal=vio, lit=0.35)
    gem(c, cx + 12 * k, cy + 26 * k, 9 * k, 10 * k, 18 * k, sides=5, table=0.0, rot=0.1, pal=cya, lit=0.3)
    c.add(rgb('#f2e6ff'), np.exp(-(((c.X - cx) / (10 * k)) ** 2 + ((c.Y - cy + 2 * k) / (26 * k)) ** 2)) * 0.5)
    sparkle(c, cx - 8 * k, cy - 26 * k, 16 * k, 0.95)
    sparkle(c, cx + 30 * k, cy + 2 * k, 8 * k, 0.7, color=rgb('#e9fcff'))
    sparkle(c, cx - 34 * k, cy + 16 * k, 6 * k, 0.6)
    fade_edges(c, 4)
    return c.image(), {}


# ============================================================================
# Lily pad with pink lotus
# ============================================================================

def lotus(c, x, y, r):
    L = Layer(c, x - r * 1.6, y - r * 1.8, r * 3.2, r * 3.0)
    rings = [(9, 1.0, 0.0, 0.55, 0.0), (8, 0.8, 0.39, 0.5, 0.15), (6, 0.55, 0.2, 0.42, 0.35)]
    for cnt, rad, rot, wid, lift in rings:
        order = sorted(range(cnt), key=lambda i: math.sin(rot + i / cnt * 2 * math.pi))
        for i in order:
            a = rot + i / cnt * 2 * math.pi
            tip = (x + math.cos(a) * r * rad, y + math.sin(a) * r * rad * 0.62 - r * lift - r * 0.25 * (1 - rad))
            pts = [(x + (tip[0] - x) * t, y - r * lift * 0.5 + (tip[1] - y + r * lift * 0.5) * t
                    - math.sin(t * math.pi) * r * 0.12) for t in np.linspace(0, 1, 10)]
            dist, t, s = spine(L, pts)
            prof = np.sin(np.pi * clamp01(t) ** 0.7) ** 0.7 * r * wid * rad * (1 - 0.3 * t)
            d = dist - prof
            front = math.sin(a)
            pc = gradient_map(t, [(0.0, rgb('#fff4fa')), (0.45, rgb('#ffb3d9')), (1.0, rgb('#ff5fae'))])
            pc = pc * (0.88 + 0.12 * front + 0.08 * (1 - lift))
            au = clamp01(np.abs(s) / np.maximum(prof, 0.1))
            pc = mix(pc, rgb('#e23d8f'), (au ** 3 * 0.3)[..., None])
            L.over(clamp01(pc), L.cover(d))
            L.over(WHITE, L.cover(op_inter(dist - prof * 0.3, d)) * 0.35 * smoothstep(0.2, 0.6, t))
            L.over(rgb('#c42a7a'), L.cover(np.abs(d + 0.4) - 0.4) * 0.35)
    cd = sd_ellipse(L, x, y - r * 0.32, r * 0.22, r * 0.14)
    cn = sphere_normals(L, x, y - r * 0.32, r * 0.22, r * 0.14)
    L.over(clamp01(mix(rgb('#e0a01a'), rgb('#fff07a'), lambert(cn)[..., None]) + spec(cn, 20)[..., None] * 0.5),
           L.cover(cd))
    L.commit()


def lily_pad(c, x, y, r, notch=0.0, squash=0.72):
    dx, dy = c.X - x, (c.Y - y) / squash
    rho = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    d = (rho - r) * squash
    da = np.abs(np.angle(np.exp(1j * (th - notch))))
    wedge = (da - 0.22) * rho
    d = op_inter(d, -wedge)
    # dark water contact ring
    c.over(np.array(SHADOW_COL), c.cover(d - 3, 3) * 0.25)
    t = clamp01(rho / r)
    col = gradient_map(t, [(0.0, rgb('#2fa84c')), (0.6, rgb('#5cd25a')), (0.92, rgb('#8fe76a')), (1.0, rgb('#c6f78f'))])
    lit = clamp01(0.5 - (dx + dy) / (r * 2.6))
    col = col * (0.82 + 0.3 * lit)[..., None]
    vein = np.abs(np.sin((th - notch) * 7.5)) < 0.08
    col = mix(col, rgb('#b8f27e'), (vein * smoothstep(0.1, 0.4, t) * 0.5)[..., None])
    c.over(clamp01(col), c.cover(d))
    inner_shadow(c, d, 4, 0.3, (0.05, 0.35, 0.2))
    c.over(rgb('#d6ff9e'), c.cover(np.abs(d + 1.4) - 1.0) * 0.6)
    hl = sd_ellipse(c, x - r * 0.3, y - r * 0.35 * squash, r * 0.42, r * 0.16)
    c.over(WHITE, c.cover(op_inter(hl, d + 2), 4) * 0.4)
    return d


@job('lilypad_1')
def lilypad_1():
    W, H = 136, 128
    c = Canvas(W, H, ss=3)
    cx, cy = W / 2, H / 2 + 14
    lily_pad(c, cx, cy, 52, notch=0.35)
    # droplet
    glass_orb(c, cx + 30, cy + 6, 4.5, alpha=0.7, halo=False)
    lotus(c, cx - 4, cy - 2, 32)
    sparkle(c, cx - 24, cy - 40, 8, 0.7)
    fade_edges(c, 3)
    return c.image(), {}


# ============================================================================
# Runner + previews
# ============================================================================

def _job(name):
    img, meta = JOBS[name]()
    save(img, f'Scenery/{name}.png')
    check_padding(img, name)
    return name, meta, img.size


def preview_pair(img, name):
    os.makedirs(PREV, exist_ok=True)
    gap = 16
    sheet = Image.new('RGBA', (img.width * 2 + gap * 3, img.height + gap * 2), (40, 190, 215, 255))
    sheet.paste((14, 24, 52, 255), (img.width + gap + gap // 2, 0, sheet.width, sheet.height))
    sheet.alpha_composite(img, (gap, gap))
    sheet.alpha_composite(img, (img.width + gap * 2, gap))
    p = os.path.join(PREV, name + '.png')
    sheet.convert('RGB').save(p)
    return p


def main():
    from multiprocessing import Pool
    names = sys.argv[1:] or list(JOBS)
    with Pool(8) as p:
        res = p.map(_job, names)
    meta = {}
    if os.path.exists(META):
        meta = json.load(open(META))
    for name, m, size in res:
        if m:
            meta[f'Scenery/{name}.png'] = m
        print(f'{name}: {size[0]}x{size[1]}')
    json.dump(meta, open(META, 'w'), indent=2, sort_keys=True)
    # previews
    for name, m, size in res:
        if name.startswith('floating_isle_fall'):
            continue
        img = Image.open(os.path.join(ART, f'Scenery/{name}.png'))
        if name == 'floating_isle':
            img = img.copy()
            f0 = os.path.join(ART, 'Scenery/floating_isle_fall_0.png')
            if os.path.exists(f0):
                img.alpha_composite(Image.open(f0))
        preview_pair(img, name)
    falls = [os.path.join(ART, f'Scenery/floating_isle_fall_{i}.png') for i in range(4)]
    if all(os.path.exists(f) for f in falls):
        fr = [Image.open(f).crop((200, 400, 600, 960)) for f in falls]
        s = Image.new('RGBA', (400 * 4 + 50, 560 + 20), (40, 190, 215, 255))
        for i, im in enumerate(fr):
            s.alpha_composite(im, (10 + i * 410, 10))
        s.convert('RGB').save(os.path.join(PREV, 'falls.png'))


if __name__ == '__main__':
    main()
