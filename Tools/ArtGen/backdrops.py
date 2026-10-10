"""
backdrops.py - the three 4096x1536 horizon panoramas that sit above the north
edge of the world and scroll with parallax:

  backdrop_lagoon.png  Blue Lagoon (bright day)
  backdrop_city.png    Glass City (golden-white afternoon)
  backdrop_moon.png    Moonpool (magical night)

Layout contract (shared with the game):
  * horizon at y = HZ = 1150; rows below are far ocean whose alpha falls
    smoothly 1 -> 0 at the bottom row so it melts into the in-game water;
  * sky is fully opaque;
  * the outer 300 px on each side fade part-way toward the plain vertical
    sky/ocean profile so neighbouring panels can crossfade / tile.

Rendering reuses the aqua.py SDF painter at ss=1 (analytic AA from the SDFs)
with local layers; distant groups are painted on their own full-size
"Group" canvas and composited with atmospheric haze.

Usage:  python3 backdrops.py [lagoon] [city] [moon]
"""
import math
import os
import sys
import time
import numpy as np
from PIL import Image
from aqua import *
from artkit import Layer, spine, bezier, sparkle, WHITE, GLOW, ART
import ui_scene as US
from ui_scene import SLayer

W, H, HZ = 4096, 1536, 1150
OUT = os.path.join(ART, 'Backgrounds')
PREV = ('/private/tmp/claude-501/-Users-markguggenheim-AquaScape/'
        'de2db03f-47af-475d-a625-9aefc8d08a9d/scratchpad/backdrop_preview')


# ----------------------------------------------------------------------------
# Infrastructure
# ----------------------------------------------------------------------------

class Group(Canvas):
    """Transparent full-size canvas sharing the base canvas' coordinates."""

    def __init__(self, base):
        self.w, self.h, self.ss = base.w, base.h, base.ss
        self.P = np.zeros_like(base.P)
        self.A = np.zeros_like(base.A)
        self.X, self.Y, self.px = base.X, base.Y, base.px


def merge(c, g, haze=None, amt=0.0, opacity=1.0, rows=None):
    """Composite group g over c, pulling its colour toward `haze` by amt
    (scalar or per-pixel field)."""
    y0, y1 = rows if rows else (0, c.h)
    P, A = g.P[y0:y1], g.A[y0:y1] * opacity
    if haze is not None:
        a = amt[y0:y1] if np.ndim(amt) else amt
        a = a[..., None] if np.ndim(a) else a
        P = P * (1 - a) + np.asarray(haze) * g.A[y0:y1, :, None] * a
    P = P * opacity
    c.P[y0:y1] = P + c.P[y0:y1] * (1 - A[..., None])


def new_canvas():
    c = Canvas(W, H, 1)
    c.X = c.X.astype(np.float32)
    c.Y = c.Y.astype(np.float32)
    c.P = c.P.astype(np.float32)
    c.A = c.A.astype(np.float32)
    return c


def region(c, x0, y0, x1, y1):
    x0, y0 = int(max(0, math.floor(x0))), int(max(0, math.floor(y0)))
    x1, y1 = int(min(c.w, math.ceil(x1))), int(min(c.h, math.ceil(y1)))
    if x1 <= x0 or y1 <= y0:
        return None
    return (slice(y0, y1), slice(x0, x1))


def blob_add(c, x, y, rx, ry, col, a):
    """Additive anisotropic gaussian (fast, no layer allocation)."""
    sl = region(c, x - rx * 3, y - ry * 3, x + rx * 3, y + ry * 3)
    if sl is None:
        return
    X, Y = c.X[sl], c.Y[sl]
    g = np.exp(-(((X - x) / rx) ** 2 + ((Y - y) / ry) ** 2)) * a
    c.P[sl] += np.asarray(col) * g[..., None]


def profile(sky, sea, gamma=1.0, sea_gamma=0.7):
    """Plain vertical colour profile (H, 3): used for the base and edge fades."""
    y = np.arange(H) + 0.5
    ts = clamp01(y / HZ) ** gamma
    to = clamp01((y - HZ) / (H - HZ)) ** sea_gamma
    return np.where((y < HZ)[:, None], gradient_map(ts, sky), gradient_map(to, sea))


def noise1d(n, spacing, seed, octaves=3):
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        s = max(1.0, spacing / 2 ** o)
        k = int(n / s) + 3
        v = rng.random(k)
        xs = np.arange(n) / s
        i = np.floor(xs).astype(int)
        f = xs - i
        f = f * f * (3 - 2 * f)
        out += (v[i] * (1 - f) + v[i + 1] * f) * amp
        tot += amp
        amp *= 0.5
    return out / tot


def finalize(c, prof, name, seed=0, edge_min=0.3):
    C = c.P.copy()
    x = np.arange(W) + 0.5
    e = np.minimum(x, W - x)
    wgt = edge_min + (1 - edge_min) * smoothstep(0, 300, e)
    C = prof[:, None, :] + (C - prof[:, None, :]) * wgt[None, :, None]
    y = np.arange(H) + 0.5
    t = clamp01((y - HZ) / (H - HZ))
    a = np.where(y < HZ, 1.0, 0.5 * (1 + np.cos(np.pi * t)))
    rng = np.random.default_rng(seed)
    dith = (rng.random((H, W, 3)) - rng.random((H, W, 3))) * 0.9
    rgb8 = np.clip(clamp01(C) * 255 + dith + 0.5, 0, 255).astype(np.uint8)
    a8 = np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    out = np.dstack([rgb8, np.broadcast_to(a8[:, None], (H, W))])
    img = Image.fromarray(out)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + '.png')
    img.save(path, optimize=False)
    # previews: over the in-game water colour
    os.makedirs(PREV, exist_ok=True)
    bgcol = (13, 15, 66) if 'moon' in name else (0, 163, 209)
    bg = Image.new('RGBA', img.size, bgcol + (255,))
    bg.alpha_composite(img)
    small = bg.resize((2048, 768), Image.LANCZOS).convert('RGB')
    small.save(os.path.join(PREV, name + '.png'))
    return path


# ----------------------------------------------------------------------------
# Sky elements
# ----------------------------------------------------------------------------

def cloud(g, cx, base, w, h, hi, lo, rim, seed, alpha=1.0, haze_col=None,
          haze=0.0, bounce=None, flat=True, ao=0.22):
    """Illustrated cumulus: sphere-shaded puffs with ambient occlusion between
    them, blue shading at the base, bright rims on top."""
    rng = np.random.default_rng(seed)
    L = SLayer(g, cx - w / 2 - h * 0.7, base - h * 1.65, w + h * 1.4, h * 1.65 + 40)
    if haze_col is not None:
        hi, lo, rim = mix(hi, haze_col, haze), mix(lo, haze_col, haze * 0.85), mix(rim, haze_col, haze * 0.5)
    puffs = []
    n = int(12 + w / 24)
    for i in range(n):
        u = rng.uniform(-1, 1)
        env = (1 - u * u) ** 0.6
        r = h * rng.uniform(0.26, 0.52) * (0.45 + 0.55 * env)
        x = cx + u * w / 2 * 0.92
        y = base - r * 0.5 - rng.uniform(0, 1) ** 0.8 * env * h * 0.85
        puffs.append((y, x, r))
    puffs.sort()
    for y, x, r in puffs:
        y0 = int(max(0, y - r * 1.4 - L.y0)); y1 = int(min(L.A.shape[0], y + r * 1.4 - L.y0 + 2))
        x0 = int(max(0, x - r * 1.4 - L.x0)); x1 = int(min(L.A.shape[1], x + r * 1.4 - L.x0 + 2))
        if y1 <= y0 or x1 <= x0:
            continue
        sub = (slice(y0, y1), slice(x0, x1))
        X, Y = L.X[sub], L.Y[sub]
        bottom = smoothstep(base + 8, base - 12, Y) if flat else 1.0
        vert = clamp01((Y - (base - h * 1.35)) / (h * 1.35))
        dx, dy = (X - x) / r, (Y - y) / r
        d = np.hypot(X - x, Y - y) - r
        Pa, Aa = L.P[sub], L.A[sub]
        occ = smoothstep(r * 0.35, 0, d) * (d > -1) * Aa * ao * bottom
        Pa = lo * occ[..., None] + Pa * (1 - occ[..., None])
        Aa = occ + Aa * (1 - occ)
        nz_ = np.sqrt(clamp01(1 - dx * dx - dy * dy))
        nl = np.sqrt(dx * dx + dy * dy + nz_ * nz_) + 1e-9
        nx, ny, nzz = dx / nl, dy / nl, nz_ / nl
        lam = clamp01(nx * -0.3 + ny * -0.72 + nzz * 0.5)
        col = mix(hi, lo, clamp01((1 - lam) * 0.5 + vert * 0.6)[..., None])
        rimf = clamp01(-ny - nx * 0.3) * (1 - nzz) ** 1.6
        col = mix(col, rim, (rimf * 0.85)[..., None])
        if bounce is not None:
            bf = clamp01(ny) * (1 - nzz) ** 2 * vert
            col = mix(col, bounce, (bf * 0.5)[..., None])
        a = clamp01(0.5 - d / (max(1.5, r * 0.035) * 1.5)) * bottom
        L.P[sub] = clamp01(col) * a[..., None] + Pa * (1 - a[..., None])
        L.A[sub] = a + Aa * (1 - a)
    L.commit(alpha)


def wisp(g, cx, cy, w, h, col, seed, alpha=0.5):
    L = SLayer(g, cx - w / 2 - 20, cy - h * 2 - 20, w + 40, 4 * h + 40)
    nz = value_noise(L.w, L.h, 40, seed=seed, octaves=4)
    streak = noise1d(L.h, 6, seed + 1, 2)[:, None]
    e = np.exp(-(((L.X - cx) / (w / 2)) ** 2 * 1.6 + ((L.Y - cy) / h) ** 2))
    a = clamp01(e * (0.45 + nz * 0.9 + streak * 0.3) - 0.35) * alpha
    L.over(np.asarray(col), a)
    L.commit()


