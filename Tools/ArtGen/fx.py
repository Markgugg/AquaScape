"""
fx.py - effect sprites for AquaScape (bubbles, sparkles, rings, clouds, fish,
keycap prompt, stars).

Output: Assets/AquaScape/Art/FX/*.png  (all centered, transparent background)
Run:    python3 fx.py [name ...]
"""
import math
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from aqua import *
from artkit import ART, FONT, PREVIEW, WHITE, preview, check_padding, sparkle

OUT = os.path.join(ART, 'FX')


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def from_alpha(c, alpha, color=WHITE):
    """Set the whole canvas to `color` with coverage `alpha` (for glow sprites)."""
    a = clamp01(alpha)
    col = np.broadcast_to(np.asarray(color, float), c.P.shape) if np.ndim(color) == 1 else color
    c.P = col * a[..., None]
    c.A = a
    return c.image()


def np_image(col, alpha):
    """Final-resolution numpy RGB + alpha -> PIL RGBA."""
    out = np.dstack([clamp01(col), clamp01(alpha)])
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), 'RGBA')


def thin_film(t):
    """Iridescent soap-film palette (cyan / magenta / gold) for t in 0..1."""
    return gradient_map(t % 1.0, [
        (0.00, rgb('#5ff3ff')),
        (0.22, rgb('#8f9bff')),
        (0.40, rgb('#ff7fe0')),
        (0.58, rgb('#ffd9a0')),
        (0.74, rgb('#9dffcf')),
        (1.00, rgb('#5ff3ff')),
    ])


def star_alpha(c, x, y, r, thin=0.07, core=0.16, diag=0.0):
    """4-point star (plus optional thinner diagonal rays) as alpha field."""
    dx, dy = np.abs(c.X - x), np.abs(c.Y - y)
    a = np.exp(-(dx / (r * thin)) ** 2) * np.exp(-(dy / r) ** 2 * 3) + \
        np.exp(-(dy / (r * thin)) ** 2) * np.exp(-(dx / r) ** 2 * 3)
    if diag:
        u, v = (dx + dy) / math.sqrt(2), np.abs(dx - dy) / math.sqrt(2)
        a = a + diag * (np.exp(-(v / (r * thin * 0.7)) ** 2) * np.exp(-(u / (r * 0.55)) ** 2 * 3))
    d2 = (c.X - x) ** 2 + (c.Y - y) ** 2
    a = a + np.exp(-d2 / (2 * (r * core) ** 2))
    return a


# ----------------------------------------------------------------------------
# Bubbles
# ----------------------------------------------------------------------------

def draw_bubble(c, cx, cy, r, detail=True):
    rr = np.hypot(c.X - cx, c.Y - cy) / r
    ang = np.arctan2(c.Y - cy, c.X - cx)
    d = sd_circle(c, cx, cy, r)
    inside = c.cover(d)

    # faint cyan outer halo so it pops on white floors and turquoise water
    halo = np.exp(-np.maximum(d, 0) ** 2 / (2 * (r * 0.07) ** 2)) * (1 - inside)
    c.over(rgb('#5fd0ff'), halo * 0.35)

    # thin-film colour swirling with angle + radius
    t = ang / (2 * math.pi) + rr * 0.6 + 0.18 * np.sin(ang * 3 + rr * 5)
    film = thin_film(t)
    # interior: nearly clear with a faint aqua tint; film gets stronger
    # toward the rim (fresnel)
    fres = smoothstep(0.35, 1.0, rr) ** 1.8
    body_a = 0.07 + 0.62 * fres
    body_col = mix(rgb('#a6ecff'), film, smoothstep(0.3, 0.9, rr)[..., None])
    c.over(clamp01(body_col), inside * body_a)
    # soft darker cool tint on the lower inner side: reads on white
    lower = smoothstep(0.55, 1.0, rr) * clamp01((c.Y - cy) / r + 0.4)
    c.over(rgb('#3a8fe0'), inside * lower * 0.22)
    # saturated film band just inside the rim
    band = np.abs(d + r * 0.10) - r * 0.07
    c.over(clamp01(film * 1.08), c.cover(band, 2.0) * 0.6)
    # crisp blue-violet edge line for definition
    edge = np.abs(d + r * 0.03) - r * 0.03
    edge_col = mix(rgb('#2a7fd4'), rgb('#a35be6'), (0.5 + 0.5 * np.sin(ang + 1.2))[..., None])
    c.over(edge_col, c.cover(edge) * 0.6)
    if detail:
        # bounce light arc bottom-right
        highlight_arc(c, cx, cy, r * 0.8, r * 0.8, r * 0.045, 20, 90, 0.55, (0.8, 1.0, 1.0))
        # thin white rim line
        rim = np.abs(d + r * 0.015) - r * 0.012
        c.over(WHITE, c.cover(rim) * 0.55)
    # big curved white highlight top-left
    highlight_arc(c, cx, cy, r * 0.75, r * 0.75, r * 0.085, 192, 268, 1.0)
    # soft window reflection
    hl = op_inter(sd_ellipse(c, cx - r * 0.30, cy - r * 0.42, r * 0.28, r * 0.15), d + 1)
    c.over(WHITE, c.cover(hl, 2.5) * 0.5)
    # small specular dots
    c.over(WHITE, c.cover(sd_circle(c, cx - r * 0.72, cy - r * 0.08, r * 0.05)) * 0.9)
    c.over(WHITE, c.cover(sd_circle(c, cx + r * 0.52, cy + r * 0.40, r * 0.065)) * 0.85)


