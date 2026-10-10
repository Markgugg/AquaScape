"""
artkit.py - shared helpers on top of aqua.py for props / fx / ui sprites.

Adds:
  * Layer: a sub-region canvas (fast local rendering, composited into a parent)
  * spine(): distance to a curved polyline with along/across coordinates
    (used for palm trunks, fronds, leaves, vines, tentacles)
  * common materials (glass orb, ceramic, chrome), contact shadow
  * preview(): composite onto turquoise + white for visual checks
"""
import math
import os
import numpy as np
from PIL import Image
from aqua import *

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
ART = os.path.join(ROOT, 'Assets/AquaScape/Art')
FONT = os.path.join(ROOT, 'Assets/AquaScape/Fonts/MPLUSRounded1c-ExtraBold.ttf')
PREVIEW = '/private/tmp/claude-501/-Users-markguggenheim-AquaScape/de2db03f-47af-475d-a625-9aefc8d08a9d/scratchpad/art_preview'

WHITE = np.array([1.0, 1.0, 1.0])
GLOW = rgb('#7ff8ff')
AQUA = rgb('#38c8f0')
AQUA_L = rgb('#5fe0ff')
SHADOW_COL = (0.02, 0.18, 0.30)

CHROME_SKY = [
    (0.00, rgb('#d7efff')),
    (0.20, rgb('#9db5d3')),
    (0.38, rgb('#7890b4')),
    (0.47, rgb('#d0deee')),
    (0.53, rgb('#ffffff')),
    (0.66, rgb('#eef6ff')),
    (0.86, rgb('#b5dcfa')),
    (1.00, rgb('#ffffff')),
]


def chrome(n):
    return mat_chrome(n, sky=CHROME_SKY)


def ceramic(n):
    return mat_plastic(n, '#f7fbff', '#9fb6d8', gloss=0.85)


def ceramic_dim(n):
    return mat_plastic(n, '#e4ecf6', '#8299be', gloss=0.6)


# ----------------------------------------------------------------------------
# Layers: render a sub-rectangle at the parent's super-sampling
# ----------------------------------------------------------------------------

class Layer(Canvas):
    """A Canvas covering parent region [x0,x0+w) x [y0,y0+h) in parent px."""

    def __init__(self, parent, x0, y0, w, h):
        x0 = int(max(0, math.floor(x0)))
        y0 = int(max(0, math.floor(y0)))
        w = int(min(parent.w - x0, math.ceil(w)))
        h = int(min(parent.h - y0, math.ceil(h)))
        self.parent, self.x0, self.y0 = parent, x0, y0
        super().__init__(max(w, 1), max(h, 1), parent.ss)
        self.X = self.X + x0
        self.Y = self.Y + y0

    def commit(self, opacity=1.0):
        """Composite this layer 'over' the parent region."""
        p, s = self.parent, self.ss
        ys, xs = self.y0 * s, self.x0 * s
        H, W = self.A.shape
        a = self.A * opacity
        P = self.P * opacity
        p.P[ys:ys + H, xs:xs + W] = P + p.P[ys:ys + H, xs:xs + W] * (1 - a[..., None])
        p.A[ys:ys + H, xs:xs + W] = a + p.A[ys:ys + H, xs:xs + W] * (1 - a)

    def commit_add(self, opacity=1.0):
        p, s = self.parent, self.ss
        ys, xs = self.y0 * s, self.x0 * s
        H, W = self.A.shape
        p.P[ys:ys + H, xs:xs + W] += self.P * opacity
        p.A[ys:ys + H, xs:xs + W] = clamp01(p.A[ys:ys + H, xs:xs + W] + self.A * opacity * 0.5)


def layer_around(c, cx, cy, rx, ry, pad=8):
    return Layer(c, cx - rx - pad, cy - ry - pad, 2 * (rx + pad), 2 * (ry + pad))


# ----------------------------------------------------------------------------
# Spine: distance to polyline + along/across coordinates
# ----------------------------------------------------------------------------