def lens_flare(c, sx, sy, strength=1.0, tint=None):
    tint = rgb('#fff6dc') if tint is None else tint
    rows = slice(0, HZ + 200)
    X, Y = c.X[rows], c.Y[rows]
    D = np.hypot(X - sx, Y - sy)
    bloom = np.exp(-(D / 60) ** 2) * 1.1 + np.exp(-(D / 190) ** 2) * 0.32 + np.exp(-(D / 700) ** 2) * 0.11
    ang = np.arctan2(Y - sy, X - sx)
    rays = ((0.5 + 0.5 * np.sin(ang * 13 + 0.4)) ** 10 * 0.16 +
            (0.5 + 0.5 * np.sin(ang * 29 + 2.0)) ** 14 * 0.10) * np.exp(-D / 650)
    streak = np.exp(-((Y - sy) / 4) ** 2) * np.exp(-np.abs(X - sx) / 900) * 0.35
    c.P[rows] += (tint * (bloom + rays)[..., None] + rgb('#c4f4ff') * streak[..., None]) * strength
    # ghosts along the line through the image centre
    cx, cy = W * 0.5, H * 0.42
    ghosts = [(0.28, 46, '#9ff8ff', 0.10, 'disc'), (0.42, 22, '#ffffff', 0.18, 'disc'),
              (0.55, 90, '#b6ffcc', 0.06, 'hex'), (0.75, 34, '#ffe08a', 0.10, 'disc'),
              (1.1, 140, '#c8b4ff', 0.05, 'ring'), (1.35, 60, '#8ff0ff', 0.08, 'hex'),
              (1.6, 26, '#ffffff', 0.12, 'disc')]
    for t, r, col, a, kind in ghosts:
        gx, gy = sx + (cx - sx) * t, sy + (cy - sy) * t
        sl = region(c, gx - r * 1.6, gy - r * 1.6, gx + r * 1.6, gy + r * 1.6)
        if sl is None:
            continue
        X, Y = c.X[sl], c.Y[sl]
        dx, dy = X - gx, Y - gy
        if kind == 'hex':
            k = np.maximum.reduce([np.abs(dx * math.cos(q) + dy * math.sin(q)) for q in (0, math.pi / 3, 2 * math.pi / 3)])
            d = k - r * 0.87
        else:
            d = np.hypot(dx, dy) - r
        fill = clamp01(0.5 - d / 4) * (0.6 if kind != 'ring' else 0.0)
        ring = np.exp(-(d / (r * 0.06 + 1.5)) ** 2)
        c.P[sl] += rgb(col) * ((fill + ring) * a * strength)[..., None]


def rainbow(c, cx, cy, R, width, alpha):
    sl = region(c, cx - R - width, 0, cx + R + width, HZ)
    X, Y = c.X[sl], c.Y[sl]
    r = np.hypot(X - cx, Y - cy)
    t = (r - (R - width / 2)) / width
    band = smoothstep(-0.15, 0.12, t) * smoothstep(1.15, 0.88, t)
    col = gradient_map(t, [(0, rgb('#a070ff')), (0.18, rgb('#4f8cff')), (0.38, rgb('#3fe0b0')),
                           (0.58, rgb('#fff26a')), (0.78, rgb('#ffa64a')), (1.0, rgb('#ff6a8a'))])
    fade = smoothstep(HZ - 20, HZ - 420, Y) * alpha
    a = band * fade
    c.P[sl] = c.P[sl] * (1 - a[..., None]) + col * a[..., None]
    # sky is a touch brighter inside the bow
    inside = smoothstep(R - width / 2, R - width * 2.5, r) * fade * 0.10
    c.P[sl] += (rgb('#ffffff') * inside[..., None])


# ----------------------------------------------------------------------------
# Islands, turbines, palms
# ----------------------------------------------------------------------------

def sky_island(g, pal, cx, top, rx, seed=4, vines=9):
    """Floating island (scaled version of ui_scene.floating_island)."""
    s = rx / 250.0
    rng = np.random.default_rng(seed)
    tip = top + 300 * s
    L = SLayer(g, cx - rx - 70 * s, top - 90 * s, 2 * rx + 140 * s, tip - top + 170 * s)
    d = sd_ellipse(L, cx, top + 16 * s, rx - 4 * s, 30 * s)
    lobes = [(-0.62, 0.38, 0.22), (-0.3, 0.72, 0.26), (0.02, 1.0, 0.3), (0.35, 0.62, 0.24), (0.66, 0.3, 0.2)]
    for lx, ll, lw in lobes:
        ll *= rng.uniform(0.85, 1.1)
        x = cx + lx * rx
        d = op_smooth_union(d, sd_capsule(L, x, top + 20 * s, x + lx * 10 * s,
                                          top + 20 * s + ll * (tip - top - 20 * s), lw * rx, 13 * s), 40 * s)
    n = normals(L, height_bevel(d, 70 * s))
    lam = clamp01((n * np.array([-0.55, -0.35, 0.75])).sum(axis=2))
    v = clamp01((L.Y - top) / (tip - top))
    col = gradient_map(v, [(0, pal['ceramic_hi']), (0.55, mix(pal['ceramic_hi'], pal['ceramic_lo'], 0.45)),
                           (1, pal['ceramic_lo'])])
    col = col * (0.72 + 0.36 * lam)[..., None]
    nz = value_noise(L.w, L.h, max(3, int(14 * s)), seed=seed + 1, octaves=3)
    col = col * (0.95 + 0.08 * nz)[..., None]
    led = ((L.Y - top - 8 * s + (L.X - cx) ** 2 / (rx * 9)) % (36 * s)) / (36 * s)
    col = mix(col, col * 0.84, (smoothstep(0.86, 1.0, led) * 0.55)[..., None])
    col = col + (smoothstep(0.5, 1.0, v) * clamp01(n[..., 1]))[..., None] * np.array([0.0, 0.12, 0.14])
    by = top + 50 * s + ((L.X - cx) / rx) ** 2 * 18 * s
    band = smoothstep(9 * s, 7 * s, np.abs(L.Y - by))
    bcol = gradient_map(clamp01((L.Y - by + 8 * s) / (16 * s)), [(0, rgb('#c8fdff')), (0.5, pal['glass']), (1, rgb('#1590d6'))])
    col = mix(col, bcol, (band * 0.92)[..., None])
    col = col + spec(n, 30)[..., None] * 0.25
    L.over(clamp01(col), L.cover(d))
    if pal['light']:
        L.glow(op_inter(d, np.abs(L.Y - by) - 8 * s), rgb('#7ff8ff'), 12 * s, 0.4)
    for i in range(vines):
        vx = cx - rx * 0.85 + i * rx * 1.7 / max(1, vines - 1) + rng.uniform(-8, 8) * s
        vl = rng.uniform(40, 130) * s * (1 - abs(vx - cx) / rx * 0.4)
        vpts = [(vx + math.sin(k * 0.6 + i) * 4 * s, top + 26 * s + k * vl / 10) for k in range(11)]
        dist, t, _ = spine(L, vpts)
        L.over(mix(pal['leaf_mid'], pal['leaf_lo'], t[..., None]), L.cover(dist - (3.0 - 1.8 * t) * max(s, 0.45)))
        for k in range(2, 11, 3):
            lx, ly = vpts[k]
            side = (4 if k % 2 else -4) * s
            L.over(pal['leaf_hi'], L.cover(sd_ellipse(L, lx + side, ly, 5.5 * s + 0.5, 3.2 * s + 0.4)))
    L.commit()
    # grass dome
    L = SLayer(g, cx - rx - 50 * s, top - 80 * s, 2 * rx + 100 * s, 140 * s)
    nz = value_noise(L.w, L.h, max(3, int(16 * s)), seed=seed + 9, octaves=2)
    gd = sd_ellipse(L, cx, top + 2 * s, rx + 10 * s, 38 * s) + (nz - 0.5) * 8 * s
    ex = clamp01(1 - ((L.X - cx) / (rx + 10 * s)) ** 2)
    ye = top + 2 * s + 38 * s * np.sqrt(ex)
    scal = (7 + 6 * np.abs(np.sin((L.X - cx) / (11.0 * s)))) * s * np.sqrt(ex)
    drape = op_inter(-(L.Y - (ye - 3 * s)), L.Y - (ye + scal)) + (ex < 0.02) * 100.0
    L.over(pal['grass'][2][1], L.cover(drape))
    gn = normals(L, height_bevel(gd, 26 * s))
    t = clamp01((L.Y - (top - 36 * s)) / (76 * s))
    gc = gradient_map(t, pal['grass'])
    gc = gc * (0.82 + 0.25 * lambert(gn))[..., None] + spec(gn, 30)[..., None] * 0.2
    L.over(clamp01(gc), L.cover(gd))
    L.over(pal['grass'][0][1], L.cover(np.abs(gd + 3 * s) - 2 * s) * smoothstep(top - 10 * s, top + 20 * s, L.Y) * 0.7)
    L.over(WHITE, L.cover(sd_ellipse(L, cx - 50 * s, top - 16 * s, rx * 0.6, 9 * s), 8) * 0.2)
    L.commit()


def sky_fall(g, x0, y0, length, w, seed=2, tint='#c8f8ff'):
    """Waterfall pouring off a floating island, dissolving into mist."""
    L = SLayer(g, x0 - w * 5, y0 - 10, w * 10, length + w * 3)
    nz = value_noise(L.w, L.h, max(2, int(w / 4)), seed=seed, octaves=2)
    t = clamp01((L.Y - y0) / length)
    hw = w * (0.5 + 0.9 * t)
    xc = x0 - w * 0.8 * t ** 2
    d = op_inter(np.abs(L.X - xc) - hw, -(L.Y - y0))
    streak = np.sin((L.X - xc) / hw * 9 + nz * 5) * 0.5 + 0.5
    col = mix(rgb(tint), WHITE, (streak * 0.7)[..., None])
    fade = 1 - smoothstep(0.35, 1.0, t)
    a = L.cover(d, 1 + t * 8) * (0.55 + 0.4 * streak) * fade * smoothstep(y0 - 2, y0 + 6, L.Y)
    L.over(col, a)
    mist = np.zeros(L.X.shape)
    rng = np.random.default_rng(seed)
    for k in range(9):
        mx = x0 - w * 0.8 * 0.5 + rng.uniform(-1.6, 1.6) * w
        my = y0 + length * rng.uniform(0.55, 0.9)
        mist = np.maximum(mist, np.exp(-((L.X - mx) ** 2 + (L.Y - my) ** 2) / (2 * (w * rng.uniform(0.9, 1.6)) ** 2)))
    L.over(WHITE, mist * 0.45)
    L.commit()