def bubble():
    S = 80
    c = Canvas(S, S, ss=4)
    draw_bubble(c, 40, 40, 31)
    # sparkle on the rim (top right)
    sa = star_alpha(c, 59, 19, 10, thin=0.09, core=0.13)
    c.over(WHITE, clamp01(sa) * 0.95)
    return c.image()


def bubble_small():
    S = 24
    c = Canvas(S, S, ss=6)
    draw_bubble(c, 12, 12, 9.0, detail=False)
    return c.image()


# ----------------------------------------------------------------------------
# Glow particles
# ----------------------------------------------------------------------------

def soft_dot():
    c = Canvas(64, 64, ss=2)
    r = np.hypot(c.X - 32, c.Y - 32) / 30
    a = np.exp(-(r ** 2) * 3.2) * (1 - smoothstep(0.85, 1.0, r))
    return from_alpha(c, a)


def sparkle_img():
    c = Canvas(64, 64, ss=3)
    r = np.hypot(c.X - 32, c.Y - 32)
    a = star_alpha(c, 32, 32, 26, thin=0.06, core=0.09)
    a = a + np.exp(-(r / 13) ** 2) * 0.35       # soft glow
    a = a * (1 - smoothstep(26, 31, r) * 0.0)
    return from_alpha(c, a)


def glint():
    c = Canvas(48, 48, ss=3)
    r = np.hypot(c.X - 24, c.Y - 24)
    a = star_alpha(c, 24, 24, 20, thin=0.045, core=0.07, diag=0.45)
    a = a + np.exp(-(r / 7) ** 2) * 0.45
    # tiny lens ring
    a = a + np.exp(-((r - 9) / 0.9) ** 2) * 0.12
    return from_alpha(c, a)


def ring():
    S = 256
    c = Canvas(S, S, ss=2)
    r = np.hypot(c.X - 128, c.Y - 128)
    R = 112
    core = np.exp(-((r - R) / 2.2) ** 2)
    glow = np.exp(-((r - R) / 7.0) ** 2) * 0.45
    inner = np.exp(-np.maximum(R - r, 0) / 18.0) * (r < R) * 0.18   # soft inner wash
    return from_alpha(c, core + glow + inner)


def dash_streak():
    W, H = 128, 32
    c = Canvas(W, H, ss=3)
    # head at the right, tapering tail to the left
    t = clamp01((c.X - 6) / 112)                      # 0 tail .. 1 head
    half = 1.5 + 9.0 * t ** 0.7 * (1 - smoothstep(0.9, 1.0, t) * 0.6)
    dy = np.abs(c.Y - 16)
    a = np.exp(-(dy / np.maximum(half, 0.5)) ** 2 * 1.6)
    a = a * smoothstep(0.0, 0.55, t) * (1 - smoothstep(0.96, 1.0, t))
    core = np.exp(-(dy / np.maximum(half * 0.3, 0.3)) ** 2) * smoothstep(0.3, 0.9, t) * 0.5
    a = a * 0.85 + core * (1 - smoothstep(0.96, 1.0, t))
    return from_alpha(c, a)


def star_small():
    c = Canvas(24, 24, ss=4)
    r = np.hypot(c.X - 12, c.Y - 12)
    a = star_alpha(c, 12, 12, 9.0, thin=0.09, core=0.14)
    a = a + np.exp(-(r / 4.0) ** 2) * 0.4
    col = mix(rgb('#dff6ff'), WHITE, clamp01(1 - r / 4)[..., None])
    return from_alpha(c, a, col)