def bezier(p0, p1, p2, n=24, p3=None):
    """Points on a quadratic (or cubic, if p3) Bezier."""
    ts = np.linspace(0, 1, n)
    pts = []
    for t in ts:
        if p3 is None:
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        else:
            x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0]
                 + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0])
            y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1]
                 + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1])
        pts.append((x, y))
    return pts


def spine(c, pts):
    """Return (dist, t, s): unsigned distance to the polyline, normalised
    arc-length param t (0..1) of the nearest point and signed lateral
    offset s (positive = left of travel direction in image space)."""
    pts = np.asarray(pts, float)
    seg = np.hypot(*(pts[1:] - pts[:-1]).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1] + 1e-9
    best = np.full(c.X.shape, 1e9)
    tt = np.zeros(c.X.shape)
    ss = np.zeros(c.X.shape)
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        ex, ey = pts[i + 1] - pts[i]
        L2 = ex * ex + ey * ey + 1e-9
        wx, wy = c.X - x0, c.Y - y0
        h = clamp01((wx * ex + wy * ey) / L2)
        dx, dy = wx - ex * h, wy - ey * h
        d = np.hypot(dx, dy)
        m = d < best
        best = np.where(m, d, best)
        tt = np.where(m, (cum[i] + h * seg[i]) / total, tt)
        cross = (ex * wy - ey * wx) / math.sqrt(L2)
        ss = np.where(m, cross, ss)
    return best, tt, ss


def tube_normals(s, w, t_tilt=None):
    """Cylinder-like normals for a tube of half-width w (s = lateral offset).
    The lateral axis is approximated as image x (good for mostly vertical
    tubes); use with care."""
    u = np.clip(s / np.maximum(w, 1e-6), -1, 1)
    nz = np.sqrt(1 - u * u)
    return u, nz


def shade_from_u(u, nz, lx=-0.55):
    """Simple lighting for a tube given lateral normal u (-1..1)."""
    return clamp01(0.35 + 0.65 * (u * lx + nz * 0.8))


# ----------------------------------------------------------------------------
# Common bits
# ----------------------------------------------------------------------------

def contact_shadow(c, cx, cy, rx, ry, opacity=0.30, core=0.45):
    """Soft ground shadow fully contained in the (rx, ry) ellipse."""
    k = np.hypot((c.X - cx) / rx, (c.Y - cy) / ry)
    a = (1 - smoothstep(core, 1.0, k)) * opacity
    c.over(np.array(SHADOW_COL), a)


def halo(c, sdf, color, R, strength=1.0, power=2.0):
    """Additive glow with compact support: exactly zero beyond distance R."""
    t = clamp01(np.maximum(sdf, 0) / R)
    c.add(np.asarray(color), (1 - t) ** power * strength * (1 - smoothstep(-2, 0, -np.maximum(-sdf, 0)) * 0))


def sheen(c, sdf, cx, cy, rx, ry, opacity=0.8, soft=3):
    """Soft white elliptical highlight clipped to a shape."""
    hl = op_inter(sd_ellipse(c, cx, cy, rx, ry), sdf + 1)
    c.over(WHITE, c.cover(hl, soft) * opacity)


def sparkle(c, x, y, r, opacity=1.0, color=WHITE, thin=0.08):
    """4-point star glint."""
    dx, dy = np.abs(c.X - x), np.abs(c.Y - y)
    star = np.exp(-(dx / (r * thin)) ** 2) * np.exp(-(dy / r) ** 2 * 2) + \
        np.exp(-(dy / (r * thin)) ** 2) * np.exp(-(dx / r) ** 2 * 2)
    core = np.exp(-(dx * dx + dy * dy) / (2 * (r * 0.16) ** 2))
    c.add(np.asarray(color), clamp01((star + core) * opacity))