def turbine(g, x, base, h, ang, col_hi, col_lo):
    L = SLayer(g, x - h * 0.62, base - h * 1.6, h * 1.24, h * 1.6 + 6)
    hx, hy = x, base - h
    w0, w1 = h * 0.028, h * 0.013
    pole = sd_capsule(L, x, base + 4, hx, hy, w0, w1)
    u = np.clip((L.X - x) / w0, -1, 1)
    pc = mix(col_lo, col_hi, clamp01(0.75 - u * 0.5)[..., None])
    L.over(pc, L.cover(pole))
    nac = sd_capsule(L, hx - h * 0.02, hy, hx + h * 0.07, hy, h * 0.03)
    L.over(mix(col_hi, col_lo, 0.25), L.cover(nac))
    for k in range(3):
        a = ang + k * 2 * math.pi / 3
        ex, ey = hx + math.cos(a) * h * 0.52, hy + math.sin(a) * h * 0.52
        bl = sd_capsule(L, hx, hy, ex, ey, h * 0.022, h * 0.006)
        # flat blade: lit on one side
        side = ((L.X - hx) * -math.sin(a) + (L.Y - hy) * math.cos(a)) > 0
        L.over(mix(col_hi, col_lo, (side * 0.35)[..., None]), L.cover(bl))
    L.over(col_hi, L.cover(sd_circle(L, hx, hy, h * 0.03)))
    L.commit()


def hills_island(g, pal, x0, x1, hmax, seed, base=HZ + 3):
    rng = np.random.default_rng(seed)
    L = SLayer(g, x0 - 40, base - hmax * 1.3, x1 - x0 + 80, hmax * 1.3 + 12)
    d = np.full(L.X.shape, 1e9)
    n = 4 + int((x1 - x0) / 220)
    for i in range(n):
        u = (i + 0.5) / n
        cx = x0 + (x1 - x0) * u + rng.uniform(-30, 30)
        hh = hmax * rng.uniform(0.45, 1.0) * (1 - (2 * u - 1) ** 2 * 0.6)
        rx = (x1 - x0) / n * rng.uniform(0.75, 1.1)
        d = op_smooth_union(d, sd_ellipse(L, cx, base, rx, hh), 22)
    d = op_inter(d, L.Y - base)
    nml = normals(L, height_bevel(d, hmax * 0.6))
    t = clamp01((L.Y - (base - hmax)) / hmax)
    col = gradient_map(t, pal['grass'])
    col = col * (0.78 + 0.32 * lambert(nml))[..., None] + spec(nml, 25)[..., None] * 0.15
    L.over(clamp01(col), L.cover(d))
    # white sand rim at the waterline
    L.over(rgb('#f4fbff'), L.cover(op_inter(d, -(L.Y - (base - 7)))) * 0.9)
    L.commit()
    return d


def dolphin(g, x, y, L_, flip=False, col_top='#4f86c4', col_bot='#e6f6ff'):
    """Small jumping dolphin arc (x,y = water entry point of the nose side)."""
    sgn = -1 if flip else 1
    p0 = (x, y)
    p1 = (x + sgn * L_ * 0.5, y - L_ * 0.62)
    p2 = (x + sgn * L_ * 1.0, y - L_ * 0.05)
    pts = bezier(p0, p1, p2, 28)
    pts = pts[4:24]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    Ly = SLayer(g, min(xs) - L_ * 0.3, min(ys) - L_ * 0.3, max(xs) - min(xs) + L_ * 0.6, max(ys) - min(ys) + L_ * 0.5)
    dist, t, s = spine(Ly, pts[::-1] if not flip else pts)
    # t=0 nose ... t=1 tail
    wp = L_ * 0.085 * np.sin(np.pi * clamp01(t * 0.92 + 0.04) ** 0.7) ** 0.9 + 0.6
    d = dist - wp
    fin_t = 0.42
    fx, fy = pts[::-1][int(len(pts) * fin_t)] if not flip else pts[int(len(pts) * fin_t)]
    fin = sd_poly(Ly, [(fx - L_ * 0.06, fy - wp.max() * 0.5), (fx + L_ * 0.04 * sgn * -1, fy - L_ * 0.17),
                       (fx + L_ * 0.07, fy - wp.max() * 0.3)])
    tx, ty = (pts[0] if not flip else pts[-1])
    fl = op_union(sd_ellipse(Ly, tx - L_ * 0.06, ty + L_ * 0.03, L_ * 0.07, L_ * 0.025),
                  sd_ellipse(Ly, tx + L_ * 0.06, ty + L_ * 0.03, L_ * 0.07, L_ * 0.025))
    body = op_union(d, fin, fl)
    up = smoothstep(-wp * 0.4, wp * 0.6, s * (1 if not flip else -1))
    col = mix(rgb(col_top), rgb(col_bot), up[..., None] * 0.85)
    col = col + (np.exp(-((s + wp * 0.4) / (wp * 0.25 + 0.5)) ** 2) * 0.25)[..., None]
    Ly.over(clamp01(col), Ly.cover(body))
    Ly.commit()


# ----------------------------------------------------------------------------
# Architecture
# ----------------------------------------------------------------------------

CHROME = [(0.0, rgb('#5d7aa6')), (0.25, rgb('#aac4e2')), (0.45, rgb('#ffffff')),
          (0.55, rgb('#e8f4ff')), (0.75, rgb('#7d9cc6')), (1.0, rgb('#d9ecff'))]


def chrome_ring(g, cx, cy, rx, ry, th, part, glow=True):
    pad = th + 8
    L = SLayer(g, cx - rx - pad, cy - ry - pad, 2 * (rx + pad), 2 * (ry + pad))
    k = np.hypot((L.X - cx) / rx, (L.Y - cy) / ry)
    d = np.abs(k - 1) * ry - th
    ang = np.arctan2((L.Y - cy) / ry, (L.X - cx) / rx)
    front = smoothstep(cy - 1.5, cy + 1.5, L.Y)
    m = front if part == 'front' else 1 - front
    t = 0.5 + 0.5 * np.cos(ang + 2.4)
    col = gradient_map(t, CHROME)
    # inner/outer edge lines (across the band)
    acr = (k - 1) * ry / th
    col = mix(col, rgb('#ffffff'), (np.exp(-((acr + 0.55) / 0.22) ** 2) * 0.7)[..., None])
    col = mix(col, rgb('#4d6a96'), (np.exp(-((acr - 0.7) / 0.2) ** 2) * 0.35)[..., None])
    if part == 'back':
        col = col * 0.82
    L.over(clamp01(col), L.cover(d) * m)
    if glow and part == 'front':
        L.glow(d, GLOW, th * 1.8, 0.25 * m)
    L.commit()


def needle(g, x, base, h, w, pal, rings, night=False, pod=True):
    """Futuristic needle tower: tapered white shaft, glass pod, chrome rings."""
    top = base - h
    # rings: back halves first
    for (fy, rr, th) in rings:
        chrome_ring(g, x, base - h * fy, w * rr, w * rr * 0.26, th, 'back')
    L = SLayer(g, x - w * 1.3, top - 30, w * 2.6, h + 40)
    prof = [(0.0, 1.0), (0.18, 0.78), (0.45, 0.5), (0.7, 0.32), (0.86, 0.16), (1.0, 0.025)]
    lp = [(x - w * r, base - h * f) for f, r in prof]
    rp = [(x + w * r, base - h * f) for f, r in prof[::-1]]
    d = sd_poly(L, [(x - w, base + 6)] + lp + rp + [(x + w, base + 6)])
    fy = clamp01((base - L.Y) / h)
    hw = np.interp(fy, [p[0] for p in prof], [p[1] for p in prof]) * w
    u = np.clip((L.X - x) / np.maximum(hw, 0.5), -1, 1)
    lam = clamp01(0.5 - u * 0.55 + np.sqrt(1 - u * u) * 0.3)
    col = mix(pal['ceramic_lo'], pal['ceramic_hi'], lam[..., None])
    col = col + (np.exp(-((u + 0.45) / 0.12) ** 2) * 0.25)[..., None]
    # aqua glass seams spiralling up
    seam = np.abs(((L.Y * 0.06 + u * 1.2) % 1.0) - 0.5) < 0.05
    col = mix(col, pal['glass'], (seam * (fy > 0.08) * 0.45)[..., None])
    if night:
        col = col + seam[..., None] * rgb('#4fe8ff') * 0.4
    L.over(clamp01(col), L.cover(d))
    L.commit()
    if pod:
        py, pr = base - h * 0.66, w * 0.62
        L = SLayer(g, x - pr * 2.2, py - pr * 2.2, pr * 4.4, pr * 4.4)
        dd = sd_ellipse(L, x, py, pr * 1.35, pr * 0.8)
        n = sphere_normals(L, x, py, pr * 1.35, pr * 0.8)
        tcol = gradient_map(clamp01(0.5 + 0.5 * n[..., 1]), [(0, rgb('#e2fbff')), (0.5, rgb('#56cff2')), (1, rgb('#1f78c8'))])
        if night:
            tcol = gradient_map(clamp01(0.5 + 0.5 * n[..., 1]), [(0, rgb('#c8ffff')), (0.5, rgb('#3fc8f0')), (1, rgb('#2a3aa0'))])
        tcol = tcol + spec(n, 60)[..., None] * 1.2
        band = np.abs(L.Y - py) < pr * 0.1
        tcol = mix(tcol, pal['ceramic_hi'], (band * 0.85)[..., None])
        if night:
            L.glow(dd, GLOW, pr * 0.9, 0.4)
        L.over(clamp01(tcol), L.cover(dd))
        L.commit()
    for (fy, rr, th) in rings:
        chrome_ring(g, x, base - h * fy, w * rr, w * rr * 0.26, th, 'front')
    # tip light
    L = SLayer(g, x - 40, top - 50, 80, 80)
    td = sd_circle(L, x, top - 4, 3.5)
    L.glow(td, GLOW if not night else rgb('#ff9ae6'), 14, 0.9)
    L.over(WHITE, L.cover(td))
    L.commit()


