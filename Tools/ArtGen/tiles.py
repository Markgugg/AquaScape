"""
tiles.py - dual-grid terrain tiles for AquaScape.

A dual-grid tile sits on the corner between four world cells. Its look is
decided by which of those four cells are filled (16 combinations), which lets
us get smooth, rounded island shapes from a plain grid of cells.

Mask bits (image space): TL=1, TR=2, BL=4, BR=8.

Each terrain is drawn from a blurred raster of the four corner cells. Blurring
then thresholding rounds every corner, and because the blur radius is smaller
than half a cell, the result along a tile edge depends only on the two cells
shared with the neighbouring tile - so tiles are always seamless.
"""
import math
import os
import numpy as np
from PIL import Image
from aqua import *

OUT = os.path.join(os.path.dirname(__file__), '../../Assets/AquaScape/Art/Tiles')
T = 128          # tile size in px (== 1 world cell at 128 PPU)
SS = 2           # super-sampling
M = T // 2       # margin rendered around the tile (half a cell)
N = (T + 2 * M) * SS


# ---------------------------------------------------------------------------
# raster helpers
# ---------------------------------------------------------------------------

def fft_blur(a, sigma):
    """Gaussian blur through the FFT (no scipy needed)."""
    h, w = a.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-2 * (math.pi ** 2) * (sigma ** 2) * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def corner_mask(mask):
    """Sharp raster (N x N) of the four corner cells, including the margin."""
    a = np.zeros((N, N))
    cell = T * SS
    off = M * SS
    corners = {1: (0, 0), 2: (1, 0), 4: (0, 1), 8: (1, 1)}
    for bit, (cx, cy) in corners.items():
        if mask & bit:
            x0 = off + cx * cell - cell // 2
            y0 = off + cy * cell - cell // 2
            a[max(0, y0):y0 + cell, max(0, x0):x0 + cell] = 1.0
    return a


def erfinv(x):
    """Inverse error function (M. Giles' polynomial approximation)."""
    w = -np.log((1.0 - x) * (1.0 + x))
    a = w - 2.5
    p1 = 2.81022636e-08
    for k in (3.43273939e-07, -3.5233877e-06, -4.39150654e-06, 0.00021858087,
              -0.00125372503, -0.00417768164, 0.246640727, 1.50140941):
        p1 = k + p1 * a
    b = np.sqrt(np.maximum(w, 0)) - 3.0
    p2 = -0.000200214257
    for k in (0.000100950558, 0.00134934322, -0.00367342844, 0.00573950773,
              -0.0076224613, 0.00943887047, 1.00167406, 2.83297682):
        p2 = k + p2 * b
    return np.where(w < 5.0, p1, p2) * x


def field(mask, sigma_px):
    """Blurred occupancy -> rounded shape + signed distance in final px.

    A Gaussian-blurred straight edge follows the normal CDF, so inverting it
    recovers the distance to the (now rounded) edge."""
    b = fft_blur(corner_mask(mask), sigma_px * SS)
    b = np.clip(b, 1e-12, 1 - 1e-12)
    sdf = -sigma_px * math.sqrt(2.0) * erfinv(2.0 * b - 1.0)
    return sdf, b


def shift_down(a, px):
    """Shift a raster down by px (final pixels); fill with 'outside' values."""
    s = int(round(px * SS))
    if s <= 0:
        return a
    out = np.empty_like(a)
    out[:s] = a[0]
    out[s:] = a[:-s]
    return out


