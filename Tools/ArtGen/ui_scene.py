"""
ui_scene.py - the 1920x1080 key-art panoramas (title day / level-complete night).

Side view: sky gradient, planet, layered cumulus clouds, a distant white glass
city on the horizon, a turquoise ocean with reflections and sparkles, a
floating grassy island with palms and a waterfall, a framing foreground shore
and drifting bubbles. Everything is drawn analytically with the aqua.py SDF
painter (ss=1 for the big canvas, analytic AA from the SDFs) using local
Layers so thousands of shapes stay fast.
"""
import math
import numpy as np
from PIL import Image, ImageFilter
from aqua import *
from artkit import Layer, spine, bezier, sparkle, WHITE, GLOW

W, H = 1920, 1080
HZ = 640          # horizon line (y)


class SLayer(Layer):
    """Layer whose content fades out near its interior borders, so glows that
    reach the layer edge never leave a visible rectangle."""

    def _window(self):
        p = self.parent
        m = max(2.0, min(28.0, 0.18 * min(self.w, self.h)))
        X, Y = self.X, self.Y
        w = np.ones(X.shape)
        if self.x0 > 0:
            w *= smoothstep(self.x0, self.x0 + m, X)
        if self.x0 + self.w < p.w:
            w *= smoothstep(self.x0 + self.w, self.x0 + self.w - m, X)
        if self.y0 > 0:
            w *= smoothstep(self.y0, self.y0 + m, Y)
        if self.y0 + self.h < p.h:
            w *= smoothstep(self.y0 + self.h, self.y0 + self.h - m, Y)
        self.P = self.P * w[..., None]
        self.A = self.A * w

    def commit(self, opacity=1.0):
        self._window()
        super().commit(opacity)

    def commit_add(self, opacity=1.0):
        self._window()
        super().commit_add(opacity)


def P(night):
    """Palette for day / night."""
    if not night:
        return dict(
            sky=[(0.0, rgb('#1f7ff0')), (0.35, rgb('#3ea6ff')), (0.7, rgb('#8fd6ff')),
                 (0.92, rgb('#d8f6ff')), (1.0, rgb('#f4fdff'))],
            haze=rgb('#d6f3ff'),
            cloud_hi=rgb('#ffffff'), cloud_lo=rgb('#a9cdf0'), cloud_rim=rgb('#ffffff'),
            sea=[(0.0, rgb('#9ff2f2')), (0.06, rgb('#4fd8e6')), (0.35, rgb('#14b4d6')),
                 (1.0, rgb('#0a78c0'))],
            glint=rgb('#ffffff'),
            grass=[(0, rgb('#a6ee6a')), (0.5, rgb('#5ccf4f')), (1, rgb('#2f9e44'))],
            leaf_hi=rgb('#b4f27a'), leaf_mid=rgb('#4cc24e'), leaf_lo=rgb('#1f7a3c'),
            trunk_hi=rgb('#f2dcb4'), trunk_lo=rgb('#b08a62'),
            ceramic_hi=rgb('#ffffff'), ceramic_lo=rgb('#9fb6d8'),
            glass=rgb('#5fe0ff'), light=0.0)
    return dict(
        sky=[(0.0, rgb('#060b2e')), (0.35, rgb('#14215e')), (0.65, rgb('#33308a')),
             (0.88, rgb('#6a58b8')), (1.0, rgb('#a58ad8'))],
        haze=rgb('#7d6cc4'),
        cloud_hi=rgb('#5c5aae'), cloud_lo=rgb('#151a4c'), cloud_rim=rgb('#c9ccff'),
        sea=[(0.0, rgb('#8f86d8')), (0.05, rgb('#4b4fa8')), (0.35, rgb('#1c2c74')),
             (1.0, rgb('#0a1240'))],
        glint=rgb('#e9f4ff'),
        grass=[(0, rgb('#5ab878')), (0.5, rgb('#2a7e64')), (1, rgb('#14485a'))],
        leaf_hi=rgb('#5fc79a'), leaf_mid=rgb('#22735e'), leaf_lo=rgb('#0d3a46'),
        trunk_hi=rgb('#9a8cc0'), trunk_lo=rgb('#4a3f78'),
        ceramic_hi=rgb('#cfd4ff'), ceramic_lo=rgb('#4a4c96'),
        glass=rgb('#7ff8ff'), light=1.0)


# ----------------------------------------------------------------------------
# Sky
# ----------------------------------------------------------------------------