def building(g, x, base, w, h, kind, pal, night=False, seed=0):
    """Hero-scale glass / ceramic tower, lit from the upper left."""
    rng = np.random.default_rng(seed)
    top = base - h
    L = SLayer(g, x - w * 1.6 - 20, top - w * 1.4 - 40, w * 3.2 + 40, h + w * 1.4 + 50)
    u = np.clip((L.X - x) / w, -1, 1)
    cyl = np.sqrt(1 - u * u)
    ry = clamp01((L.Y - top) / h)
    glow_parts = []
    if kind == 'glass':
        d = op_inter(sd_capsule(L, x, base + w, x, top + w, w), L.Y - base - 4)
        col = gradient_map(clamp01(0.5 + 0.5 * u), [(0, rgb('#e8fdff')), (0.3, rgb('#86e0fa')),
                                                      (0.65, rgb('#2fa4e6')), (1, rgb('#1866b8'))])
        if night:
            col = gradient_map(clamp01(0.5 + 0.5 * u), [(0, rgb('#5a7ae0')), (0.5, rgb('#24338a')), (1, rgb('#121a56'))])
        # sky reflection: lighter at the top, warm glint low
        col = mix(col, rgb('#f2fbff') if not night else rgb('#6a6ad0'), ((1 - ry) ** 3 * 0.35)[..., None])
        floors = (((L.Y - top) % 16) < 1.6) * 0.12
        col = col * (1 - floors)[..., None]
        col = col + (np.exp(-((u + 0.5) / 0.08) ** 2) * 0.55 + np.exp(-((u - 0.55) / 0.03) ** 2) * 0.35)[..., None]
        bands = (np.abs(((L.Y - top - w * 1.2) % 130) - 65) > 60) * (L.Y > top + w * 1.1)
        col = mix(col, pal['ceramic_hi'], (bands * 0.85)[..., None])
        if night:
            lights = (((L.Y - top) % 16) > 5) * (((L.X - x + w) % 9) < 4) * (np.abs(u) < 0.85)
            pick = value_noise(L.w, L.h, 7, seed=seed, octaves=1) > 0.58
            col = mix(col, rgb('#9ffcff'), (lights * pick * 0.85)[..., None])
    elif kind == 'white':
        d = op_inter(sd_capsule(L, x, base + w, x, top + w * 0.6, w, w * 0.6), L.Y - base - 4)
        lam = clamp01(cyl * 0.65 - u * 0.4 + 0.25)
        col = mix(pal['ceramic_lo'], pal['ceramic_hi'], lam[..., None])
        win = (np.abs(u + 0.05) < 0.28) * (L.Y > top + w * 0.9)
        wcol = gradient_map(clamp01(0.5 + 0.5 * u / 0.3), [(0, rgb('#bff6ff')), (1, rgb('#2a96dc'))])
        if night:
            wcol = mix(wcol, rgb('#7ff8ff'), 0.4)
        col = mix(col, wcol, (win * 0.9)[..., None])
        ribs = ((L.Y - top) % 44 < 3) * win
        col = mix(col, pal['ceramic_hi'], (ribs * 0.7)[..., None])
    elif kind == 'pod':
        d = sd_capsule(L, x, base + 4, x, top + w * 1.5, w * 0.32, w * 0.2)
        lam = clamp01(cyl * 0.6 - u * 0.4 + 0.3)
        col = mix(pal['ceramic_lo'], pal['ceramic_hi'], lam[..., None])
    else:  # 'disc' tower
        d = sd_capsule(L, x, base + 4, x, top, w * 0.4, w * 0.22)
        lam = clamp01(cyl * 0.6 - u * 0.4 + 0.3)
        col = mix(pal['ceramic_lo'], pal['ceramic_hi'], lam[..., None])
    L.over(clamp01(col), L.cover(d))
    if kind in ('glass', 'white'):
        cap = sd_ellipse(L, x, top + w * (0.95 if kind == 'glass' else 0.7), w * 0.92, w * 0.18)
        L.over(WHITE, L.cover(cap, 2) * 0.35)
        ant = sd_capsule(L, x, top + 4, x, top - w * 1.1, max(1.2, w * 0.05))
        L.over(pal['ceramic_hi'], L.cover(ant))
        tip = sd_circle(L, x, top - w * 1.1, max(2.5, w * 0.1))
        L.glow(tip, GLOW if not night else rgb('#ff9ae6'), max(6, w * 0.3), 0.8)
        # glowing aqua ring near the top
        gy = top + w * 1.6
        gl = op_inter(d, np.abs(L.Y - gy) - max(2, w * 0.07))
        L.over(rgb('#aaffff'), L.cover(gl))
        L.glow(gl, GLOW, max(5, w * 0.25), 0.45 if not night else 0.8)
    if kind == 'pod':
        py, pr = top + w * 1.2, w * 1.1
        dd = sd_circle(L, x, py, pr)
        n = sphere_normals(L, x, py, pr)
        pc = gradient_map(clamp01(0.5 + 0.5 * n[..., 1]), [(0, rgb('#ecfdff')), (0.5, rgb('#5fd6f6')), (1, rgb('#1d6fc0'))])
        pc = pc + spec(n, 70)[..., None] * 1.3
        pc = mix(pc, WHITE, ((np.abs(L.Y - py) < pr * 0.08) * 0.85)[..., None])
        if night:
            L.glow(dd, GLOW, pr * 0.6, 0.5)
        L.over(clamp01(pc), L.cover(dd))
    if kind == 'disc':
        dy = top + h * 0.12
        dd = op_smooth_union(sd_ellipse(L, x, dy, w * 1.6, w * 0.28), sd_ellipse(L, x, dy - w * 0.25, w * 0.8, w * 0.4), 8)
        n = normals(L, height_bevel(dd, w * 0.4))
        dc = mat_plastic(n, '#ffffff', '#9fb6d8', 0.8)
        under = smoothstep(dy, dy + w * 0.3, L.Y)
        dc = mix(dc, rgb('#5fe0ff'), (under * 0.7)[..., None])
        L.over(dc, L.cover(dd))
        L.glow(op_inter(dd, -(L.Y - dy - w * 0.12)), GLOW, w * 0.4, 0.5)
    L.commit()


def geo_dome(g, cx, base, r, pal, night=False, seed=0, cells=7.0):
    """Eden-Project style geodesic glass dome full of greenery."""
    L = SLayer(g, cx - r - 30, base - r - 30, 2 * r + 60, r + 40)
    d = op_inter(sd_circle(L, cx, base, r), L.Y - base)
    n = sphere_normals(L, cx, base, r)
    nx, ny, nz = n[..., 0], n[..., 1], n[..., 2]
    lon = np.arctan2(nx, nz)
    lat = np.arcsin(np.clip(-ny, -1, 1))
    K = cells / (math.pi / 2)
    fams = [lon * K, (lon * 0.5 + lat * 0.866) * K, (lon * 0.5 - lat * 0.866) * K]
    fd = np.minimum.reduce([np.abs(f - np.round(f)) for f in fams])
    # convert lattice distance to approx pixels, so lines stay ~even
    lw = max(0.9, r / 110)
    pxd = fd * r / K
    frame = clamp01(1 - (pxd - lw * 0.5) / 1.0) * (lat > 0.02)
    # interior greenery (seen through glass)
    gn = value_noise(L.w, L.h, max(4, int(r / 6)), seed=seed, octaves=3)
    fill_h = base - r * (0.55 + 0.35 * gn)
    green = smoothstep(fill_h - 6, fill_h + 6, L.Y)
    gcol = gradient_map(clamp01(gn * 1.4 - 0.2), [(0, pal['leaf_lo']), (0.5, pal['leaf_mid']), (1, pal['leaf_hi'])])
    # glass: reflect sky up top, aqua tint, fresnel to white
    t = clamp01(0.5 - 0.5 * ny)
    glass = gradient_map(t, [(0, rgb('#4fc8ec')), (0.6, rgb('#a8ecff')), (1, rgb('#f2fdff'))])
    if night:
        glass = gradient_map(t, [(0, rgb('#24307e')), (0.6, rgb('#3c58b0')), (1, rgb('#7c8ae0'))])
        gcol = gcol * 0.7 + rgb('#10406a') * 0.3
    col = mix(glass, gcol, (green * 0.75)[..., None])
    # panel facets: subtle per-cell brightness variation
    cid = np.floor(fams[0]) * 7.31 + np.floor(fams[1]) * 3.17
    col = col * (0.93 + 0.1 * (np.sin(cid) * 0.5 + 0.5))[..., None]
    fres = (1 - nz) ** 2
    col = mix(col, rgb('#ffffff') if not night else rgb('#9fa8ff'), (fres * 0.45)[..., None])
    col = col + spec(n, 120)[..., None] * 0.15
    col = mix(col, pal['ceramic_hi'], (frame * 0.85)[..., None])
    if night:
        col = col + (green * gn * 0.25)[..., None] * rgb('#5fffd0')
        L.glow(d, GLOW, r * 0.15, 0.35)
    L.over(clamp01(col), L.cover(d))
    # rim highlight
    L.over(WHITE, L.cover(np.abs(d + 1.5) - 1.0) * clamp01(-nx * 0.8 - ny * 0.6) * 0.8)
    L.commit()


def arch(g, x0, x1, base, h, w, pal, night=False):
    """Sweeping white parabolic arch."""
    pts = [(x0 + (x1 - x0) * t, base - h * (1 - (2 * t - 1) ** 2)) for t in np.linspace(0, 1, 40)]
    L = SLayer(g, x0 - w * 2 - 10, base - h - w * 2 - 10, x1 - x0 + w * 4 + 20, h + w * 3 + 20)
    dist, t, s = spine(L, pts)
    wt = w * (1.0 + 0.6 * (2 * t - 1) ** 2)
    d = op_inter(dist - wt, L.Y - base - 3)
    uu = np.clip(s / wt, -1, 1)
    lam = clamp01(0.55 + 0.4 * uu * (1 if True else -1) + np.sqrt(1 - uu * uu) * 0.2)
    col = mix(pal['ceramic_lo'], pal['ceramic_hi'], lam[..., None])
    col = col + (np.exp(-((uu - 0.35) / 0.15) ** 2) * 0.3)[..., None]
    L.over(clamp01(col), L.cover(d))
    gl = op_inter(dist - wt * 0.15, L.Y - base)
    L.over(rgb('#b8ffff'), L.cover(gl) * 0.8)
    L.glow(gl, GLOW, w * 0.6, 0.35 if not night else 0.7)
    L.commit()


def bridge(g, x0, x1, y, sag, w, pal, night=False):
    pts = [(x0 + (x1 - x0) * t, y - sag * (1 - (2 * t - 1) ** 2)) for t in np.linspace(0, 1, 30)]
    L = SLayer(g, x0 - 10, y - sag - w * 3 - 10, x1 - x0 + 20, sag + w * 6 + 20)
    dist, t, s = spine(L, pts)
    d = dist - w
    uu = np.clip(s / w, -1, 1)
    col = mix(pal['ceramic_hi'], pal['ceramic_lo'], clamp01(0.5 + 0.5 * uu)[..., None] * 0.6)
    L.over(col, L.cover(d))
    gl = np.abs(dist - w * 0.1) - max(0.8, w * 0.18)
    L.over(rgb('#9ff8ff'), L.cover(gl) * 0.9)
    L.glow(gl, GLOW, w * 0.8, 0.3 if not night else 0.6)
    L.commit()