def glass_orb(c, cx, cy, r, lit=0.0, tint=('#e9fbff', '#8fe6ff', '#2aa6e6'),
              glow_col=GLOW, alpha=0.82, halo=True):
    """Glossy glass sphere. lit=0 -> clear/dim glass, 1 -> brilliant glow."""
    d = sd_circle(c, cx, cy, r)
    n = sphere_normals(c, cx, cy, r)
    rr = np.hypot(c.X - cx, c.Y - cy) / r
    if halo and lit > 0:
        c.glow(d, glow_col, r * 0.9, 0.55 * lit)
        c.glow(d, WHITE, r * 0.25, 0.35 * lit)
    # body: inner ramp (bright bottom = refracted light caustic)
    t = clamp01((c.Y - (cy - r)) / (2 * r))
    col = gradient_map(t, [(0.0, rgb(tint[0])), (0.5, rgb(tint[1])), (1.0, rgb(tint[2]))])
    fres = clamp01(rr) ** 3
    col = mix(col, rgb('#ffffff'), fres[..., None] * 0.35)
    # caustic at the bottom inside
    caus = np.exp(-(((c.X - cx) / (r * 0.55)) ** 2 + ((c.Y - (cy + r * 0.55)) / (r * 0.28)) ** 2))
    col = col + caus[..., None] * 0.35
    a = c.cover(d) * (alpha * (0.55 + 0.45 * fres) + lit * 0.4)
    c.over(clamp01(col), a)
    if lit > 0:
        core = np.exp(-(rr / 0.55) ** 2)
        c.add(mix(glow_col, WHITE, 0.5), core * lit * c.cover(d) * 0.9)
        c.add(WHITE, np.exp(-(rr / 0.25) ** 2) * lit * c.cover(d) * 0.8)
    # rim line and reflections
    rim = np.abs(d + 1.2) - 1.0
    c.over(WHITE, c.cover(rim) * 0.55)
    hl = op_inter(sd_ellipse(c, cx - r * 0.3, cy - r * 0.48, r * 0.5, r * 0.28), d + 2)
    c.over(WHITE, c.cover(hl, 3) * 0.85 * smoothstep(cy - r * 0.05, cy - r * 0.8, c.Y))
    highlight_arc(c, cx, cy, r * 0.82, r * 0.82, max(1.0, r * 0.035), 30, 80, 0.45, (0.85, 1.0, 1.0))
    c.over(WHITE, c.cover(sd_circle(c, cx + r * 0.42, cy - r * 0.42, max(1.5, r * 0.07))) * 0.9)
    return d


def ring_band(c, cx, cy, rx, ry, thick, material=None, top_y=None):
    """A chrome ring seen at 3/4: front half of an elliptical torus band."""
    d = np.abs(sd_ellipse(c, cx, cy, rx, ry)) - thick
    return d


# ----------------------------------------------------------------------------
# Output + preview
# ----------------------------------------------------------------------------

def save(img, rel):
    path = os.path.join(ART, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


def check_padding(img, name, pad=2):
    a = np.asarray(img)[..., 3]
    edge = max(a[:pad].max(), a[-pad:].max(), a[:, :pad].max(), a[:, -pad:].max())
    if edge > 8:
        print(f'WARNING {name}: touches edge (alpha {edge})')


def preview(imgs, name, scale=1.0, cols=None, bg2=(255, 255, 255)):
    """Composite image(s) on turquoise (top row) and white (bottom row)."""
    if not isinstance(imgs, (list, tuple)):
        imgs = [imgs]
    if scale != 1.0:
        imgs = [im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                          Image.LANCZOS) for im in imgs]
    gap = 12
    w = sum(im.width for im in imgs) + gap * (len(imgs) + 1)
    h = max(im.height for im in imgs)
    sheet = Image.new('RGBA', (w, 2 * h + 3 * gap), (40, 190, 215, 255))
    sheet.paste((*bg2, 255), (0, h + 2 * gap - gap // 2, w, 2 * h + 3 * gap))
    x = gap
    for im in imgs:
        sheet.alpha_composite(im, (x, gap + h - im.height))
        sheet.alpha_composite(im, (x, 2 * gap + h + h - im.height))
        x += im.width + gap
    os.makedirs(PREVIEW, exist_ok=True)
    p = os.path.join(PREVIEW, name + '.png')
    sheet.convert('RGB').save(p)
    return p