def periodic_noise(c, seed, freqs=(1, 2, 3, 5, 8), amp_decay=0.6):
    """Noise that tiles every T pixels (so neighbouring tiles line up)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(c.X.shape)
    amp, tot = 1.0, 0.0
    for f in freqs:
        for _ in range(3):
            kx, ky = rng.integers(-f, f + 1, 2)
            if kx == 0 and ky == 0:
                kx = f
            ph = rng.random() * 2 * math.pi
            out += amp * np.sin(2 * math.pi * (kx * c.X + ky * c.Y) / T + ph)
            tot += amp
        amp *= amp_decay
    return out / tot * 0.5 + 0.5


class TileCanvas(Canvas):
    """Canvas covering the tile plus margin; image() crops to the tile."""

    def __init__(self):
        super().__init__(T + 2 * M, T + 2 * M, SS)
        # shift coordinates so (0,0) is the tile's top-left corner
        self.X = self.X - M
        self.Y = self.Y - M

    def image(self):
        full = super().image()
        return full.crop((M, M, M + T, M + T))


def interior_window(c, margin=22):
    """1 in the middle of the tile, fading to 0 near its borders."""
    wx = smoothstep(0, margin, c.X) * smoothstep(T, T - margin, c.X)
    wy = smoothstep(0, margin, c.Y) * smoothstep(T, T - margin, c.Y)
    return wx * wy


# ---------------------------------------------------------------------------
# Ground: white ceramic island with a glossy cliff and aqua glass band
# ---------------------------------------------------------------------------
CLIFF_H = 40
SIGMA = 19


def render_ground(mask, variant=0):
    c = TileCanvas()
    sdf, occ = field(mask, SIGMA)
    land = c.cover(sdf)

    # --- cliff: land extruded downwards -----------------------------------
    depth = np.full(sdf.shape, np.inf)
    cliff_sdf = np.full(sdf.shape, np.inf)
    edge_nx = np.zeros(sdf.shape)
    gx = np.gradient(sdf, axis=1)
    for k in range(0, CLIFF_H + 1):
        sh = shift_down(sdf, k)
        inside = sh < 0
        depth = np.where(inside & (depth == np.inf), k, depth)
        cliff_sdf = np.minimum(cliff_sdf, sh)
        edge_nx = np.where(inside & (depth == k), shift_down(gx, k), edge_nx)
    cliff_cov = c.cover(cliff_sdf) * (1 - land)
    d01 = np.clip(depth / CLIFF_H, 0, 1)
    d01 = np.where(np.isinf(depth), 1, d01)

    # soft shadow + foam line on the water beneath the cliff
    below = shift_down(cliff_sdf, 10)
    sh_a = c.cover(below, 6) * (1 - c.cover(cliff_sdf)) * 0.28
    c.over(rgb('#0b4a66'), sh_a)

    # cliff body: glossy white ceramic, wrapping around rounded corners
    side = np.clip(edge_nx / (np.abs(edge_nx).max() + 1e-6), -1, 1)
    base = gradient_map(d01, [(0.0, rgb('#ffffff')), (0.35, rgb('#eef5fc')),
                              (0.75, rgb('#c9d9ee')), (1.0, rgb('#9fb6d6'))])
    base = base * (1 - 0.12 * np.clip(side, 0, 1)[..., None])  # right-facing a bit darker
    base = base + 0.10 * np.clip(-side, 0, 1)[..., None]
    c.over(clamp01(base), cliff_cov)
    # aqua glass band
    band = smoothstep(0.42, 0.47, d01) * (1 - smoothstep(0.66, 0.71, d01))
    band_col = gradient_map((d01 - 0.42) / 0.29, [(0.0, rgb('#b8fbff')), (0.5, rgb('#38c8f0')),
                                                   (1.0, rgb('#1590d6'))])
    c.over(band_col, band * cliff_cov * 0.95)
    # specular streak on the glass band
    streak = smoothstep(0.47, 0.5, d01) * (1 - smoothstep(0.5, 0.54, d01))
    c.over(np.array([1, 1, 1.0]), streak * cliff_cov * 0.55)
    # chrome hairline above the band and a dark base line
    line = smoothstep(0.36, 0.38, d01) * (1 - smoothstep(0.39, 0.41, d01))
    c.over(rgb('#8fa7c6'), line * cliff_cov * 0.8)
    base_line = smoothstep(0.88, 1.0, d01)
    c.over(rgb('#5d7da3'), base_line * cliff_cov * 0.5)

    # --- top surface: pale ceramic plaza --------------------------------------
    h = height_bevel(sdf, 9)
    n = normals(c, h)
    noise = periodic_noise(c, 11)
    top = gradient_map(noise, [(0.0, rgb('#e9f1f8')), (1.0, rgb('#fbfdff'))])
    # subtle plaza grid (period 64px so it lines up between tiles)
    gxl = np.abs(((c.X + 32) % 64) - 32)
    gyl = np.abs(((c.Y + 32) % 64) - 32)
    grout = (1 - smoothstep(0.6, 1.6, np.minimum(gxl, gyl)))
    top = mix(top, rgb('#cfdceb'), grout * 0.55)
    # bevel shading + sheen
    lam = lambert(n)
    top = top * (0.86 + 0.16 * lam)[..., None] + spec(n, 40)[..., None] * 0.5
    c.over(clamp01(top), land)
    # inner aqua glass inlay running along the edge
    inlay = np.abs(sdf + 15) - 2.2
    inlay_a = c.cover(inlay) * land
    c.over(rgb('#5fe0ff'), inlay_a * 0.85)
    c.glow(inlay, rgb('#7ff4ff'), 3.5, 0.18 * 1.0)
    # top-left rim highlight
    rim = np.abs(sdf + 2.5) - 1.3
    c.over(np.array([1, 1, 1.0]), c.cover(rim) * land * clamp01(0.4 + lam))

    # decorative glass inlays on some full plaza tiles (kept off the borders)
    if mask == 15 and variant:
        def inlay_panel(cx, cy, half, radius):
            d = sd_box(c, cx, cy, half, half, radius)
            n2 = normals(c, height_bevel(d, 4))
            t = clamp01((c.Y - (cy - half)) / (2 * half))
            g = gradient_map(t, [(0, rgb('#c9f6ff')), (0.5, rgb('#5fd3f5')), (1, rgb('#2aa4e6'))])
            g = g + spec(n2, 60)[..., None] * 0.8
            c.over(clamp01(g), c.cover(d) * 0.85)
            c.over(np.array([1, 1, 1.0]), c.cover(np.abs(d) - 1.2) * 0.9)
            band = op_inter(d + 2, (c.X - cx) + (c.Y - cy) * 0.9 + half * 0.2)
            band = op_inter(band, -((c.X - cx) + (c.Y - cy) * 0.9 + half * 0.7))
            c.over(np.array([1, 1, 1.0]), c.cover(band) * 0.35)
        if variant == 1:
            inlay_panel(64, 64, 20, 7)
        elif variant == 2:
            for (x, y) in ((32, 32), (96, 32), (32, 96), (96, 96)):
                inlay_panel(x, y, 8, 3)
        else:
            ring = np.abs(sd_circle(c, 64, 64, 20)) - 2.0
            c.over(rgb('#5fe0ff'), c.cover(ring) * 0.8)
            c.glow(ring, rgb('#7ff4ff'), 3, 0.15)
            inlay_panel(64, 64, 7, 3)
    return c.image()


# ---------------------------------------------------------------------------
# Grass overlay (sits on top of the ground, inset from island edges)
# ---------------------------------------------------------------------------

def render_grass(mask, variant=0):
    c = TileCanvas()
    dist, _ = field(mask, 19)
    wob = periodic_noise(c, 5, freqs=(4, 6, 9, 13), amp_decay=0.75)
    sdf = dist + 13 + (wob - 0.5) * 9          # inset from the cell edge
    cov = c.cover(sdf)

    # drop shadow onto the plaza
    sh = shift_down(sdf, 5)
    c.over(rgb('#3d6b70'), c.cover(sh - 1, 5) * (1 - cov) * 0.22)

    n = normals(c, height_bevel(sdf, 10))
    tone = periodic_noise(c, 21, freqs=(1, 2, 3))
    blades = periodic_noise(c, 33 + variant * 0, freqs=(16, 21, 26, 32), amp_decay=0.9)
    col = gradient_map(tone, [(0.0, rgb('#2fae4c')), (0.45, rgb('#55cc57')), (1.0, rgb('#97e66d'))])
    # clumpy light / dark patches
    clumps = periodic_noise(c, 44, freqs=(3, 5, 7), amp_decay=0.7)
    col = mix(col, rgb('#2a9844'), smoothstep(0.58, 0.8, clumps) * 0.35)
    col = mix(col, rgb('#a8ef7a'), smoothstep(0.6, 0.85, 1 - clumps) * 0.3)
    # fine blade strokes: stretched vertical noise reads as little grass tufts
    tufts = periodic_noise(c, 57, freqs=(24, 32, 40), amp_decay=0.95)
    tuft_dark = smoothstep(0.66, 0.8, tufts)
    tuft_lit = smoothstep(0.66, 0.8, shift_down(tufts, 2.0))
    col = mix(col, rgb('#2d9e48'), tuft_dark * 0.55)
    col = mix(col, rgb('#c8fa94'), (tuft_lit * (1 - tuft_dark)) * 0.45)
    col = mix(col, rgb('#2a9a45'), smoothstep(0.55, 0.9, blades) * 0.3)
    lam = lambert(n)
    col = col * (0.8 + 0.28 * lam)[..., None] + spec(n, 25)[..., None] * 0.18
    # darker edge so the grass reads as a soft raised carpet
    col = mix(col, rgb('#2b8f42'), smoothstep(-6, 0, sdf) * 0.5)
    c.over(clamp01(col), cov)
    # bright leafy lip on the upper edge
    lip = np.abs(sdf + 3) - 1.5
    c.over(rgb('#c6ff9a'), c.cover(lip) * cov * clamp01(lam * 1.2) * 0.7)

    if mask == 15 and variant:
        # little flowers and clover kept inside the tile
        rng = np.random.default_rng(100 + variant)
        w = interior_window(c, 20)
        palette = [rgb('#ffffff'), rgb('#ff9ad5'), rgb('#ffe27a'), rgb('#9af0ff')]
        for _ in range(rng.integers(3, 7)):
            x, y = rng.uniform(22, 106, 2)
            col = palette[rng.integers(0, 4)]
            for k in range(5):
                a = k / 5 * 2 * math.pi
                d = sd_circle(c, x + math.cos(a) * 3, y + math.sin(a) * 3, 2.6)
                c.over(col, c.cover(d) * w)
            c.over(rgb('#ffd34d'), c.cover(sd_circle(c, x, y, 1.6)) * w)
        for _ in range(rng.integers(2, 5)):
            x, y = rng.uniform(22, 106, 2)
            for k in range(3):
                a = k / 3 * 2 * math.pi - 0.5
                d = sd_ellipse(c, x + math.cos(a) * 4, y + math.sin(a) * 4, 4.5, 3.5)
                c.over(rgb('#2f9e48'), c.cover(d) * w * 0.9)
    return c.image()


# ---------------------------------------------------------------------------
# Glass walkway (bridges, Glass City floors)
# ---------------------------------------------------------------------------
GLASS_H = 16


def render_glass(mask, variant=0):
    c = TileCanvas()
    sdf, _ = field(mask, 9)
    cov = c.cover(sdf)
    # thin glass edge
    cliff = np.full(sdf.shape, np.inf)
    depth = np.full(sdf.shape, np.inf)
    for k in range(GLASS_H + 1):
        sh = shift_down(sdf, k)
        depth = np.where((sh < 0) & np.isinf(depth), k, depth)
        cliff = np.minimum(cliff, sh)
    ccov = c.cover(cliff) * (1 - cov)
    d01 = np.where(np.isinf(depth), 1, depth / GLASS_H)
    c.over(rgb('#0b4a66'), c.cover(shift_down(cliff, 6), 5) * (1 - c.cover(cliff)) * 0.18)
    edge = gradient_map(d01, [(0, rgb('#e9fbff')), (0.5, rgb('#6fd8f6')), (1, rgb('#2b9fe0'))])
    c.over(edge, ccov * 0.85)
    c.over(np.array([1, 1, 1.0]), ccov * (1 - smoothstep(0.75, 1.0, d01)) * 0)  # placeholder
    c.over(rgb('#ffffff'), ccov * smoothstep(0.82, 1.0, d01) * 0.7)

    # translucent glass top
    n = normals(c, height_bevel(sdf, 7))
    tone = periodic_noise(c, 3, freqs=(1, 2))
    glass = gradient_map(tone, [(0, rgb('#7fdcff')), (1, rgb('#b6efff'))])
    c.over(glass, cov * 0.62)
    # diagonal reflection streaks (periodic so they continue across tiles)
    diag = ((c.X + c.Y) % 128) / 128
    streak = smoothstep(0.30, 0.34, diag) * (1 - smoothstep(0.38, 0.44, diag))
    streak += 0.6 * smoothstep(0.52, 0.535, diag) * (1 - smoothstep(0.545, 0.56, diag))
    c.over(np.array([1, 1, 1.0]), cov * streak * 0.35)
    # panel seams every 64px
    gxl = np.abs(((c.X + 32) % 64) - 32)
    gyl = np.abs(((c.Y + 32) % 64) - 32)
    seam = 1 - smoothstep(0.5, 1.4, np.minimum(gxl, gyl))
    c.over(rgb('#e8fbff'), cov * seam * 0.6)
    # white chrome rim
    rim = np.abs(sdf + 4) - 3.2
    rn = n
    rim_col = mat_plastic(rn, '#ffffff', '#a9c4e3', gloss=1.0)
    c.over(rim_col, c.cover(rim) * cov)
    c.over(rgb('#5fe8ff'), c.cover(np.abs(sdf + 9.5) - 1.0) * cov * 0.8)
    return c.image()


def solid_tile():
    img = Image.new('RGBA', (T, T), (255, 255, 255, 255))
    return img


def main():
    from multiprocessing import Pool
    os.makedirs(OUT, exist_ok=True)
    jobs = []
    for m in range(16):
        jobs.append(('ground', m, 0))
        jobs.append(('grass', m, 0))
        jobs.append(('glass', m, 0))
    for v in (1, 2, 3):
        jobs.append(('ground', 15, v))
        jobs.append(('grass', 15, v))
    with Pool() as p:
        p.map(_job, jobs)
    solid_tile().save(f'{OUT}/solid.png')
    print('tiles:', len(jobs))


def _job(j):
    kind, m, v = j
    fn = {'ground': render_ground, 'grass': render_grass, 'glass': render_glass}[kind]
    name = f'{kind}_{m:02d}' + (f'_v{v}' if v else '')
    fn(m, v).save(f'{OUT}/{name}.png')


if __name__ == '__main__':
    main()