def monorail(g, pts, w, pal, train_t=(0.3,), cars=4, night=False, pylon_base=HZ + 2):
    pts = np.asarray(pts, float)
    xs, ys = pts[:, 0], pts[:, 1]
    # pylons
    for k in range(0, len(pts), 6):
        px, py = pts[k]
        L = SLayer(g, px - w * 2, py - 4, w * 4, pylon_base - py + 8)
        dd = sd_capsule(L, px, py, px, pylon_base, w * 0.5, w * 0.8)
        uu = np.clip((L.X - px) / (w * 0.8), -1, 1)
        L.over(mix(pal['ceramic_lo'], pal['ceramic_hi'], clamp01(0.7 - uu * 0.4)[..., None]), L.cover(dd))
        L.commit()
    L = SLayer(g, xs.min() - 20, ys.min() - w * 6, xs.max() - xs.min() + 40, ys.max() - ys.min() + w * 9)
    dist, t, s = spine(L, pts)
    d = dist - w * 0.7
    L.over(mix(pal['ceramic_hi'], pal['ceramic_lo'], clamp01(0.5 + 0.5 * np.clip(s / w, -1, 1))[..., None] * 0.6), L.cover(d))
    L.over(rgb('#9ff8ff'), L.cover(np.abs(dist - w * 0.2) - 0.8) * 0.7)
    L.glow(d, GLOW, w, 0.15 if not night else 0.4)
    # train: offset spine slightly above the beam
    seg = np.hypot(*(pts[1:] - pts[:-1]).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    for tt in train_t:
        s0 = tt * cum[-1]
        for k in range(cars):
            a0, a1 = s0 + k * w * 9, s0 + k * w * 9 + w * 8
            p0 = (np.interp(a0, cum, xs), np.interp(a0, cum, ys) - w * 1.9)
            p1 = (np.interp(a1, cum, xs), np.interp(a1, cum, ys) - w * 1.9)
            cd = sd_capsule(L, p0[0], p0[1], p1[0], p1[1], w * 1.4)
            ly = clamp01((L.Y - (p0[1] - w * 1.4)) / (w * 2.8))
            tc = gradient_map(ly, [(0, rgb('#ffffff')), (0.6, rgb('#e2ecf8')), (1, rgb('#8ea8cc'))])
            win = np.abs(L.Y - (p0[1] + (p1[1] - p0[1]) * clamp01((L.X - p0[0]) / (p1[0] - p0[0] + 1e-6)) - w * 0.3)) < w * 0.42
            tc = mix(tc, rgb('#3fc8f0') if not night else rgb('#aaffff'), (win * 0.9)[..., None])
            L.over(tc, L.cover(cd))
            if night:
                L.glow(cd, GLOW, w * 2, 0.25)
    L.commit()


def crystal(g, x, base, h, w, tilt, c1, c2, glow_col, seed=0):
    ca, sa = math.cos(tilt), math.sin(tilt)

    def P(px, py):  # local (px along width, py up) -> image
        return (x + px * ca + py * sa, base - (py * ca - px * sa))
    pts = [P(-w, 0), P(-w, h * 0.78), P(0, h), P(w, h * 0.78), P(w, 0)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    L = SLayer(g, min(xs) - w * 4, min(ys) - w * 4, max(xs) - min(xs) + w * 8, max(ys) - min(ys) + w * 5)
    d = sd_poly(L, pts)
    lx = (L.X - x) * ca - (base - L.Y) * sa       # local x
    ly = (L.X - x) * sa + (base - L.Y) * ca       # local y (up)
    v = clamp01(ly / h)
    col = mix(rgb(c2), rgb(c1), v[..., None])
    facet = lx > w * 0.15
    col = mix(col, col * 0.62, (facet * 0.8)[..., None])
    col = col + (np.exp(-((lx + w * 0.45) / (w * 0.12)) ** 2) * 0.35 * v)[..., None]
    L.glow(d, rgb(glow_col), w * 2.2, 0.55)
    L.over(clamp01(col), L.cover(d) * 0.95)
    L.over(WHITE, L.cover(np.abs(lx - w * 0.15) - 0.7) * L.cover(d) * 0.5 * v)
    L.commit()


def jelly(g, x, y, r, col, seed=0):
    rng = np.random.default_rng(seed)
    col = rgb(col)
    G = SLayer(g, x - r * 5, y - r * 4.5, r * 10, r * 10.5)
    bell = op_inter(sd_ellipse(G, x, y, r, r * 0.82), G.Y - (y + r * 0.18))
    G.glow(bell, col, r * 1.3, 0.35)
    G.glow(bell, WHITE, r * 0.3, 0.2)
    # tendrils
    for k in range(6):
        ox = x + (k / 5 - 0.5) * r * 1.4
        ln = r * rng.uniform(2.2, 4.0)
        ph = rng.uniform(0, 6)
        pts = [(ox + math.sin(ph + j * 0.6) * r * 0.18 * (j / 10), y + r * 0.15 + j * ln / 10) for j in range(11)]
        dist, t, _ = spine(G, pts)
        G.add(mix(col, WHITE, 0.4), clamp01(1 - dist / (1.2 + r * 0.03)) * (1 - t) * 0.55)
        G.add(col, np.exp(-(dist / (r * 0.12)) ** 2) * (1 - t) * 0.18)
    G.commit_add()
    B = SLayer(g, x - r * 1.5, y - r * 1.3, r * 3, r * 2)
    bell = op_inter(sd_ellipse(B, x, y, r, r * 0.82), B.Y - (y + r * 0.18))
    tt = clamp01((B.Y - (y - r * 0.82)) / r)
    bc = mix(mix(col, WHITE, 0.55), col, tt[..., None])
    B.over(bc, B.cover(bell) * (0.85 - 0.4 * tt))
    hl = op_inter(sd_ellipse(B, x - r * 0.3, y - r * 0.4, r * 0.38, r * 0.22), bell)
    B.over(WHITE, B.cover(hl, 3) * 0.7)
    B.commit()


def star_field(c, n, seed, ymax, col=rgb('#dfe8ff')):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        x = rng.uniform(0, W)
        y = rng.uniform(0, 1) ** 1.25 * ymax
        r = rng.uniform(0.45, 1.3) if rng.random() > 0.06 else rng.uniform(1.4, 2.2)
        b = rng.uniform(0.35, 1.0) * (1 - 0.6 * (y / ymax) ** 2)
        tint = mix(col, rgb('#ffe2f4') if rng.random() < 0.3 else rgb('#bff6ff'), rng.uniform(0, 0.6))
        sl = region(c, x - 6, y - 6, x + 6, y + 6)
        X, Y = c.X[sl], c.Y[sl]
        D2 = (X - x) ** 2 + (Y - y) ** 2
        a = np.exp(-D2 / (2 * (r * 0.6) ** 2)) * b + np.exp(-D2 / (2 * (r * 1.8) ** 2)) * b * 0.25
        c.P[sl] += tint * a[..., None]


def bubbles(g, spots, opacity=0.9):
    from ui import draw_bubble
    for x, y, r in spots:
        L = SLayer(g, x - r * 2, y - r * 2, r * 4, r * 4)
        draw_bubble(L, x, y, r, 1.0)
        L.commit(opacity)


# ----------------------------------------------------------------------------
# Ocean band
# ----------------------------------------------------------------------------

def ocean(c, sea, sky_img, gx, glint, night=False, refl=0.45, refl_fade=240,
          glit_w=60, glit_k=0.55, seed=31, streaks=500, streak_col=None):
    Y, X = c.Y[HZ:], c.X[HZ:]
    t = clamp01((Y - HZ) / (H - HZ))
    col = gradient_map(t ** 0.7, sea)
    depth = 1.0 / ((Y - HZ) + 10)
    small = value_noise(256, 1024, 18, seed=seed, octaves=4)
    tex = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((4096, 1024), Image.BICUBIC), float) / 255
    v = (depth * 7000).astype(int) % 1024
    u = ((X - W / 2) * (0.55 + depth * 22) + 2048).astype(int) % 4096
    tv = tex[v, u]
    waves = smoothstep(0.52, 0.72, tv)
    troughs = smoothstep(0.46, 0.26, tv)
    col = mix(col, clamp01(col * 1.12 + 0.05), (waves * 0.45)[..., None])
    col = mix(col, col * 0.84, (troughs * 0.3)[..., None])
    # reflections of the sky (flipped, rippled, vertically smeared)
    sky = np.asarray(sky_img, float)[:HZ, :, :3] / 255.0
    nrow = H - HZ
    refl_img = sky[::-1][:nrow].copy()
    sm = refl_img.copy()
    for k in (1, 2, 3, 4):
        sm[k:] += refl_img[:-k]
    refl_img = sm / 5
    rows = np.arange(nrow)
    for i in range(nrow):
        sh = int(np.sin(i * 0.5) * (1.5 + i * 0.03) + np.sin(i * 0.11 + 1) * (2 + i * 0.02))
        refl_img[i] = np.roll(refl_img[i], sh, axis=0)
    fade = np.exp(-rows / refl_fade)[:, None]
    a = fade * refl * (0.6 + 0.4 * (1 - troughs))
    tintm = np.array([0.82, 0.98, 1.0]) if not night else np.array([0.85, 0.9, 1.05])
    col = mix(col, refl_img * tintm, a[..., None])
    # glitter path under the light source
    path = np.exp(-((X - gx) / (glit_w + (Y - HZ) * glit_k)) ** 2)
    glit = smoothstep(0.6, 0.76, tv) * path
    col = col + glint * (glit * (0.75 if not night else 0.95))[..., None]
    col = col + glint * (path * np.exp(-(Y - HZ) / 140) * 0.18)[..., None]
    # bright haze line right at the horizon
    col = col + (np.exp(-((Y - HZ) / 3.5) ** 2) * 0.35)[..., None] * (sea[0][1] if True else 1)
    c.P[HZ:] = col
    c.A[HZ:] = 1.0
    # horizontal sparkle streaks
    rng = np.random.default_rng(seed + 5)
    sc = glint if streak_col is None else streak_col
    for _ in range(streaks):
        y = HZ + 3 + rng.uniform(0, 1) ** 1.6 * (H - HZ - 40)
        k = (y - HZ) / (H - HZ)
        if rng.random() < 0.5:
            x = gx + rng.normal(0, glit_w * 1.2 + (y - HZ) * glit_k * 0.8)
            amp = rng.uniform(0.4, 1.0)
        else:
            x = rng.uniform(0, W)
            amp = rng.uniform(0.15, 0.5)
        rx = (6 + 50 * k) * rng.uniform(0.5, 1.6)
        ry = 0.6 + 1.6 * k
        blob_add(c, x, y, rx, ry, sc, amp)


# ----------------------------------------------------------------------------
# 1. Blue Lagoon
# ----------------------------------------------------------------------------

def lagoon():
    t0 = time.time()
    pal = US.P(False)
    sky = [(0.0, rgb('#1e7fe0')), (0.32, rgb('#3398ee')), (0.62, rgb('#72c2f6')),
           (0.84, rgb('#bfe9fb')), (1.0, rgb('#f0fdff'))]
    sea = [(0.0, rgb('#e8fdff')), (0.02, rgb('#9ff0f2')), (0.12, rgb('#3fd2e4')),
           (0.45, rgb('#0fb4da')), (1.0, rgb('#00a3d1'))]
    prof = profile(sky, sea, 1.1)
    c = new_canvas()
    c.P[:] = prof[:, None, :]
    c.A[:] = 1
    haze = rgb('#dff5ff')
    SX, SY = 720, 230
    # soft warm wash around the sun
    rows = slice(0, HZ)
    D = np.hypot(c.X[rows] - SX, (c.Y[rows] - SY) * 1.2)
    c.P[rows] += (np.exp(-(D / 1100) ** 2) * 0.07)[..., None] * np.array([1.0, 1.0, 0.9])
    rainbow(c, 2700, 1420, 1240, 78, 0.30)

    # high wisps
    for i, (x, y, w) in enumerate([(1500, 150, 900), (2700, 110, 700), (3500, 260, 600), (500, 520, 500), (2200, 420, 500)]):
        wisp(c, x, y, w, 30, WHITE, 40 + i, 0.45)

    # big cumulus
    g = Group(c)
    cl_hi, cl_lo, cl_rim = rgb('#ffffff'), rgb('#9ec4ee'), rgb('#ffffff')
    bnc = rgb('#d4fbff')
    cloud(g, 3480, 820, 1050, 380, cl_hi, cl_lo, cl_rim, 11, bounce=bnc)
    cloud(g, 3860, 900, 520, 200, cl_hi, cl_lo, cl_rim, 12, bounce=bnc)
    cloud(g, 1050, 900, 1000, 360, cl_hi, cl_lo, cl_rim, 13, bounce=bnc)
    cloud(g, 520, 960, 520, 190, cl_hi, cl_lo, cl_rim, 14, bounce=bnc)
    cloud(g, 2280, 470, 520, 150, cl_hi, cl_lo, cl_rim, 15, bounce=bnc, haze_col=haze, haze=0.1)
    cloud(g, 1720, 640, 300, 100, cl_hi, cl_lo, cl_rim, 16, haze_col=haze, haze=0.2)
    merge(c, g)

    # horizon cloud bank
    g = Group(c)
    rng = np.random.default_rng(5)
    x = -100
    k = 0
    while x < W + 100:
        w = rng.uniform(380, 640)
        cloud(g, x + w / 2, HZ - 2, w, rng.uniform(90, 170), cl_hi, cl_lo, cl_rim, 100 + k, ao=0.15)
        x += w * 0.68
        k += 1
    merge(c, g, haze, 0.55, 0.9)

    # wind-turbine island (far left)
    g = Group(c)
    hills_island(g, pal, 540, 1380, 150, 3)
    for i, (tx, th, ta) in enumerate([(640, 170, 0.3), (790, 210, 1.2), (950, 240, 2.0), (1110, 200, 0.8), (1260, 160, 1.7)]):
        base = HZ - 50 - 50 * (1 - ((tx - 960) / 420) ** 2)
        turbine(g, tx, base + 10, th, ta, rgb('#ffffff'), rgb('#8fa6c8'))
    merge(c, g, haze, 0.38)

    # distant gleaming skyline
    g = Group(c)
    srng = np.random.default_rng(21)
    x = 1900
    while x < 3000:
        w = srng.uniform(10, 20)
        h = srng.uniform(50, 150) * (1 - abs((x - 2450) / 600) * 0.6)
        US.tower(g, x, HZ, w, h, pal, srng.choice(['glass', 'white', 'white']), 0.5, False, srng)
        x += w * 2 + srng.uniform(4, 16)
    specs = [(2060, 16, 120, 'white'), (2140, 22, 200, 'glass'), (2230, 60, 70, 'dome'),
             (2330, 18, 170, 'white'), (2640, 24, 240, 'glass'), (2700, 14, 160, 'spire'),
             (2770, 55, 75, 'dome'), (2860, 18, 130, 'glass'), (2930, 14, 90, 'white')]
    for sx, sw, sh, sk in specs:
        US.tower(g, sx, HZ + 2, sw, sh, pal, sk, 0.2, False, srng)
    needle(g, 2480, HZ + 2, 540, 21, pal, [(0.62, 2.6, 2.4), (0.72, 2.1, 2.0), (0.82, 1.5, 1.6)])
    arch(g, 2540, 2760, HZ + 2, 130, 5, pal)
    arch(g, 2150, 2330, HZ + 2, 95, 4, pal)
    for (dx, dr) in [(2400, 46), (2560, 34)]:
        geo_dome(g, dx, HZ + 2, dr, pal, seed=dx, cells=5)
    merge(c, g, haze, 0.2)

    # palm islet (right)
    g = Group(c)
    L = SLayer(g, 3150, HZ - 60, 520, 70)
    sd = op_inter(sd_ellipse(L, 3400, HZ + 2, 220, 24), L.Y - HZ - 2)
    L.over(rgb('#fbf3dc'), L.cover(sd))
    gd = op_inter(sd_ellipse(L, 3410, HZ + 4, 170, 34), L.Y - HZ + 6)
    L.over(gradient_map(clamp01((L.Y - HZ + 40) / 40), pal['grass']), L.cover(gd))
    L.commit()
    for (px, ph, pl, sd_) in [(3300, 120, -30, 31), (3360, 160, 20, 32), (3450, 140, 40, 33), (3520, 100, -20, 34)]:
        US.palm(g, px, HZ - 20, ph, pl, pal, scale=0.32, seed=sd_)
    merge(c, g, haze, 0.42)

    # floating islands
    g = Group(c)
    sky_fall(g, 2930, 600, 420, 15, seed=3)
    sky_island(g, pal, 3120, 560, 230, seed=4)
    US.palm(g, 3190, 562, 200, 40, pal, scale=0.72, seed=11)
    US.palm(g, 3040, 566, 150, -50, pal, scale=0.58, seed=12)
    US.bush(g, 3280, 566, 34, pal, 5, flowers=4)
    US.bush(g, 2990, 572, 26, pal, 6, flowers=2)
    merge(c, g)
    g = Group(c)
    sky_fall(g, 1475, 475, 260, 9, seed=5)
    sky_island(g, pal, 1560, 450, 135, seed=7, vines=6)
    US.palm(g, 1590, 452, 120, 30, pal, scale=0.45, seed=21)
    US.bush(g, 1500, 456, 22, pal, 8, flowers=2)
    merge(c, g, haze, 0.12)
    g = Group(c)
    sky_fall(g, 3720, 290, 160, 6, seed=9)
    sky_island(g, pal, 3780, 275, 80, seed=9, vines=5)
    US.bush(g, 3790, 278, 20, pal, 9, flowers=2)
    for (x, y, r) in [(2830, 700, 16), (3400, 470, 11), (1760, 560, 10), (3600, 380, 8)]:
        US.mini_rock(g, x, y, r, pal)
    merge(c, g, haze, 0.18)

    lens_flare(c, SX, SY, 1.0)
    sky_img = Image.fromarray((clamp01(c.P) * 255).astype(np.uint8)).convert('RGBA')
    ocean(c, sea, sky_img, SX + 150, rgb('#ffffff'), refl=0.42, glit_w=70, glit_k=0.7)

    # dolphins in the far water
    g = Group(c)
    dolphin(g, 1880, HZ + 46, 70)
    dolphin(g, 1990, HZ + 60, 56)
    for (dx, dy, rr) in [(1880, HZ + 46, 20), (1960, HZ + 47, 14), (1990, HZ + 60, 16), (2045, HZ + 61, 10)]:
        L = SLayer(g, dx - rr * 2, dy - rr, rr * 4, rr * 2)
        L.over(WHITE, L.cover(np.abs(sd_ellipse(L, dx, dy, rr, rr * 0.22)) - 1.0) * 0.7)
        L.commit()
    merge(c, g)

    # bubbles
    g = Group(c)
    bubbles(g, [(2050, 760, 28), (2120, 690, 14), (2010, 640, 9), (3700, 980, 34), (3640, 900, 15),
                (1290, 780, 20), (1240, 700, 10), (2650, 860, 12), (420, 700, 16), (3900, 640, 12),
                (2900, 240, 14), (1880, 300, 10)])
    merge(c, g)
    p = finalize(c, prof, 'backdrop_lagoon', 1)
    print('lagoon', round(time.time() - t0, 1), 's ->', p)


# ----------------------------------------------------------------------------
# 2. Glass City
# ----------------------------------------------------------------------------

def city():
    t0 = time.time()
    pal = dict(US.P(False))
    pal['ceramic_lo'] = rgb('#a7b8d4')
    sky = [(0.0, rgb('#2f88e4')), (0.34, rgb('#5aaef0')), (0.66, rgb('#b6dcf4')),
           (0.88, rgb('#fbeed6')), (1.0, rgb('#fff8ea'))]
    sea = [(0.0, rgb('#fff6e4')), (0.02, rgb('#b6f0ea')), (0.12, rgb('#44d0e0')),
           (0.45, rgb('#10b2d8')), (1.0, rgb('#00a3d1'))]
    prof = profile(sky, sea, 1.1)
    c = new_canvas()
    c.P[:] = prof[:, None, :]
    c.A[:] = 1
    haze = rgb('#eef0ea')
    SX, SY = 640, 300
    rows = slice(0, HZ)
    D = np.hypot(c.X[rows] - SX, (c.Y[rows] - SY) * 1.3)
    c.P[rows] += (np.exp(-(D / 1500) ** 2) * 0.14)[..., None] * np.array([1.0, 0.92, 0.7])

    for i, (x, y, w) in enumerate([(1200, 120, 900), (2900, 180, 1000), (3700, 90, 600), (2000, 300, 500)]):
        wisp(c, x, y, w, 32, rgb('#fffaf0'), 60 + i, 0.45)

    g = Group(c)
    cl_hi, cl_lo, cl_rim = rgb('#fffdf8'), rgb('#a9c4e6'), rgb('#fff1c8')
    cloud(g, 520, 700, 820, 320, cl_hi, cl_lo, cl_rim, 21, bounce=rgb('#ffe9c4'))
    cloud(g, 3600, 640, 1000, 340, cl_hi, cl_lo, cl_rim, 22, bounce=rgb('#ffe9c4'))
    cloud(g, 1500, 360, 420, 120, cl_hi, cl_lo, cl_rim, 23, haze_col=haze, haze=0.1)
    cloud(g, 2700, 300, 360, 100, cl_hi, cl_lo, cl_rim, 24, haze_col=haze, haze=0.15)
    merge(c, g)
    g = Group(c)
    rng = np.random.default_rng(6)
    x, k = -100, 0
    while x < W + 100:
        w = rng.uniform(380, 640)
        cloud(g, x + w / 2, HZ - 2, w, rng.uniform(150, 280), cl_hi, cl_lo, cl_rim, 200 + k, ao=0.15)
        x += w * 0.66
        k += 1
    merge(c, g, haze, 0.45, 0.95)

    # far skyline row
    g = Group(c)
    srng = np.random.default_rng(31)
    x = 420
    while x < 3700:
        w = srng.uniform(12, 26)
        h = srng.uniform(80, 260) * (1 - abs((x - 2048) / 1900) * 0.55)
        US.tower(g, x, HZ, w, h, pal, srng.choice(['glass', 'white', 'white']), 0.25, False, srng)
        x += w * 2 + srng.uniform(6, 30)
    merge(c, g, haze, 0.55)

    # mid row
    g = Group(c)
    mids = [(700, 28, 300, 'white'), (820, 34, 420, 'glass'), (960, 30, 260, 'pod'),
            (1240, 40, 480, 'glass'), (1360, 30, 360, 'white'), (2760, 36, 470, 'glass'),
            (2890, 30, 340, 'disc'), (3020, 44, 520, 'glass'), (3170, 30, 300, 'white'),
            (3330, 36, 400, 'glass'), (3480, 28, 260, 'pod'), (580, 24, 220, 'glass')]
    for i, (bx, bw, bh, bk) in enumerate(mids):
        building(g, bx, HZ + 2, bw, bh, bk, pal, seed=i)
    bridge(g, 820, 1240, HZ - 260, 40, 5, pal)
    bridge(g, 2760, 3020, HZ - 300, 30, 5, pal)
    merge(c, g, haze, 0.32)

    # hero row
    g = Group(c)
    arch(g, 2280, 2760, HZ + 2, 380, 16, pal)
    arch(g, 1340, 1800, HZ + 2, 300, 13, pal)
    heroes = [(1560, 56, 640, 'glass'), (1700, 40, 470, 'white'), (2420, 60, 700, 'glass'),
              (2570, 44, 520, 'disc'), (1100, 46, 560, 'glass'), (3220, 48, 600, 'glass'),
              (2900, 38, 420, 'white')]
    for i, (bx, bw, bh, bk) in enumerate(heroes):
        building(g, bx, HZ + 2, bw, bh, bk, pal, seed=20 + i)
    needle(g, 2048, HZ + 2, 900, 46, pal, [(0.58, 3.0, 5.0), (0.68, 2.5, 4.4), (0.78, 2.0, 3.8), (0.88, 1.4, 3.0)])
    bridge(g, 1560, 2048, HZ - 420, 60, 7, pal)
    bridge(g, 2048, 2420, HZ - 460, 50, 7, pal)
    mono = [(x, HZ - 150 - 40 * math.sin((x - 300) / 700)) for x in np.linspace(300, 3800, 70)]
    monorail(g, mono, 7, pal, train_t=(0.28, 0.7))
    merge(c, g, haze, 0.1)

    # waterfront: domes, greenery, promenade
    g = Group(c)
    L = SLayer(g, 300, HZ - 40, 3500, 50)
    prom = op_inter(sd_box(L, 2048, HZ - 6, 1720, 14, 10), L.Y - HZ - 3)
    pc = gradient_map(clamp01((L.Y - (HZ - 20)) / 22), [(0, rgb('#ffffff')), (1, rgb('#b6c6de'))])
    L.over(pc, L.cover(prom))
    gl = op_inter(prom, np.abs(L.Y - (HZ - 12)) - 1.5)
    L.over(rgb('#aaffff'), L.cover(gl))
    L.glow(gl, GLOW, 5, 0.4)
    L.commit()
    brng = np.random.default_rng(8)
    for x in np.arange(380, 3740, 70):
        if 1840 < x < 2260:
            continue
        US.bush(g, x + brng.uniform(-20, 20), HZ - 14, brng.uniform(22, 34), pal, int(x), flowers=brng.integers(0, 3))
    for (dx, dr, s_) in [(900, 150, 1), (1110, 110, 2), (760, 90, 3), (2850, 170, 4), (3080, 120, 5), (3270, 80, 6), (2650, 70, 7)]:
        geo_dome(g, dx, HZ - 12, dr, pal, seed=s_, cells=6 if dr > 100 else 5)
    for (px, ph, pl, sd_) in [(1300, 150, 20, 41), (1420, 120, -25, 42), (2280, 140, 30, 43), (3420, 160, -30, 44), (3560, 120, 20, 45), (600, 130, 25, 46)]:
        US.palm(g, px, HZ - 16, ph, pl, pal, scale=0.42, seed=sd_)
    merge(c, g, haze, 0.06)

    lens_flare(c, SX, SY, 0.6, tint=rgb('#fff0cc'))
    sky_img = Image.fromarray((clamp01(c.P) * 255).astype(np.uint8)).convert('RGBA')
    ocean(c, sea, sky_img, SX + 200, rgb('#fff6dc'), refl=0.6, refl_fade=320, glit_w=90, glit_k=0.8)
    g = Group(c)
    bubbles(g, [(3800, 960, 26), (3740, 880, 12), (330, 900, 18), (2600, 1000, 14), (1500, 940, 10)])
    merge(c, g)
    p = finalize(c, prof, 'backdrop_city', 2)
    print('city', round(time.time() - t0, 1), 's ->', p)


# ----------------------------------------------------------------------------
# 3. Moonpool
# ----------------------------------------------------------------------------

def moon_disc(c, cx, cy, r):
    # halo
    rows = slice(0, HZ)
    D = np.hypot(c.X[rows] - cx, c.Y[rows] - cy) - r
    Dp = np.maximum(D, 0)
    halo = np.exp(-(Dp / (r * 0.12)) ** 2) * 0.32 + np.exp(-(Dp / (r * 0.6)) ** 2) * 0.32 + np.exp(-(Dp / (r * 1.8)) ** 2) * 0.16
    c.P[rows] += (rgb('#b9b4ff') * halo[..., None]) + rgb('#7fe8ff') * (np.exp(-(Dp / (r * 0.04)) ** 2) * 0.18)[..., None]
    L = SLayer(c, cx - r - 10, cy - r - 10, 2 * r + 20, 2 * r + 20)
    d = sd_circle(L, cx, cy, r)
    n = sphere_normals(L, cx, cy, r)
    nz = value_noise(L.w, L.h, 90, seed=12, octaves=5)
    fine = value_noise(L.w, L.h, 12, seed=13, octaves=3)
    base = gradient_map(nz, [(0, rgb('#cdcdf0')), (0.42, rgb('#e2e0f8')), (0.6, rgb('#f6f4ff')), (1, rgb('#ffffff'))])
    base = base * (0.94 + 0.08 * fine)[..., None]
    lam = clamp01(n[..., 0] * -0.35 + n[..., 1] * -0.3 + n[..., 2] * 0.88)
    col = base * (0.8 + 0.26 * lam)[..., None]
    # maria: big soft darker patches
    rng = np.random.default_rng(3)
    for _ in range(9):
        a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(0.1, 0.7) * r
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        cd = sd_circle(L, x, y, rng.uniform(0.1, 0.24) * r) + (nz - 0.5) * r * 0.15
        col = mix(col, col * np.array([0.82, 0.84, 0.96]), (L.cover(cd, r * 0.03) * 0.6)[..., None])
    # craters
    for _ in range(46):
        a = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.uniform(0, 1)) * r * 0.9
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        cr = r * (rng.uniform(0.015, 0.05) if rng.random() < 0.8 else rng.uniform(0.06, 0.11))
        # foreshorten towards the limb
        k = rr / r
        dx, dy = L.X - x, L.Y - y
        radial = np.array([math.cos(a), math.sin(a)])
        along = dx * radial[0] + dy * radial[1]
        perp = -dx * radial[1] + dy * radial[0]
        sq = math.sqrt(max(0.15, 1 - k * k))
        q = np.hypot(along / sq, perp) / cr
        bowl = clamp01(1.0 - q) ** 0.5 * (q < 1)
        # light from the upper left: shadow on the upper-left inner wall
        side = clamp01(-(dx * -0.7 + dy * -0.7) / cr)
        lit = clamp01((dx * -0.7 + dy * -0.7) / cr * -1)
        sh = (q < 1) * clamp01((dx * 0.7 + dy * 0.7) / cr * -1 + 0.2)
        col = col * (1 - (bowl * 0.06 + sh * 0.16 * clamp01(1 - q * 0.8)))[..., None]
        rim = np.exp(-((q - 1.0) / 0.12) ** 2) * clamp01((dx * 0.7 + dy * 0.7) / cr)
        col = col + (rim * 0.12)[..., None]
    fres = (1 - n[..., 2]) ** 2.5
    col = mix(col, rgb('#c8ecff'), (fres * 0.45)[..., None])
    L.over(clamp01(col), L.cover(d))
    L.over(WHITE, L.cover(np.abs(d + 2) - 2) * clamp01(-n[..., 0] - n[..., 1]) * 0.6)
    L.commit()