# ----------------------------------------------------------------------------
# Clouds (density field -> blur -> shaded puffs)
# ----------------------------------------------------------------------------

def blob_field(w, h, blobs):
    """Sum of soft round puffs rendered with PIL, as float array."""
    im = Image.new('F', (w, h), 0.0)
    acc = np.zeros((h, w))
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    for (x, y, r, k) in blobs:
        x0, x1 = int(max(0, x - r * 1.6)), int(min(w, x + r * 1.6))
        y0, y1 = int(max(0, y - r * 1.6)), int(min(h, y + r * 1.6))
        sx, sy = xx[y0:y1, x0:x1], yy[y0:y1, x0:x1]
        d2 = ((sx - x) ** 2 + (sy - y) ** 2) / (r * r)
        acc[y0:y1, x0:x1] = np.maximum(acc[y0:y1, x0:x1], k * clamp01(1 - d2) ** 0.5)
    return acc


def pil_blur(a, sigma):
    """Gaussian blur (sigma px) via FFT with edge padding (no scipy)."""
    pad = int(sigma * 3) + 2
    b = np.pad(a, pad, mode='edge')
    h, w = b.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-2 * (math.pi ** 2) * (sigma ** 2) * (fx ** 2 + fy ** 2))
    out = np.real(np.fft.ifft2(np.fft.fft2(b) * g))
    return out[pad:-pad, pad:-pad]


def cloud(seed, W, H, n_main, spread):
    """Painterly cumulus: shaded spherical puffs layered back (top) to front
    (bottom), each front puff overlapping the shaded underside of the one
    behind it; wispy, noise-eroded edges."""
    rng = np.random.default_rng(seed)
    cx, cy = W / 2, H * 0.55
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    puffs = []
    for i in range(n_main * 3):
        a = rng.uniform(0, 2 * math.pi)
        rad = rng.uniform(0, 1) ** 0.7
        x = cx + math.cos(a) * rad * spread[0]
        y = cy + math.sin(a) * rad * spread[1] * 0.9
        # big puffs in the middle, small ones toward the rim
        r = H * rng.uniform(0.7, 1.15) * (0.25 - 0.16 * rad)
        puffs.append((y, x, r))
    # a few big domes give the cumulus its silhouette
    for i in range(4):
        x = cx + rng.uniform(-0.55, 0.55) * spread[0]
        y = cy - spread[1] * rng.uniform(0.15, 0.45)
        puffs.append((y, x, H * rng.uniform(0.24, 0.3)))
    # a flat-ish base row so the underside reads as a cloud bottom
    for i in range(n_main):
        x = cx + (i / (n_main - 1) - 0.5) * 1.75 * spread[0]
        edge = abs(i / (n_main - 1) - 0.5) * 2
        r = H * rng.uniform(0.11, 0.16) * (1 - edge * 0.5)
        y = cy + spread[1] * 0.55 * (1 - edge ** 2 * 0.8)
        puffs.append((y, x, r))
    puffs.sort()
    L = np.array([-0.5, -0.75, 0.45]); L /= np.linalg.norm(L)
    col = np.zeros((H, W, 3))
    alpha = np.zeros((H, W))
    nz_edge = value_noise(W, H, 22, seed=seed + 3, octaves=3)
    for (y, x, r) in puffs:
        x0, x1 = int(max(0, x - r - 4)), int(min(W, x + r + 4))
        y0, y1 = int(max(0, y - r - 4)), int(min(H, y + r + 4))
        X, Y = xx[y0:y1, x0:x1], yy[y0:y1, x0:x1]
        dx, dy = (X - x) / r, (Y - y) / r
        rr = np.hypot(dx, dy)
        dz = np.sqrt(clamp01(1 - rr * rr))
        lam = clamp01(dx * L[0] + dy * L[1] + dz * L[2])
        # vertical ambient: lower part of the whole cloud is bluer
        v = clamp01((Y - (cy - spread[1])) / (2 * spread[1]))
        t = clamp01(lam * 0.8 + 0.34 - v * 0.30)
        pc = gradient_map(t, [
            (0.00, rgb('#9fb6d8')),
            (0.30, rgb('#c3d4ec')),
            (0.55, rgb('#e6f0fa')),
            (0.78, rgb('#ffffff')),
            (1.00, rgb('#ffffff')),
        ])
        # translucent silver lining on the lit rim
        lining = smoothstep(0.75, 0.98, rr) * clamp01(-(dx + dy) * 0.8)
        pc = mix(pc, np.array([1, 1, 1.0]), (lining * 0.6)[..., None])
        # soft edge, eroded by noise for a fluffy rim
        er = (nz_edge[y0:y1, x0:x1] - 0.5) * 0.22
        pa = smoothstep(1.0 + er, 0.8 + er, rr)
        ca = alpha[y0:y1, x0:x1]
        col[y0:y1, x0:x1] = pc * pa[..., None] + col[y0:y1, x0:x1] * (1 - pa[..., None])
        alpha[y0:y1, x0:x1] = pa + ca * (1 - pa)
    # gentle overall softening + wispy outer edge
    col = np.dstack([pil_blur(col[..., k], 1.4) for k in range(3)])
    alpha = pil_blur(alpha, 1.4)
    # col is premultiplied (puffs composited 'over'): un-premultiply
    colu = np.where(alpha[..., None] > 1e-3, col / np.maximum(alpha, 1e-3)[..., None], 1.0)
    wisp = value_noise(W, H, 40, seed=seed + 11, octaves=4)
    alpha = clamp01(alpha * 1.12 - (1 - alpha) * 0.35 * wisp)
    m = 6
    edge = np.ones_like(alpha)
    edge[:m] = edge[-m:] = 0
    edge[:, :m] = edge[:, -m:] = 0
    alpha = alpha * pil_blur(edge, 3)
    return np_image(colu, alpha)