def draw_sky(c, pal, night, rng):
    t = clamp01(c.Y / HZ)
    col = gradient_map(t ** 1.15, pal['sky'])
    # gentle diagonal sun/moon wash from the upper right
    wash = np.exp(-(((c.X - 1500) / 900) ** 2 + ((c.Y - 200) / 500) ** 2))
    col = col + wash[..., None] * (np.array([0.10, 0.12, 0.10]) if not night else np.array([0.08, 0.06, 0.14]))
    c.over(clamp01(col), np.ones(c.X.shape))
    if night:
        # milky way band + stars
        band = np.exp(-((c.Y - (520 - c.X * 0.28)) / 150) ** 2)
        nz = value_noise(W, H, 90, seed=7, octaves=5)
        c.add(rgb('#8a7fe0'), band * (nz ** 2) * 0.35 * (c.Y < HZ))
        for _ in range(520):
            x, y = rng.uniform(0, W), rng.uniform(0, HZ - 20) ** 1.0
            y = rng.uniform(0, 1) ** 1.6 * (HZ - 30)
            r = rng.uniform(0.6, 1.7)
            L = SLayer(c, x - 7, y - 7, 14, 14)
            d = sd_circle(L, x, y, r)
            L.glow(d, rgb('#cfe0ff'), r * 1.4, rng.uniform(0.4, 1.0))
            L.over(WHITE, L.cover(d) * rng.uniform(0.6, 1.0))
            L.commit_add()
        for _ in range(26):
            x, y = rng.uniform(0, W), rng.uniform(0, 1) ** 1.4 * (HZ - 80)
            r = rng.uniform(8, 18)
            L = SLayer(c, x - r * 1.6, y - r * 1.6, r * 3.2, r * 3.2)
            sparkle(L, x, y, r, rng.uniform(0.6, 1.0), color=rgb('#e6f0ff'))
            L.commit_add()
    else:
        # faint light rays from the upper right
        ang = np.arctan2(c.Y + 300, c.X - 1700)
        rays = (np.sin(ang * 38) * 0.5 + 0.5) ** 6 * np.exp(-((c.Y) / 700) ** 2)
        c.add(WHITE, rays * 0.06)


def draw_planet(c, pal, night):
    cx, cy, r = (1500, 250, 175) if not night else (1460, 270, 210)
    L = SLayer(c, cx - r * 2.4, cy - r * 1.9, r * 4.8, r * 3.8)
    d = sd_circle(L, cx, cy, r)
    n = sphere_normals(L, cx, cy, r)
    # atmosphere glow
    L.glow(d, rgb('#f0fcff') if not night else rgb('#dfe4ff'), r * 0.3, 0.5 if not night else 0.7)
    L.glow(d, rgb('#aeeaff') if not night else rgb('#8a7cff'), r * 0.85, 0.2 if not night else 0.35)
    nz = value_noise(L.w, L.h, 50, seed=3, octaves=4)
    if not night:
        # pastel gas-giant bands (lavender / pink / cyan), lit from upper-left
        u = (L.Y - cy) / r + (nz - 0.5) * 0.25
        bands = np.sin(u * 7.5) * 0.5 + 0.5
        base = gradient_map(bands, [(0, rgb('#e7e2ff')), (0.35, rgb('#ffe9f6')),
                                    (0.7, rgb('#e2f7ff')), (1, rgb('#cfe0ff'))])
        lam = clamp01(n[..., 0] * -0.45 + n[..., 1] * -0.45 + n[..., 2] * 0.78)
        col = base * (0.72 + 0.32 * lam)[..., None]
        col = mix(col, rgb('#9fd8ff'), ((1 - n[..., 2]) ** 2.5 * 0.55)[..., None])
        alpha = 0.93
    else:
        base = gradient_map(nz, [(0, rgb('#dfe2f4')), (0.55, rgb('#fbfbff')), (1, rgb('#e9ecfb'))])
        lam = clamp01(n[..., 0] * -0.3 + n[..., 1] * -0.25 + n[..., 2] * 0.9)
        col = base * (0.78 + 0.26 * lam)[..., None]
        col = mix(col, rgb('#b8b4ff'), ((1 - n[..., 2]) ** 2.5 * 0.4)[..., None])
        alpha = 1.0
        # soft maria (very low contrast)
        rng = np.random.default_rng(12)
        for _ in range(7):
            a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(0.1, 0.7) * r
            x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
            cd = sd_circle(L, x, y, rng.uniform(0.1, 0.22) * r)
            col = mix(col, col * np.array([0.8, 0.82, 0.95]), (L.cover(cd, 10) * 0.7)[..., None])
            col = mix(col, np.minimum(col * 1.06, 1), (L.cover(np.abs(cd + 2) - 1.5, 3) * 0.4)[..., None])
    L.over(clamp01(col), L.cover(d) * alpha)
    # glossy highlight + crisp rim light
    hl = op_inter(sd_ellipse(L, cx - r * 0.35, cy - r * 0.45, r * 0.45, r * 0.25), d + 4)
    L.over(WHITE, L.cover(hl, 12) * 0.35)
    L.over(WHITE, L.cover(np.abs(d + 1.5) - 1.5) * clamp01(-n[..., 0] - n[..., 1] * 0.5) * 0.8)
    if not night:
        # thin tilted ring (Y2K planet)
        dx, dy = L.X - cx, L.Y - cy
        rot = math.radians(-14)
        ux = dx * math.cos(rot) + dy * math.sin(rot)
        uy = -dx * math.sin(rot) + dy * math.cos(rot)
        k = np.hypot(ux / (r * 1.75), uy / (r * 0.34))
        front = ((uy > 0) | (np.hypot(dx, dy) > r)).astype(float)
        ring = np.abs(k - 1) * r * 0.34 - 3.0
        L.over(WHITE, L.cover(ring) * front * 0.8)
        ring2 = np.abs(k - 0.92) * r * 0.34 - 1.4
        L.over(rgb('#bff3ff'), L.cover(ring2) * front * 0.65)
        L.glow(ring, rgb('#bff8ff'), 6, 0.25 * front)
    L.commit()
    # second small moon
    mx, my, mr = (1180, 140, 34) if not night else (1130, 150, 30)
    L = SLayer(c, mx - mr * 3, my - mr * 3, mr * 6, mr * 6)
    d = sd_circle(L, mx, my, mr)
    n = sphere_normals(L, mx, my, mr)
    L.glow(d, WHITE, mr * 0.5, 0.35)
    lam = clamp01(n[..., 0] * -0.5 + n[..., 1] * -0.4 + n[..., 2] * 0.75)
    col = mix(rgb('#c4d2f4') if not night else rgb('#8f96d0'), rgb('#ffffff'), lam[..., None])
    L.over(col, L.cover(d) * (0.88 if not night else 0.95))
    L.commit()


