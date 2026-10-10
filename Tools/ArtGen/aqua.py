"""
aqua.py - a tiny "2.5D" SDF painter used to generate every AquaScape sprite.

Shapes are described as signed distance fields (negative inside). Each shape
is turned into a fake height field (a bevel or a dome), normals are derived
from that height, and a material function shades it (chrome, glossy plastic,
glass, ...). Everything is rendered super-sampled and box-filtered down for
clean anti-aliased edges.

Coordinates are in *final* pixels, x to the right and y DOWN (image space).
"""
import math
import os
import numpy as np
from PIL import Image, ImageFilter

# ----------------------------------------------------------------------------
# Small math helpers
# ----------------------------------------------------------------------------

def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(e0, e1, x):
    t = clamp01((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    """Linear blend; a scalar-field t is broadcast over RGB automatically."""
    a, b, t = np.asarray(a, float), np.asarray(b, float), np.asarray(t, float)
    is_rgb = a.shape[-1:] == (3,) or b.shape[-1:] == (3,)
    if is_rgb and t.ndim and t.shape[-1:] not in ((3,), (1,)):
        t = t[..., None]
    return a + (b - a) * t


def rgb(hexstr):
    """'#rrggbb' -> float array in 0..1."""
    h = hexstr.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def gradient_map(t, stops):
    """Map scalar field t (0..1) through a list of (pos, color) stops."""
    t = clamp01(t)
    out = np.zeros(t.shape + (3,))
    pos = [s[0] for s in stops]
    cols = [np.asarray(s[1], dtype=float) for s in stops]
    out[...] = cols[0]
    for i in range(len(stops) - 1):
        a, b = pos[i], pos[i + 1]
        w = clamp01((t - a) / max(b - a, 1e-6))[..., None]
        seg = (t >= a)[..., None]
        out = np.where(seg, cols[i] + (cols[i + 1] - cols[i]) * w, out)
    return out


def value_noise(w, h, scale, seed=0, octaves=4):
    """Cheap fractal value noise (0..1) without scipy."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        s = max(1, int(scale / (2 ** o)))
        gw, gh = w // s + 3, h // s + 3
        grid = rng.random((gh, gw))
        img = Image.fromarray((grid * 255).astype(np.uint8)).resize(
            (gw * s, gh * s), Image.BICUBIC)
        arr = np.asarray(img, dtype=float)[:h, :w] / 255.0
        out += arr * amp
        total += amp
        amp *= 0.5
    return out / total


# ----------------------------------------------------------------------------
# Canvas
# ----------------------------------------------------------------------------

class Canvas:
    """Premultiplied RGBA float canvas rendered at `ss` times final size."""

    def __init__(self, w, h, ss=3):
        self.w, self.h, self.ss = w, h, ss
        W, H = w * ss, h * ss
        self.P = np.zeros((H, W, 3))   # premultiplied colour
        self.A = np.zeros((H, W))      # alpha
        ys, xs = np.mgrid[0:H, 0:W].astype(float)
        # final-pixel coordinates of each sub-sample centre
        self.X = (xs + 0.5) / ss
        self.Y = (ys + 0.5) / ss
        self.px = 1.0 / ss            # size of one sub-sample in final px

    # -- compositing -------------------------------------------------------
    def over(self, color, alpha):
        alpha = clamp01(alpha)
        if np.ndim(color) == 1:
            color = np.broadcast_to(color, self.P.shape)
        a = alpha[..., None]
        self.P = color * a + self.P * (1 - a)
        self.A = alpha + self.A * (1 - alpha)

    def add(self, color, alpha):
        """Additive light (keeps alpha of what is below, adds glow alpha)."""
        alpha = clamp01(alpha)
        if np.ndim(color) == 1:
            color = np.broadcast_to(color, self.P.shape)
        self.P = self.P + color * alpha[..., None]
        self.A = clamp01(self.A + alpha * 0.5)

    def cover(self, sdf, soft=1.0):
        """Anti-aliased coverage of a distance field (in final px)."""
        return clamp01(0.5 - sdf / (soft * self.px * 1.5))

    def glow(self, sdf, color, radius, strength=1.0):
        """Soft additive halo outside/around a shape."""
        g = np.exp(-np.maximum(sdf, 0) ** 2 / (2 * radius ** 2)) * strength
        self.add(color, g)

    def shadow(self, sdf, blur, opacity, color=(0.05, 0.25, 0.35)):
        a = clamp01(0.5 - sdf / blur) * opacity
        self.over(np.array(color), a)

    # -- output ------------------------------------------------------------
    def image(self):
        ss = self.ss
        H, W = self.A.shape
        P = self.P.reshape(H // ss, ss, W // ss, ss, 3).mean(axis=(1, 3))
        A = self.A.reshape(H // ss, ss, W // ss, ss).mean(axis=(1, 3))
        C = np.where(A[..., None] > 1e-5, P / np.maximum(A[..., None], 1e-5), 0)
        out = np.dstack([clamp01(C), clamp01(A)])
        return Image.fromarray((out * 255 + 0.5).astype(np.uint8), 'RGBA')

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.image().save(path)


# ----------------------------------------------------------------------------
# Signed distance primitives (final px units)
# ----------------------------------------------------------------------------

def sd_circle(c, cx, cy, r):
    return np.hypot(c.X - cx, c.Y - cy) - r


def sd_ellipse(c, cx, cy, rx, ry):
    # good-enough ellipse distance (exact on the axes)
    dx, dy = (c.X - cx) / rx, (c.Y - cy) / ry
    k = np.hypot(dx, dy)
    return (k - 1.0) * min(rx, ry)


def sd_box(c, cx, cy, hw, hh, r=0.0):
    qx = np.abs(c.X - cx) - (hw - r)
    qy = np.abs(c.Y - cy) - (hh - r)
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    inside = np.minimum(np.maximum(qx, qy), 0)
    return outside + inside - r


def sd_capsule(c, x1, y1, x2, y2, r1, r2=None):
    if r2 is None:
        r2 = r1
    px, py = c.X - x1, c.Y - y1
    bx, by = x2 - x1, y2 - y1
    L2 = bx * bx + by * by + 1e-9
    h = clamp01((px * bx + py * by) / L2)
    return np.hypot(px - bx * h, py - by * h) - (r1 + (r2 - r1) * h)


def sd_poly(c, pts):
    """Signed distance to a closed polygon (list of (x,y))."""
    X, Y = c.X, c.Y
    n = len(pts)
    d = np.full(X.shape, 1e9)
    s = np.ones(X.shape)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[i - 1]
        ex, ey = x1 - x0, y1 - y0
        wx, wy = X - x0, Y - y0
        h = clamp01((wx * ex + wy * ey) / (ex * ex + ey * ey + 1e-9))
        bx, by = wx - ex * h, wy - ey * h
        d = np.minimum(d, bx * bx + by * by)
        c1 = Y >= y0
        c2 = Y < y1
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


def op_union(*ds):
    out = ds[0]
    for d in ds[1:]:
        out = np.minimum(out, d)
    return out


def op_smooth_union(a, b, k):
    h = clamp01(0.5 + 0.5 * (b - a) / k)
    return b + (a - b) * h - k * h * (1 - h)


def op_sub(a, b):
    return np.maximum(a, -b)


def op_inter(a, b):
    return np.maximum(a, b)


# ----------------------------------------------------------------------------
# Height fields and normals
# ----------------------------------------------------------------------------

def height_bevel(sdf, bevel):
    """Quarter-circle bevel profile: 0 at the edge, `bevel` on the plateau."""
    d = clamp01(-sdf / bevel)
    return bevel * np.sqrt(1 - (1 - d) ** 2)


def normals(c, height):
    gy, gx = np.gradient(height, c.px)
    n = np.dstack([-gx, -gy, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n


def sphere_normals(c, cx, cy, rx, ry=None):
    ry = ry or rx
    dx = (c.X - cx) / rx
    dy = (c.Y - cy) / ry
    dz = np.sqrt(clamp01(1 - dx * dx - dy * dy))
    n = np.dstack([dx, dy, dz])
    n /= np.linalg.norm(n, axis=2, keepdims=True) + 1e-9
    return n


LIGHT = np.array([-0.45, -0.75, 0.55])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1.0])
HALF = HALF / np.linalg.norm(HALF)


def lambert(n):
    return clamp01((n * LIGHT).sum(axis=2))


def spec(n, power):
    return clamp01((n * HALF).sum(axis=2)) ** power


# ----------------------------------------------------------------------------
# Materials (return an RGB field for a given normal map)
# ----------------------------------------------------------------------------

def mat_chrome(n, tint=(1, 1, 1), sky=None):
    """Mirror chrome reflecting an aqua sky / white horizon / blue ground."""
    # reflection of a view ray looking into the screen
    ny = -n[..., 1]          # +1 when normal faces up
    nz = n[..., 2]
    nx = n[..., 0]
    t = ny * 0.5 + 0.5       # 0 = facing down, 1 = facing up
    t = clamp01(t + nx * 0.08)
    stops = sky or [
        (0.00, rgb('#cfe9ff')),   # bounce light at the very bottom
        (0.18, rgb('#5d7fa6')),
        (0.40, rgb('#33507a')),   # dark ground reflection
        (0.47, rgb('#9fb8d6')),
        (0.52, rgb('#ffffff')),   # bright horizon line
        (0.62, rgb('#d9ecff')),
        (0.85, rgb('#8fc8f5')),   # sky
        (1.00, rgb('#e8f6ff')),
    ]
    col = gradient_map(t, stops)
    # flat-facing parts look more like a soft studio reflection
    col = mix(col, rgb('#eaf3fb'), smoothstep(0.85, 1.0, nz)[..., None] * 0.35)
    col = col + spec(n, 80)[..., None] * 1.2 + spec(n, 12)[..., None] * 0.15
    return clamp01(col * np.asarray(tint))


def mat_plastic(n, base=('#f7fbff'), shade=('#9fb6d8'), gloss=0.9):
    base, shade = rgb(base), rgb(shade)
    l = lambert(n)
    col = mix(shade, base, (0.25 + 0.75 * l)[..., None])
    # cool blue rim from the sky
    rim = (1 - n[..., 2]) ** 2
    col = mix(col, rgb('#bfe6ff'), (rim * 0.35)[..., None])
    col = col + spec(n, 45)[..., None] * gloss + spec(n, 8)[..., None] * 0.08
    return clamp01(col)


def mat_glass(c, n, mask_sdf, top, mid, bottom, glow=None):
    """Glossy tinted glass: vertical colour ramp + fresnel + reflections."""
    # vertical ramp using normal y as a stand in for depth
    t = clamp01(n[..., 1] * 0.5 + 0.5)
    col = gradient_map(t, [(0.0, rgb(top)), (0.55, rgb(mid)), (1.0, rgb(bottom))])
    fres = (1 - n[..., 2]) ** 2.2
    col = mix(col, rgb('#bfefff'), (fres * 0.55)[..., None])
    col = col + spec(n, 120)[..., None] * 1.5 + spec(n, 20)[..., None] * 0.15
    return clamp01(col)


# ----------------------------------------------------------------------------
# Composite helpers
# ----------------------------------------------------------------------------

def paint(c, sdf, color, alpha=1.0, soft=1.0):
    c.over(color, c.cover(sdf, soft) * alpha)


def paint_shaded(c, sdf, material, bevel=None, normals_override=None, alpha=1.0):
    """Shade a shape with a material callback taking a normal map."""
    if normals_override is not None:
        n = normals_override
    else:
        n = normals(c, height_bevel(sdf, bevel))
    col = material(n)
    c.over(col, c.cover(sdf) * alpha)
    return n


def inner_shadow(c, sdf, width, opacity, color=(0.2, 0.3, 0.5), clip=None):
    """Darken just inside the edge of a shape (ambient occlusion feel)."""
    a = smoothstep(-width, 0, sdf) * c.cover(sdf) * opacity
    if clip is not None:
        a = a * c.cover(clip)
    c.over(np.array(color), a)


def highlight_arc(c, cx, cy, rx, ry, thickness, a0, a1, opacity=0.9, color=(1, 1, 1)):
    """Curved specular stripe (used for visors and bubbles)."""
    ang = np.arctan2((c.Y - cy) / ry, (c.X - cx) / rx)
    rad = np.hypot((c.X - cx) / rx, (c.Y - cy) / ry)
    band = np.abs(rad - 1.0) * min(rx, ry) - thickness
    lo, hi = math.radians(a0), math.radians(a1)
    span = (hi - lo) / 2
    mid = (hi + lo) / 2
    da = np.abs(np.angle(np.exp(1j * (ang - mid))))
    taper = clamp01(1 - (da / span) ** 2)
    a = c.cover(band) * taper * opacity
    c.over(np.array(color), a)


def blur_image(img, radius):
    return img.filter(ImageFilter.GaussianBlur(radius))


def save_sheet(frames, path):
    """Horizontally pack PIL frames (used only for previews)."""
    w = sum(f.width for f in frames)
    h = max(f.height for f in frames)
    sheet = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    x = 0
    for f in frames:
        sheet.paste(f, (x, 0))
        x += f.width
    sheet.save(path)