def cloud_1():
    return cloud(3, 820, 440, 16, (300, 130))


def cloud_2():
    return cloud(17, 640, 380, 12, (230, 110))


def cloud_3():
    return cloud(29, 900, 420, 20, (360, 115))


def cloud_shadow():
    """Very soft dark blob: sum of wide gaussians, gently noise-modulated."""
    S = 512
    rng = np.random.default_rng(41)
    yy, xx = np.mgrid[0:S, 0:S].astype(float)
    dens = np.zeros((S, S))
    for i in range(12):
        a = rng.uniform(0, 2 * math.pi)
        rad = rng.uniform(0, 1) ** 0.7
        x, y = 256 + math.cos(a) * rad * 140, 258 + math.sin(a) * rad * 85
        sg = rng.uniform(58, 78)
        dens += np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sg * sg))
    dens *= 0.85 + 0.3 * value_noise(S, S, 90, seed=4, octaves=3)
    a = smoothstep(0.04, 0.9, dens / dens.max()) ** 1.15
    edge = np.ones_like(a)
    edge[:16] = edge[-16:] = 0
    edge[:, :16] = edge[:, -16:] = 0
    a = a * pil_blur(edge, 10) * 0.6
    col = np.broadcast_to(np.array([0.02, 0.16, 0.28]), (S, S, 3))
    return np_image(col, a)


# ----------------------------------------------------------------------------
# Fish silhouettes (top view, pointing right)
# ----------------------------------------------------------------------------