# ----------------------------------------------------------------------------
# Clouds
# ----------------------------------------------------------------------------

def cumulus(c, cx, base, w, h, pal, seed, alpha=1.0, haze=0.0, flat=True):
    """Illustrated cumulus: many sphere-shaded puffs, flat-ish bottom."""
    rng = np.random.default_rng(seed)
    L = SLayer(c, cx - w / 2 - h * 0.6, base - h * 1.5, w + h * 1.2, h * 1.5 + 30)
    puffs = []
    n = int(10 + w / 30)
    for i in range(n):
        u = rng.uniform(-1, 1)
        env = (1 - u * u) ** 0.7
        r = h * rng.uniform(0.28, 0.55) * (0.45 + 0.55 * env)
        x = cx + u * w / 2 * 0.9
        y = base - r * 0.55 - rng.uniform(0, 1) * env * h * 0.75
        puffs.append((y, x, r))
    puffs.sort()
    hi = mix(pal['cloud_hi'], pal['haze'], haze)
    lo = mix(pal['cloud_lo'], pal['haze'], haze * 0.8)
    bottom = smoothstep(base + 6, base - 10, L.Y) if flat else 1.0
    for y, x, r in puffs:
        d = sd_circle(L, x, y, r)
        nn = sphere_normals(L, x, y, r)
        lam = clamp01(nn[..., 0] * -0.25 + nn[..., 1] * -0.75 + nn[..., 2] * 0.5)
        vert = clamp01((L.Y - (base - h * 1.3)) / (h * 1.3))     # darker towards the base
        col = mix(hi, lo, clamp01((1 - lam) * 0.55 + vert * 0.55)[..., None])
        # rim light on top edges
        rim = clamp01(-nn[..., 1]) * (1 - nn[..., 2]) ** 1.5
        col = mix(col, pal['cloud_rim'], (rim * 0.8)[..., None])
        L.over(clamp01(col), L.cover(d, max(1.5, r * 0.04)) * bottom)
    L.commit(alpha)


def wisp(c, cx, cy, w, h, pal, seed, alpha=0.5):
    """Thin streaky high cloud."""
    L = SLayer(c, cx - w / 2 - 20, cy - h - 20, w + 40, 2 * h + 40)
    nz = value_noise(L.w, L.h, 30, seed=seed, octaves=3)
    e = np.exp(-(((L.X - cx) / (w / 2)) ** 2 * 1.5 + ((L.Y - cy) / h) ** 2))
    a = clamp01(e * (0.5 + nz) - 0.25) * alpha
    L.over(pal['cloud_hi'], a)
    L.commit()


def draw_clouds_far(c, pal, night):
    # horizon cloud bank behind the city
    rng = np.random.default_rng(5)
    x = -80
    k = 0
    while x < W + 100:
        w = rng.uniform(260, 420)
        cumulus(c, x + w / 2, HZ - 2, w, rng.uniform(90, 150), pal, 100 + k, alpha=0.95, haze=0.35)
        x += w * 0.7
        k += 1
    # high wisps
    for i, (x, y, w) in enumerate([(300, 120, 520), (820, 70, 380), (1750, 520, 300), (520, 330, 300)]):
        wisp(c, x, y, w, 26, pal, 40 + i, 0.35 if not night else 0.2)


def draw_clouds_mid(c, pal, night):
    k = 0.8 if night else 0.97
    cumulus(c, 260, 400, 520, 190, pal, 7, alpha=k)
    cumulus(c, 110, 470, 300, 120, pal, 8, alpha=0.95)
    cumulus(c, 960, 520, 360, 120, pal, 9, alpha=0.9, haze=0.25)
    cumulus(c, 1830, 440, 420, 170, pal, 10, alpha=0.97)
    cumulus(c, 1240, 330, 220, 70, pal, 11, alpha=0.85, haze=0.1)


# ----------------------------------------------------------------------------
# City
# ----------------------------------------------------------------------------