def aurora(c, x0, x1, ybase, amp, height, seed, alpha, ca, cb):
    sl = region(c, x0 - 100, 0, x1 + 100, ybase + amp + 200)
    X, Y = c.X[sl], c.Y[sl]
    xs = X[0]
    n1 = noise1d(len(xs) + 2, 260, seed, 2)[:len(xs)]
    yb = ybase + amp * (np.sin((xs - x0) / 520 + seed) * 0.7 + (n1 - 0.5) * 1.6)
    dy = yb[None, :] - Y               # >0 above the bottom edge
    # fine vertical rays, sheared a little
    rays = noise1d(len(xs) + 400, 9, seed + 1, 3)
    shift = (np.clip(dy, 0, None) * 0.25).astype(int)
    idx = np.clip(np.arange(len(xs))[None, :] + shift, 0, len(rays) - 1)
    rv = rays[idx]
    inten = np.where(dy > 0, np.exp(-dy / height) * (0.35 + 0.65 * np.exp(-dy / (height * 0.25))), np.exp(dy / 22)) * (0.35 + 1.2 * rv ** 2)
    inten *= smoothstep(x0 - 100, x0 + 400, X) * smoothstep(x1 + 100, x1 - 400, X)
    inten *= (0.15 + 1.4 * noise1d(len(xs), 160, seed + 2, 2) ** 2)[None, :]
    tcol = clamp01(dy / (height * 1.6))
    col = mix(rgb(ca), rgb(cb), tcol[..., None])
    c.P[sl] += col * (inten * alpha)[..., None]