def sd_rot_ellipse(c, cx, cy, rx, ry, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    x, y = c.X - cx, c.Y - cy
    u, v = x * ca + y * sa, -x * sa + y * ca
    k = np.hypot(u / rx, v / ry)
    return (k - 1.0) * min(rx, ry)


def fish(kind):
    """Top-down fish silhouette pointing right (soft, dark teal)."""
    from artkit import spine
    W, H = 100, 48
    c = Canvas(W, H, ss=3)
    cy = 24
    if kind == 1:   # plump reef fish / koi
        x0, x1, wmax, bend = 24, 95, 12.0, 1.5
        fin = (68, 11, 8, 3.4, 0.75)
        tail = [(28, cy), (10, cy - 13), (6, cy - 10), (13, cy), (6, cy + 10), (10, cy + 13)]
    else:           # slender darting fish with a long forked tail
        x0, x1, wmax, bend = 24, 94, 7.5, 2.0
        fin = (70, 7.5, 7, 2.4, 0.8)
        tail = [(27, cy), (6, cy - 13), (3, cy - 11), (15, cy), (3, cy + 11), (6, cy + 13)]
    pts = [(x0 + (x1 - x0) * t, cy + bend * math.sin(t * math.pi * 1.2 - 0.4) * (1 - t))
           for t in np.linspace(0, 1, 16)]
    dist, t, _ = spine(c, pts)
    pk = 0.62
    prof = (t ** 0.9) * ((1 - t) ** 0.55) / (pk ** 0.9 * (1 - pk) ** 0.55)
    w = wmax * prof + 1.2
    body = dist - w
    shape = op_smooth_union(body, sd_poly(c, tail), 3)
    fx_, fy, frx, fry, fa = fin
    for sgn in (-1, 1):
        f = sd_rot_ellipse(c, fx_ - 5, cy + sgn * (fy + 1), frx, fry, -sgn * fa)
        shape = op_smooth_union(shape, f, 2)
    a = c.cover(shape, soft=2.5)
    # darker along the spine, lighter fins/edges
    col = mix(rgb('#127083'), rgb('#053445'),
              (1 - smoothstep(0, wmax * 0.9, dist))[..., None] * (body < 0)[..., None])
    c.over(col, a * 0.9)
    return c.image().filter(ImageFilter.GaussianBlur(1.1))


# ----------------------------------------------------------------------------
# "SPACE" keycap prompt
# ----------------------------------------------------------------------------

def text_mask(c, text, size, cx, cy):
    """Render text with PIL at super-sampled resolution -> alpha field."""
    ss = c.ss
    font = ImageFont.truetype(FONT, int(size * ss))
    H, W = c.A.shape
    im = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(im)
    bb = dr.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    dr.text((cx * ss - tw / 2 - bb[0], cy * ss - th / 2 - bb[1]), text, font=font, fill=255)
    return np.asarray(im, dtype=float) / 255.0


def prompt_space():
    W, H = 124, 56
    c = Canvas(W, H, ss=3)
    cx = W / 2
    # drop shadow
    c.shadow(sd_box(c, cx, 30, 56, 19, 14), 6, 0.30, (0.02, 0.18, 0.30))
    # key base (front skirt) - darker aqua glass
    base = sd_box(c, cx, 28, 57, 21, 15)
    t = clamp01((c.Y - 8) / 40)
    col = gradient_map(t, [(0, rgb('#bdf4ff')), (0.6, rgb('#38c8f0')), (1, rgb('#1680cc'))])
    c.over(col, c.cover(base))
    # key top face: white -> pale aqua glossy
    top = sd_box(c, cx, 24, 52, 16, 12)
    n = normals(c, height_bevel(top, 6))
    tc = gradient_map(clamp01((c.Y - 8) / 32), [(0, rgb('#ffffff')), (0.55, rgb('#eefbff')),
                                                  (1, rgb('#a8ecff'))])
    lam = lambert(n)
    tc = tc * (0.9 + 0.12 * lam)[..., None] + spec(n, 40)[..., None] * 0.4
    c.over(clamp01(tc), c.cover(top))
    # glossy top-half highlight
    gl = op_inter(sd_box(c, cx, 15, 48, 6, 6), top + 2)
    c.over(WHITE, c.cover(gl, 2) * 0.7)
    # crisp rims
    c.over(WHITE, c.cover(np.abs(base + 0.8) - 0.8) * 0.9)
    c.over(rgb('#7fdcff'), c.cover(np.abs(top) - 0.7) * 0.6)
    # text
    tm = text_mask(c, 'SPACE', 17, cx, 24.5)
    c.over(rgb('#0d3a8c'), tm)
    return c.image()


# ----------------------------------------------------------------------------

JOBS = {
    'bubble': bubble,
    'bubble_small': bubble_small,
    'soft_dot': soft_dot,
    'sparkle': sparkle_img,
    'glint': glint,
    'ring': ring,
    'dash_streak': dash_streak,
    'cloud_1': cloud_1,
    'cloud_2': cloud_2,
    'cloud_3': cloud_3,
    'cloud_shadow': cloud_shadow,
    'fish_1': lambda: fish(1),
    'fish_2': lambda: fish(2),
    'prompt_space': prompt_space,
    'star': star_small,
}


def _job(name):
    img = JOBS[name]()
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, name + '.png'))
    check_padding(img, name)
    return name, img.size


def main():
    from multiprocessing import Pool
    names = [a for a in sys.argv[1:] if not a.startswith('-')] or list(JOBS)
    with Pool(8) as p:
        for name, size in p.map(_job, names):
            print(f'{name}.png {size[0]}x{size[1]}')


def make_previews():
    """Preview sheets on turquoise + white (scratchpad only)."""
    L = lambda n: Image.open(os.path.join(OUT, n + '.png')).convert('RGBA')
    small = ['bubble', 'bubble_small', 'soft_dot', 'sparkle', 'glint', 'star', 'dash_streak',
             'fish_1', 'fish_2', 'prompt_space']
    preview([L(n) for n in small], 'fx_small_x3', scale=3)
    preview([L('ring'), L('cloud_shadow')], 'fx_ring_shadow')
    for n in ('cloud_1', 'cloud_2', 'cloud_3'):
        preview(L(n), 'fx_' + n, bg2=(40, 120, 200))


if __name__ == '__main__':
    if '--preview' in sys.argv:
        make_previews()
    else:
        main()