def tower(L, x, base, w, h, pal, kind, haze, night, rng):
    """One distant building. kind: 'glass' cylinder, 'white' tower, 'dome', 'spire'."""
    hz = pal['haze']
    top = base - h
    if kind == 'dome':
        d = op_union(sd_ellipse(L, x, base, w, h), sd_box(L, x, base + 5, w, 10))
        d = op_inter(d, L.Y - base - 2)
    elif kind == 'spire':
        d = sd_poly(L, [(x - w, base + 2), (x - w * 0.6, base - h * 0.55), (x, top), (x + w * 0.6, base - h * 0.55), (x + w, base + 2)])
    else:
        d = sd_box(L, x, base - h / 2 + 4, w, h / 2 + 4, min(w * 0.9, 14))
    u = clamp01((L.X - (x - w)) / (2 * w)) * 2 - 1            # -1..1 across
    cyl = np.sqrt(clamp01(1 - u * u))
    if kind == 'glass':
        col = gradient_map(clamp01(0.5 + 0.5 * u), [(0, rgb('#c9f6ff')), (0.45, rgb('#5fd2f5')), (1, rgb('#2a8fd6'))])
        if night:
            col = gradient_map(clamp01(0.5 + 0.5 * u), [(0, rgb('#4a6ad0')), (0.5, rgb('#24338a')), (1, rgb('#141c58'))])
        stripe = smoothstep(0.08, 0.0, np.abs(u + 0.45)) * 0.7
        col = col + stripe[..., None]
        # horizontal white ceramic rings
        rings = (np.abs(((L.Y - top) % 46) - 23) > 20) * (L.Y > top + 18)
        col = mix(col, pal['ceramic_hi'], (rings * 0.8)[..., None])
    else:
        col = mix(pal['ceramic_lo'], pal['ceramic_hi'], (0.35 + 0.65 * clamp01(cyl * 0.7 - u * 0.4))[..., None])
        # aqua glass band
        band = np.abs(L.Y - (top + h * 0.28)) < 5
        col = mix(col, pal['glass'], (band * (kind != 'spire') * 0.85)[..., None])
    if night:
        # window lights
        wy = ((L.Y - top) % 14) < 4
        wx = ((L.X - x + w) % 10) < 5
        lights = wy * wx * (L.Y > top + 10) * (np.abs(u) < 0.8)
        seedmap = value_noise(L.w, L.h, 6, seed=int(x), octaves=1) > 0.55
        col = mix(col, rgb('#9ffcff'), (lights * seedmap * 0.9)[..., None])
    col = mix(col, hz, haze)
    cov = L.cover(d)
    L.over(clamp01(col), cov)
    # top cap highlight + antenna light
    if kind in ('glass', 'white'):
        cap = sd_ellipse(L, x, top + 4, w * 0.95, 5)
        L.over(mix(pal['ceramic_hi'], hz, haze * 0.6), L.cover(cap) * 0.9)
        ant = sd_capsule(L, x, top, x, top - h * 0.12, 1.2)
        L.over(mix(pal['ceramic_hi'], hz, haze), L.cover(ant))
        tip = sd_circle(L, x, top - h * 0.12, 2.5)
        L.glow(tip, GLOW if not night else rgb('#ff9ae6'), 5, 0.7)
    return d


def draw_city(c, pal, night):
    rng = np.random.default_rng(21)
    x0, x1 = 120, 1000
    L = SLayer(c, x0 - 60, HZ - 360, x1 - x0 + 120, 380)
    if night:
        L.glow(sd_box(L, (x0 + x1) / 2, HZ, (x1 - x0) / 2, 40, 40), rgb('#5fe0ff'), 70, 0.35)
    # far row
    x = x0
    while x < x1:
        w = rng.uniform(10, 22)
        h = rng.uniform(60, 150) * (1 - abs((x - 560) / 600) * 0.6)
        tower(L, x, HZ, w, h, pal, rng.choice(['glass', 'white', 'white']), 0.55, night, rng)
        x += w * 2 + rng.uniform(2, 14)
    # near row: hero towers
    specs = [(250, 26, 170, 'glass'), (330, 60, 70, 'dome'), (430, 22, 250, 'white'),
             (470, 30, 300, 'glass'), (540, 18, 220, 'spire'), (600, 70, 90, 'dome'),
             (690, 24, 200, 'glass'), (750, 18, 140, 'white'), (830, 40, 60, 'dome'),
             (880, 16, 120, 'glass'), (180, 18, 110, 'white'), (960, 30, 45, 'dome')]
    for x, w, h, k in specs:
        tower(L, x, HZ + 2, w, h, pal, k, 0.22, night, rng)
    if night:
        for x, w, h, k in specs:
            if k in ('glass', 'white', 'spire'):
                L.glow(sd_capsule(L, x, HZ - h * 0.2, x, HZ - h, w * 0.6), rgb('#5fe0ff'), 16, 0.12)
    L.commit()


# ----------------------------------------------------------------------------
# Ocean
# ----------------------------------------------------------------------------