def moon():
    t0 = time.time()
    pal = US.P(True)
    sky = [(0.0, rgb('#040823')), (0.3, rgb('#0c1550')), (0.6, rgb('#22287a')),
           (0.85, rgb('#463a9c')), (1.0, rgb('#7c62c4'))]
    sea = [(0.0, rgb('#a690e8')), (0.02, rgb('#5c52b4')), (0.15, rgb('#2a2c80')),
           (0.5, rgb('#171a5c')), (1.0, rgb('#0d0f42'))]
    prof = profile(sky, sea, 1.05)
    c = new_canvas()
    c.P[:] = prof[:, None, :]
    c.A[:] = 1
    haze = rgb('#5a4aa8')
    # milky way: a diagonal band of dust
    rows = slice(0, HZ)
    X, Y = c.X[rows], c.Y[rows]
    band = np.exp(-((Y - (980 - X * 0.22)) / 230) ** 2)
    nz = value_noise(W, HZ, 110, seed=7, octaves=5)
    nz2 = value_noise(W, HZ, 30, seed=8, octaves=3)
    dust = band * clamp01(nz * 1.6 - 0.35) ** 1.5
    lanes = smoothstep(0.55, 0.75, nz2) * band
    mwc = mix(rgb('#8a78e8'), rgb('#e08ad8'), nz2[..., None] * 0.6)
    c.P[rows] += mwc * (dust * 0.22)[..., None] + rgb('#7fe0ff') * (band * nz2 * 0.06)[..., None]
    c.P[rows] *= (1 - lanes * 0.18)[..., None]
    del X, Y, band, nz, nz2, dust, lanes, mwc
    star_field(c, 4200, 3, HZ - 30)
    # milky-way star cluster density
    rng = np.random.default_rng(4)
    for _ in range(2200):
        x = rng.uniform(0, W)
        y = 980 - x * 0.22 + rng.normal(0, 150)
        if 0 < y < HZ - 40:
            r = rng.uniform(0.4, 0.9)
            blob_add(c, x, y, r, r, rgb('#e8e4ff'), rng.uniform(0.3, 0.9))
    for _ in range(40):
        x, y = rng.uniform(150, W - 150), rng.uniform(0, 1) ** 1.3 * (HZ - 200)
        r = rng.uniform(8, 22)
        L = SLayer(c, x - r * 1.6, y - r * 1.6, r * 3.2, r * 3.2)
        sparkle(L, x, y, r, rng.uniform(0.5, 1.0), color=rgb('#e6f0ff'))
        L.commit_add()

    aurora(c, 150, 2300, 520, 110, 190, 1, 0.75, '#3dffc0', '#b05aff')
    aurora(c, 900, 3900, 330, 80, 140, 5, 0.45, '#5fe8ff', '#ff6ad0')
    MX, MY, MR = 2700, 560, 400
    moon_disc(c, MX, MY, MR)
    # small ringed planet
    g = Group(c)
    L = SLayer(g, 900, 120, 300, 200)
    pd = sd_circle(L, 1050, 220, 42)
    pn = sphere_normals(L, 1050, 220, 42)
    pc = gradient_map(clamp01(0.5 + 0.5 * pn[..., 1] + (pn[..., 0]) * 0.2), [(0, rgb('#ffd0f4')), (0.5, rgb('#b48cff')), (1, rgb('#3a2c8a'))])
    L.over(pc, L.cover(pd))
    dx, dy = L.X - 1050, L.Y - 220
    rot = math.radians(-18)
    ux = dx * math.cos(rot) + dy * math.sin(rot)
    uy = -dx * math.sin(rot) + dy * math.cos(rot)
    kk = np.hypot(ux / 95, uy / 18)
    front = ((uy > 0) | (np.hypot(dx, dy) > 42)).astype(float)
    L.over(rgb('#e8e0ff'), L.cover(np.abs(kk - 1) * 18 - 2.2) * front * 0.75)
    L.glow(pd, rgb('#c49cff'), 20, 0.35)
    L.commit()
    merge(c, g)

    # low violet clouds lit by the moon
    g = Group(c)
    chi, clo, crim = rgb('#4a4aa6'), rgb('#161a54'), rgb('#dfe2ff')
    cloud(g, 560, 1040, 700, 190, chi, clo, crim, 31, ao=0.2)
    cloud(g, 3720, 1030, 760, 200, chi, clo, crim, 32, ao=0.2)
    cloud(g, 1800, 930, 380, 90, chi, clo, crim, 33, ao=0.2)
    merge(c, g, haze, 0.25, 0.85)
    g = Group(c)
    rng = np.random.default_rng(7)
    x, k = -100, 0
    while x < W + 100:
        w = rng.uniform(380, 640)
        cloud(g, x + w / 2, HZ - 2, w, rng.uniform(70, 130), chi, clo, crim, 300 + k, ao=0.15)
        x += w * 0.7
        k += 1
    merge(c, g, haze, 0.45, 0.75)

    # crystal islet (left)
    g = Group(c)
    L = SLayer(g, 700, HZ - 120, 900, 130)
    dd = op_inter(op_smooth_union(sd_ellipse(L, 1150, HZ + 4, 380, 60), sd_ellipse(L, 1000, HZ + 4, 160, 95), 40), L.Y - HZ - 3)
    L.over(gradient_map(clamp01((L.Y - HZ + 95) / 95), [(0, rgb('#3a3c8e')), (1, rgb('#141850'))]), L.cover(dd))
    L.over(rgb('#7c84e0'), L.cover(np.abs(dd + 2) - 1.2) * smoothstep(HZ, HZ - 60, L.Y) * 0.6)
    L.commit()
    crng = np.random.default_rng(11)
    cr = [(1000, 380, 30, -0.05), (1060, 300, 24, 0.12), (930, 250, 22, -0.25), (1140, 220, 20, 0.22),
          (870, 160, 16, -0.4), (1230, 170, 16, 0.3), (1320, 120, 13, 0.1), (790, 110, 12, -0.2), (1420, 80, 11, 0.25)]
    for i, (x, h, w, tl) in enumerate(cr):
        cols = ('#e6ffff', '#3fc8f0', '#7ff8ff') if i % 3 else ('#ffe6ff', '#b05aff', '#e49cff')
        base = HZ - 50 + abs(x - 1050) * 0.12
        crystal(g, x, base, h, w, tl, cols[0], cols[1], cols[2], seed=i)
    merge(c, g, haze, 0.12)

    # dim glowing city (right)
    g = Group(c)
    srng = np.random.default_rng(41)
    x = 3080
    L = SLayer(g, 3000, HZ - 200, 900, 220)
    L.glow(sd_box(L, 3450, HZ, 400, 30, 30), rgb('#5fe0ff'), 70, 0.3)
    L.commit_add()
    while x < 3840:
        w = srng.uniform(10, 22)
        h = srng.uniform(60, 230) * (1 - abs((x - 3450) / 500) * 0.5)
        US.tower(g, x, HZ, w, h, pal, srng.choice(['glass', 'white', 'spire']), 0.35, True, srng)
        x += w * 2 + srng.uniform(4, 18)
    needle(g, 3460, HZ + 2, 380, 16, pal, [(0.62, 2.6, 2.0), (0.74, 2.0, 1.7)], night=True)
    geo_dome(g, 3300, HZ + 2, 44, pal, night=True, seed=3, cells=5)
    merge(c, g, haze, 0.3)

    # glowing jellyfish lanterns drifting in the far sky
    g = Group(c)
    for i, (x, y, r, col) in enumerate([(1500, 640, 34, '#7ff8ff'), (1660, 520, 22, '#ff9ae6'), (1830, 700, 16, '#c49cff'),
                                       (2050, 420, 26, '#7ff8ff'), (3350, 360, 30, '#ff9ae6'), (3550, 520, 20, '#7ff8ff'),
                                       (3760, 300, 16, '#c49cff'), (650, 420, 28, '#ff9ae6'), (480, 600, 18, '#7ff8ff'),
                                       (2250, 780, 14, '#ff9ae6'), (1300, 330, 14, '#c49cff'), (3150, 780, 18, '#7ff8ff')]):
        jelly(g, x, y, r, col, seed=i)
    merge(c, g)

    sky_img = Image.fromarray((clamp01(c.P) * 255).astype(np.uint8)).convert('RGBA')
    ocean(c, sea, sky_img, MX, rgb('#e8eeff'), night=True, refl=0.55, refl_fade=300,
          glit_w=170, glit_k=0.6, streaks=1300)
    # glowing plankton specks on the far water
    rng = np.random.default_rng(13)
    for _ in range(160):
        x = rng.uniform(0, W)
        y = HZ + 6 + rng.uniform(0, 1) ** 1.5 * 300
        blob_add(c, x, y, 1.6, 1.0, rgb('#7ff8ff') if rng.random() < 0.6 else rgb('#ff9ae6'), rng.uniform(0.3, 0.8))
    p = finalize(c, prof, 'backdrop_moon', 3)
    print('moon', round(time.time() - t0, 1), 's ->', p)


JOBS = {'lagoon': lagoon, 'city': city, 'moon': moon}


def run(name):
    JOBS[name]()


if __name__ == '__main__':
    names = sys.argv[1:] or list(JOBS)
    if len(names) == 1:
        run(names[0])
    else:
        from multiprocessing import Pool
        with Pool(len(names)) as p:
            p.map(run, names)