def draw_ocean(c, pal, night, sky_img):
    t = clamp01((c.Y - HZ) / (H - HZ))
    sea = (c.Y >= HZ).astype(float)
    col = gradient_map(t ** 0.8, pal['sea'])
    # perspective wave texture: strongly anisotropic noise (wide ripples),
    # rows compressed near the horizon
    depth = 1.0 / ((c.Y - HZ).clip(0) + 18)
    small = value_noise(192, 1024, 20, seed=31, octaves=4)
    tex = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((3072, 1024), Image.BICUBIC), float) / 255
    v = (depth * 9000).astype(int) % 1024
    u = ((c.X - W / 2) * (0.7 + depth * 25) + 1536).astype(int) % 3072
    tv = tex[v, u]
    waves = smoothstep(0.5, 0.72, tv)
    troughs = smoothstep(0.45, 0.25, tv)
    col = mix(col, clamp01(col * 1.15 + 0.06), (waves * 0.5)[..., None])
    col = mix(col, col * 0.82, (troughs * 0.35)[..., None])
    # light caustic-ish bright band near the horizon
    col = col + (np.exp(-((c.Y - HZ) / 60) ** 2) * 0.08)[..., None]
    c.over(clamp01(col), sea)

    # reflections of the sky elements (flipped, rippled, blurred)
    sky = np.asarray(sky_img, float)[:HZ] / 255.0
    refl = sky[::-1].copy()
    nrow = min(H - HZ, refl.shape[0])
    refl = refl[:nrow]
    rows = np.arange(nrow)
    for i in range(nrow):
        sh = int(np.sin(i * 0.45) * (1.5 + i * 0.04) + np.sin(i * 0.13 + 1) * 3)
        refl[i] = np.roll(refl[i], sh, axis=0)
    rim = Image.fromarray((refl * 255).astype(np.uint8), 'RGBA').filter(ImageFilter.GaussianBlur(2.0))
    ra = np.asarray(rim, float) / 255.0
    fade = np.exp(-rows / (130 if not night else 170))[:, None]
    reg_c = c.P[HZ:HZ + nrow]
    a = fade * (0.42 if not night else 0.5) * (0.55 + 0.45 * waves[HZ:HZ + nrow])
    tint = ra[..., :3] * (np.array([0.85, 1.0, 1.0]) if not night else np.array([0.9, 0.95, 1.1]))
    c.P[HZ:HZ + nrow] = tint * a[..., None] + reg_c * (1 - a[..., None])

    # bright glitter path under the planet / moon
    px = 1500 if not night else 1460
    path = np.exp(-((c.X - px) / (50 + (c.Y - HZ) * 0.5)) ** 2) * sea
    glit = smoothstep(0.6, 0.78, tv) * path
    c.add(pal['glint'], glit * (0.65 if not night else 0.9))
    # horizon haze line
    c.add(pal['haze'], np.exp(-((c.Y - HZ) / 4) ** 2) * 0.45)
    # sparkles scattered over the water
    rng = np.random.default_rng(77)
    for _ in range(60):
        y = HZ + 8 + rng.uniform(0, 1) ** 1.7 * (H - HZ - 8)
        x = rng.uniform(0, W)
        if rng.random() < 0.45:
            x = px + rng.normal(0, 60 + (y - HZ) * 0.4)
        x = float(np.clip(x, 10, W - 10))
        r = 4 + (y - HZ) / (H - HZ) * 20 * rng.uniform(0.4, 1.0)
        L = SLayer(c, x - r * 1.6, y - r * 1.6, r * 3.2, r * 3.2)
        sparkle(L, x, y, r, rng.uniform(0.5, 1.0), color=pal['glint'])
        L.commit_add()


# ----------------------------------------------------------------------------
# Palm (side view) + plants
# ----------------------------------------------------------------------------

def frond(c, x0, y0, ang, length, width, pal, droop=0.45, seed=0):
    dx, dy = math.cos(ang), math.sin(ang)
    p1 = (x0 + dx * length * 0.45, y0 + dy * length * 0.45 - length * 0.18)
    p2 = (x0 + dx * length * 0.95, y0 + dy * length * 0.95 + length * droop)
    pts = bezier((x0, y0), p1, p2, 22)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    pad = width + 6
    L = SLayer(c, min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)
    dist, t, s = spine(L, pts)
    wprof = width * np.sin(np.pi * clamp01(t) ** 0.75) ** 0.7 * (1 - 0.25 * t)
    # leaflets: diagonal teeth along the frond
    ph = t * 15 - np.abs(s) / np.maximum(wprof, 1) * 0.9
    f = ph - np.floor(ph)
    serr = 0.3 + 0.7 * smoothstep(0.0, 0.8, f)
    d = dist - wprof * serr
    across = clamp01(np.abs(s) / np.maximum(wprof, 1))
    upper = (s < 0)          # side facing the light
    col = mix(pal['leaf_hi'], pal['leaf_mid'], clamp01(across * 0.8 + t * 0.4)[..., None])
    col = mix(col, pal['leaf_lo'], ((~upper) * 0.45 + smoothstep(0.75, 1.0, t) * 0.3)[..., None])
    col = mix(col, pal['leaf_lo'], (smoothstep(0.15, 0.0, f) * 0.5)[..., None])  # gaps
    # midrib + gloss
    col = mix(col, pal['leaf_hi'] * 1.1, (smoothstep(2.2, 0.6, dist) * 0.8)[..., None])
    gl = np.exp(-((across - 0.35) / 0.12) ** 2) * upper * (1 - t) * 0.35
    col = col + gl[..., None]
    L.over(clamp01(col), L.cover(d))
    L.commit()


def palm(c, bx, by, height, lean, pal, scale=1.0, seed=0, n_fronds=9):
    rng = np.random.default_rng(seed)
    tx, ty = bx + lean, by - height
    pts = bezier((bx, by), (bx + lean * 0.1, by - height * 0.55), (tx, ty), 26)
    w0, w1 = 16 * scale, 9 * scale
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    L = SLayer(c, min(xs) - 30, min(ys) - 30, max(xs) - min(xs) + 60, max(ys) - min(ys) + 60)
    dist, t, s = spine(L, pts)
    wt = w0 + (w1 - w0) * t
    d = dist - wt
    u = np.clip(s / wt, -1, 1)
    lam = clamp01(0.45 + 0.55 * (-u * 0.7 + np.sqrt(1 - u * u) * 0.5))
    col = mix(pal['trunk_lo'], pal['trunk_hi'], lam[..., None])
    ringp = (t * height / (11 * scale)) % 1.0
    col = mix(col, pal['trunk_lo'] * 0.8, (smoothstep(0.75, 0.95, ringp) * 0.6)[..., None])
    col = col + (smoothstep(0.0, 0.15, ringp) * smoothstep(0.3, 0.15, ringp) * 0.12)[..., None]
    L.over(clamp01(col), L.cover(d))
    L.commit()
    # fronds behind, coconuts, fronds in front
    angs = np.linspace(-math.pi * 0.95, -math.pi * 0.05, n_fronds) + rng.uniform(-0.12, 0.12, n_fronds)
    back = angs[::2]
    front = angs[1::2]
    for a in back:
        frond(c, tx, ty, a, rng.uniform(150, 190) * scale, 24 * scale, pal, droop=rng.uniform(0.35, 0.6))
    for k in range(3):
        cxk, cyk = tx + (k - 1) * 9 * scale, ty + 10 * scale + (k % 2) * 6 * scale
        Lc = SLayer(c, cxk - 15 * scale, cyk - 15 * scale, 30 * scale, 30 * scale)
        dd = sd_circle(Lc, cxk, cyk, 9 * scale)
        nn = sphere_normals(Lc, cxk, cyk, 9 * scale)
        cc = mix(rgb('#5a3a22'), rgb('#b88a50'), lambert(nn)[..., None]) + spec(nn, 30)[..., None] * 0.4
        if pal['light']:
            cc = cc * 0.55 + np.array([0.05, 0.05, 0.15])
        Lc.over(clamp01(cc), Lc.cover(dd))
        Lc.commit()
    for a in front:
        frond(c, tx, ty, a + 0.15, rng.uniform(140, 175) * scale, 24 * scale, pal, droop=rng.uniform(0.5, 0.8))
    # two droopy fronds hanging down
    frond(c, tx, ty, math.pi * 0.15, 130 * scale, 22 * scale, pal, droop=0.9)
    frond(c, tx, ty, math.pi * 0.85, 130 * scale, 22 * scale, pal, droop=0.9)


def bush(c, cx, cy, r, pal, seed, flowers=0, night=False):
    rng = np.random.default_rng(seed)
    L = SLayer(c, cx - r * 1.8, cy - r * 1.6, r * 3.6, r * 2.2)
    blobs = sorted([(cy - rng.uniform(0, 1) * r * 0.6, cx + rng.uniform(-1, 1) * r, r * rng.uniform(0.45, 0.7)) for _ in range(9)])
    for y, x, rr in blobs:
        d = sd_circle(L, x, y, rr)
        nn = sphere_normals(L, x, y, rr)
        lam = lambert(nn)
        col = mix(pal['leaf_lo'], pal['leaf_hi'], (0.2 + 0.8 * lam)[..., None]) + spec(nn, 40)[..., None] * (0.35 if not night else 0.12)
        L.over(clamp01(col), L.cover(d) * smoothstep(cy + 6, cy - 4, L.Y))
    for i in range(flowers):
        x = cx + rng.uniform(-0.9, 0.9) * r
        y = cy - rng.uniform(0.1, 0.9) * r
        fr = rng.uniform(5, 8) * r / 40
        pc = rgb('#ff8fd0') if not night else rgb('#7ff8ff')
        if night:
            L.glow(sd_circle(L, x, y, fr), rgb('#7ff8ff') if i % 2 else rgb('#c49cff'), fr * 1.4, 0.32)
            pc = rgb('#9ffcff') if i % 2 else rgb('#d6b8ff')
        for k in range(5):
            a = k / 5 * 2 * math.pi + i
            d = sd_ellipse(L, x + math.cos(a) * fr * 0.8, y + math.sin(a) * fr * 0.8, fr * 0.75, fr * 0.75)
            L.over(pc, L.cover(d))
        L.over(rgb('#fff1a0'), L.cover(sd_circle(L, x, y, fr * 0.35)))
    L.commit()


# ----------------------------------------------------------------------------
# Floating island + waterfall
# ----------------------------------------------------------------------------

def floating_island(c, pal, night, cx=1420, top=540, rx=250):
    """Floating island: rounded white ceramic underside with stalactite lobes,
    an aqua glass band, hanging vines, and a grassy dome on top."""
    tip = top + 290
    L = SLayer(c, cx - rx - 70, top - 90, 2 * rx + 140, tip - top + 170)
    rng = np.random.default_rng(4)
    d = sd_ellipse(L, cx, top + 16, rx - 4, 30)
    lobes = [(-0.62, 0.38, 0.22), (-0.3, 0.7, 0.26), (0.02, 1.0, 0.3), (0.35, 0.66, 0.24), (0.66, 0.32, 0.2)]
    for lx, ll, lw in lobes:
        x = cx + lx * rx
        d = op_smooth_union(d, sd_capsule(L, x, top + 20, x + lx * 10, top + 20 + ll * (tip - top - 20),
                                          lw * rx, 13), 40)
    hgt = height_bevel(d, 70)
    n = normals(L, hgt)
    lam = clamp01((n * np.array([-0.55, -0.35, 0.75])).sum(axis=2))
    v = clamp01((L.Y - top) / (tip - top))
    col = gradient_map(v, [(0, pal['ceramic_hi']), (0.55, mix(pal['ceramic_hi'], pal['ceramic_lo'], 0.45)),
                           (1, pal['ceramic_lo'])])
    col = col * (0.72 + 0.36 * lam)[..., None]
    nz = value_noise(L.w, L.h, 14, seed=5, octaves=3)
    col = col * (0.95 + 0.08 * nz)[..., None]
    # stratified ledges that wrap around the rounded body
    wy = L.Y - (n[..., 1] * 0)
    led = ((L.Y - top - 8 + (L.X - cx) ** 2 / (rx * 9)) % 36) / 36
    col = mix(col, col * 0.84, (smoothstep(0.86, 1.0, led) * 0.55)[..., None])
    col = col + (smoothstep(0.0, 0.08, led) * smoothstep(0.16, 0.08, led) * 0.08)[..., None]
    # bounce light from the water on the underside
    col = col + (smoothstep(0.5, 1.0, v) * clamp01(n[..., 1]))[..., None] * np.array([0.0, 0.12, 0.14])
    # aqua glass band with a glossy streak
    by = top + 50 + ((L.X - cx) / rx) ** 2 * 18
    band = smoothstep(9, 7, np.abs(L.Y - by))
    bcol = gradient_map(clamp01((L.Y - by + 8) / 16), [(0, rgb('#c8fdff')), (0.5, pal['glass']), (1, rgb('#1590d6'))])
    col = mix(col, bcol, (band * 0.92)[..., None])
    col = mix(col, WHITE, (smoothstep(1.5, 0, np.abs(L.Y - by + 3)) * band * 0.6)[..., None])
    col = col + spec(n, 30)[..., None] * 0.25
    cov = L.cover(d)
    L.over(clamp01(col), cov)
    if night:
        L.glow(op_inter(d, np.abs(L.Y - by) - 8), rgb('#7ff8ff'), 12, 0.4)
    # hanging vines
    for i in range(10):
        vx = cx - rx * 0.88 + i * rx * 0.19 + rng.uniform(-8, 8)
        vl = rng.uniform(40, 130) * (1 - abs(vx - cx) / rx * 0.4)
        vpts = [(vx + math.sin(k * 0.6 + i) * 4, top + 26 + k * vl / 10) for k in range(11)]
        dist, t, s = spine(L, vpts)
        vd = dist - (3.0 - 1.8 * t)
        L.over(mix(pal['leaf_mid'], pal['leaf_lo'], t[..., None]), L.cover(vd))
        for k in range(2, 11, 2):
            lx, ly = vpts[k]
            side = 4 if k % 4 else -4
            L.over(pal['leaf_hi'] if k % 4 else pal['leaf_mid'], L.cover(sd_ellipse(L, lx + side, ly, 5.5, 3.2)))
        if night and i % 3 == 0:
            ex, ey = vpts[-1]
            fd = sd_circle(L, ex, ey + 3, 3.5)
            L.glow(fd, rgb('#7ff8ff'), 6, 0.6)
            L.over(rgb('#d8ffff'), L.cover(fd))
    L.commit()

    # grass top: glossy dome with a lit front lip
    L = SLayer(c, cx - rx - 50, top - 80, 2 * rx + 100, 140)
    nz = value_noise(L.w, L.h, 16, seed=9, octaves=2)
    g = sd_ellipse(L, cx, top + 2, rx + 10, 38) + (nz - 0.5) * 8
    # scalloped grass drape hanging over the front edge
    ex = clamp01(1 - ((L.X - cx) / (rx + 10)) ** 2)
    ye = top + 2 + 38 * np.sqrt(ex)                      # front edge of the dome
    scal = (7 + 6 * np.abs(np.sin((L.X - cx) / 11.0))) * np.sqrt(ex)
    drape = op_inter(-(L.Y - (ye - 3)), L.Y - (ye + scal)) + (ex < 0.02) * 100.0
    L.over(pal['grass'][2][1], L.cover(drape))
    gh = height_bevel(g, 26)
    gn = normals(L, gh)
    t = clamp01((L.Y - (top - 36)) / 76)
    col = gradient_map(t, pal['grass'])
    col = col * (0.82 + 0.25 * lambert(gn))[..., None] + spec(gn, 30)[..., None] * 0.2
    col = col + (smoothstep(0.6, 0.85, nz) * 0.06)[..., None]
    L.over(clamp01(col), L.cover(g))
    # bright lip along the front edge, darker drape below it
    front = smoothstep(top - 10, top + 20, L.Y)
    L.over(pal['grass'][0][1], L.cover(np.abs(g + 3) - 2) * front * 0.7)
    hl = sd_ellipse(L, cx - 50, top - 16, rx * 0.6, 9)
    L.over(WHITE, L.cover(hl, 8) * 0.2)
    L.commit()


def waterfall(c, pal, night, x0, y0, y1, w=30):
    L = SLayer(c, x0 - w * 4, y0 - 20, w * 8, y1 - y0 + 110)
    nz = value_noise(L.w, L.h, 5, seed=2, octaves=2)
    t = clamp01((L.Y - y0) / (y1 - y0))
    hw = w * (0.55 + 0.7 * t)
    xc = x0 - 14 * t ** 2
    d = np.abs(L.X - xc) - hw
    d = op_inter(d, -(L.Y - y0))
    d = op_inter(d, L.Y - y1)
    streak = np.sin((L.X - xc) / hw * 10 + nz * 5) * 0.5 + 0.5
    base = rgb('#bff6ff') if not night else rgb('#9fb0ff')
    col = mix(base, WHITE, (streak * 0.7)[..., None])
    a = L.cover(d) * (0.55 + 0.35 * streak) * smoothstep(y0 - 2, y0 + 10, L.Y)
    L.glow(d, WHITE if not night else rgb('#9ff8ff'), 8, 0.18)
    L.over(col, a)
    # splash: soft mist puffs + ripple rings on the water
    mist = WHITE if not night else rgb('#c8d0ff')
    for k in range(10):
        ang = k / 9 * math.pi
        bx = x0 - 14 + math.cos(ang) * w * 1.7
        by = y1 + 4 - math.sin(ang) * 20
        L.over(mist, L.cover(sd_circle(L, bx, by, w * 0.8), 9) * 0.5)
    for k, rr in enumerate((1.8, 2.6, 3.4)):
        ring = np.abs(sd_ellipse(L, x0 - 14, y1 + 14 + k * 4, w * rr, w * rr * 0.18)) - 1.2
        L.over(WHITE, L.cover(ring, 1.5) * (0.6 - k * 0.15))
    L.commit()


# ----------------------------------------------------------------------------
# Foreground shore + bubbles
# ----------------------------------------------------------------------------

def foreground_shore(c, pal, night):
    # white sand / ceramic shore with grass, bottom-left
    L = SLayer(c, 0, 800, 820, 280)
    d = sd_ellipse(L, 160, 1170, 650, 280)
    n = normals(L, height_bevel(d, 30))
    col = gradient_map(clamp01((L.Y - 890) / 190), [(0, pal['ceramic_hi']), (1, pal['ceramic_lo'])])
    col = col * (0.85 + 0.2 * lambert(n))[..., None] + spec(n, 40)[..., None] * 0.4
    L.glow(d, WHITE, 14, 0.25 if not night else 0.12)
    L.over(clamp01(col), L.cover(d))
    # wet sand line + foam
    L.over(rgb('#7fe8f0') if not night else rgb('#5a5cb8'), L.cover(np.abs(d + 9) - 3, 2) * 0.5)
    L.over(WHITE, L.cover(np.abs(d - 2) - 2.5, 2) * (0.85 if not night else 0.5))
    g = sd_ellipse(L, 100, 1180, 560, 245) + (value_noise(L.w, L.h, 5, seed=4, octaves=2) - 0.5) * 12
    gn = normals(L, height_bevel(g, 25))
    gc = gradient_map(clamp01((L.Y - 935) / 150), pal['grass'])
    gc = gc * (0.82 + 0.25 * lambert(gn))[..., None] + spec(gn, 30)[..., None] * 0.2
    L.over(clamp01(gc), L.cover(g))
    L.over(pal['grass'][0][1], L.cover(np.abs(g + 3) - 2) * 0.6)
    L.commit()
    bush(c, 120, 990, 70, pal, 1, flowers=5, night=night)
    bush(c, 340, 1010, 55, pal, 2, flowers=3, night=night)
    palm(c, 40, 1080, 640, 230, pal, scale=1.45, seed=3)


def bubbles(c, pal, night):
    from ui import draw_bubble
    rng = np.random.default_rng(99)
    spots = [(1100, 860, 30), (1150, 780, 16), (1080, 720, 10), (680, 900, 22), (720, 820, 12),
             (1700, 900, 40), (1760, 790, 20), (1640, 740, 12), (300, 640, 14), (860, 560, 18),
             (1870, 650, 14), (560, 990, 34), (1010, 980, 18), (1220, 1010, 46), (1290, 920, 14),
             (1560, 1010, 22), (1820, 990, 12), (640, 760, 8), (780, 700, 6), (1620, 820, 9),
             (420, 560, 10), (1000, 420, 8), (1960 - 120, 360, 16)]
    for x, y, r in spots:
        L = SLayer(c, x - r * 2, y - r * 2, r * 4, r * 4)
        draw_bubble(L, x, y, r, 1.0)
        L.commit(0.95)


def scene(night):
    pal = P(night)
    rng = np.random.default_rng(1)
    c = Canvas(W, H, 1)
    draw_sky(c, pal, night, rng)
    draw_planet(c, pal, night)
    draw_clouds_far(c, pal, night)
    draw_clouds_mid(c, pal, night)
    draw_city(c, pal, night)
    # sky snapshot for water reflections
    sky_img = c.image()
    draw_ocean(c, pal, night, sky_img)
    # soft shadow of the island on the water far below it
    c.over(np.array([0.02, 0.2, 0.32]) if not night else np.array([0.02, 0.02, 0.1]),
           c.cover(sd_ellipse(c, 1440, 905, 250, 24), 40) * 0.3)
    waterfall(c, pal, night, 1196, 548, 900)
    floating_island(c, pal, night)
    palm(c, 1495, 540, 230, 50, pal, scale=0.85, seed=11)
    palm(c, 1335, 544, 180, -60, pal, scale=0.7, seed=12)
    bush(c, 1590, 542, 42, pal, 5, flowers=4, night=night)
    bush(c, 1280, 546, 34, pal, 6, flowers=2, night=night)
    bush(c, 1420, 548, 30, pal, 7, flowers=3, night=night)
    # little floating rocks around the island
    for (x, y, r) in [(1700, 700, 26), (1150, 470, 16), (1760, 610, 12)]:
        mini_rock(c, x, y, r, pal)
    foreground_shore(c, pal, night)
    bubbles(c, pal, night)
    img = c.image().convert('RGB').convert('RGBA')
    return img




def mini_rock(c, x, y, r, pal):
    L = SLayer(c, x - r * 2, y - r * 1.5, r * 4, r * 4.5)
    d = op_smooth_union(sd_ellipse(L, x, y, r, r * 0.35), sd_capsule(L, x, y, x + r * 0.1, y + r * 1.6, r * 0.75, 2), r * 0.5)
    n = normals(L, height_bevel(d, r))
    v = clamp01((L.Y - y) / (r * 1.8))
    col = gradient_map(v, [(0, pal['ceramic_hi']), (1, pal['ceramic_lo'])]) * (0.75 + 0.3 * lambert(n))[..., None]
    L.over(clamp01(col), L.cover(d))
    g = sd_ellipse(L, x, y - 2, r * 1.05, r * 0.32)
    L.over(gradient_map(clamp01((L.Y - y + r * 0.3) / (r * 0.6)), pal['grass']), L.cover(g))
    L.commit()
