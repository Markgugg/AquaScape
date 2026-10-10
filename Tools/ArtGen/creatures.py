"""
creatures.py - AquaScape animals: top-down pond/reef fish, glassy sky fish,
morpho butterfly. All sprites are centred (no pivot entries needed).

Usage:  python3 creatures.py               # everything
        python3 creatures.py koi_orange    # one family (all its frames)
"""
import math
import os
import sys
from types import SimpleNamespace
import numpy as np
from PIL import Image, ImageFilter
from aqua import *
from artkit import *
from props import fade_edges

PREV = '/private/tmp/claude-501/-Users-markguggenheim-AquaScape/de2db03f-47af-475d-a625-9aefc8d08a9d/scratchpad/scenery_preview'
FAMILIES = {}


def family(name, frames):
    def deco(fn):
        FAMILIES[name] = (fn, frames)
        return fn
    return deco


def view(c, X, Y):
    """A stand-in canvas with remapped coordinates (for warped SDF evaluation)."""
    return SimpleNamespace(X=X, Y=Y, px=c.px)


def drop_shadow(img, dx=5, dy=7, blur=4, opacity=0.2):
    a = img.split()[3].filter(ImageFilter.GaussianBlur(blur))
    a = a.point(lambda v: int(v * opacity))
    sh = Image.new('RGBA', img.size, tuple(int(v * 255) for v in SHADOW_COL) + (0,))
    sh.putalpha(a)
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.paste(sh, (dx, dy))
    out.alpha_composite(img)
    return out


# ============================================================================
# Shared fish body builder (spine + profile)
# ============================================================================

class FishFrame:
    """Spine from nose (right) to tail (left). tt = 0 at the nose, 1 at the
    tail tip; s = lateral offset (positive = screen-up)."""

    def __init__(self, c, cx, cy, L, off_fn, t0=-0.3, t1=1.25, n=56):
        self.c, self.cx, self.cy, self.L = c, cx, cy, L
        self.off = off_fn
        ts = np.linspace(t0, t1, n)
        self.x_nose = cx + L * 0.5
        self.pts = [(self.x_nose - t * L, cy + off_fn(t)) for t in ts]
        dist, t, s = spine(c, self.pts)
        self.tt = t0 + t * (t1 - t0)
        self.s = s
        self.dist = dist

    def point(self, t):
        return self.x_nose - t * self.L, self.cy + self.off(t)

    def angle(self, t):
        x0, y0 = self.point(t - 0.01)
        x1, y1 = self.point(t + 0.01)
        return math.atan2(y1 - y0, x1 - x0)   # direction nose->tail


def fin_fan(c, base, ang, length, width, col_in, col_out, alpha=0.7, rays=9, bend=0.2,
            glow=None, wave=0.0, phase=0.0):
    """Translucent rounded fin fan from base along ang (radians, image space)."""
    dx, dy = math.cos(ang), math.sin(ang)
    px, py = -dy, dx
    bx, by = base
    pts = [(bx + dx * length * t + px * length * bend * t * t + px * wave * length * math.sin(t * 5 + phase) * t,
            by + dy * length * t + py * length * bend * t * t + py * wave * length * math.sin(t * 5 + phase) * t)
           for t in np.linspace(0, 1, 16)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = width + 6
    L = Layer(c, min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)
    dist, t, s = spine(L, pts)
    prof = width * np.sin(np.pi * clamp01(t * 0.92 + 0.08) ** 0.55) ** 0.8
    d = dist - prof
    u = s / np.maximum(prof, 0.5)
    ray = 0.5 + 0.5 * np.cos(u * rays * math.pi * 0.5)
    col = mix(rgb(col_in), rgb(col_out), smoothstep(0.1, 1.0, t)[..., None])
    col = col * (0.85 + 0.2 * ray)[..., None]
    if glow is not None:
        halo(L, d, rgb(glow), width * 0.8, 0.4)
    a = L.cover(d) * alpha * (0.75 + 0.25 * ray)
    L.over(clamp01(col), a)
    L.over(WHITE, L.cover(np.abs(d + 0.6) - 0.6) * 0.45 * smoothstep(0.3, 0.9, t))
    L.commit()


# ============================================================================
# Top-down fish
# ============================================================================

def koi_pattern(tt, u, patches, wob_seed=0):
    m = np.zeros_like(tt)
    for (t0, u0, rt, ru, ph) in patches:
        wob = 1 + 0.18 * np.sin(tt * 31 + u * 7 + ph) + 0.1 * np.sin(u * 13 - tt * 17 + ph * 2)
        k = np.hypot((tt - t0) / rt, (u - u0) / ru)
        m = np.maximum(m, smoothstep(1.0 * wob, 0.82 * wob, k))
    return m


SPECIES = {
    'koi_orange': dict(L=156, W=0.145, tb=0.70, tailw=0.24, fork=0.2, amp=0.08, nose=0.6, peak=0.28,
                       base='#fbfbf6', patch='#ff7a1c', patch2='#ffb24a', fin_in='#fff6ec', fin_out='#ffd2a6',
                       patches=[(0.22, 0.25, 0.14, 0.9, 0.3), (0.45, -0.2, 0.12, 0.9, 1.4), (0.58, 0.5, 0.08, 0.6, 2.2),
                                (0.06, 0.0, 0.07, 0.5, 0.9)],
                       pect=0.34, flow=0.12, canvas=(228, 144), barbels=True),
    'koi_white': dict(L=150, W=0.145, tb=0.70, tailw=0.24, fork=0.2, amp=0.08, nose=0.6, peak=0.28,
                      base='#fdfdfb', patch='#e8262e', patch2='#ff6a5a', fin_in='#ffffff', fin_out='#e6f2ff',
                      patches=[(0.12, 0.0, 0.08, 0.7, 0.2), (0.4, 0.35, 0.09, 0.75, 1.0), (0.55, -0.3, 0.07, 0.7, 2.0)],
                      gold=[(0.27, -0.3, 0.07, 0.6, 0.5)], pect=0.34, flow=0.12, canvas=(222, 144), barbels=True),
    'fish_yellow': dict(L=112, W=0.24, tb=0.74, tailw=0.2, fork=0.1, amp=0.06, nose=0.32, peak=0.4,
                        base='#ffe019', patch='#ffe019', patch2='#ffe019', fin_in='#ffe94a', fin_out='#ffc400',
                        patches=[], pect=0.20, flow=0.0, canvas=(164, 124), barbels=False, tang='yellow'),
    'fish_blue': dict(L=116, W=0.23, tb=0.74, tailw=0.2, fork=0.1, amp=0.06, nose=0.32, peak=0.4,
                      base='#1f6ff0', patch='#0b1640', patch2='#0b1640', fin_in='#2a7fff', fin_out='#123a9a',
                      patches=[], pect=0.20, flow=0.0, canvas=(166, 124), barbels=False, tang='blue'),
}


def draw_fish(name, frame):
    sp = SPECIES[name]
    W, H = sp['canvas']
    c = Canvas(W, H, ss=3)
    L = sp['L']
    cx, cy = W / 2 - L * 0.04, H / 2
    ph = 2 * math.pi * frame / 4
    A = sp['amp'] * L

    def off(t):
        tc = min(max(t, 0.0), 1.25)
        return A * (tc ** 2.0 * math.sin(ph - 4.2 * tc) - 0.12 * math.sin(ph + 0.6) * (1 - min(tc, 1)))

    F = FishFrame(c, cx, cy, L, off)
    tt, s = F.tt, F.s
    tb, Wb = sp['tb'], sp['W'] * L
    # body half-width profile
    b = clamp01(tt / tb)
    nr, pk = sp['nose'], sp.get('peak', 0.3)
    front = np.sqrt(clamp01(1 - ((b - pk) / pk) ** 2)) ** (1.0 - 0.4 * nr)
    back = 0.15 + 0.85 * np.cos(np.pi / 2 * clamp01((b - pk) / (1 - pk))) ** 0.85
    w = Wb * np.where(b < pk, front, back)
    w = np.where(tt > tb, Wb * 0.15 * clamp01(1 - (tt - tb) / 0.06), w)
    w = np.maximum(w, 0.3)
    body = np.where(tt < 0, np.hypot(s, L * tt), np.abs(s) - w)
    body = np.maximum(body, (tt - tb - 0.05) * L)
    u = clamp01(np.abs(s) / w) * np.sign(s)
    flow = sp['flow']

    # ---- tail fin (fan seen from above) ----------------------------------
    tb0 = tb - 0.05
    tf = clamp01((tt - tb0) / (1 - tb0))
    fw = sp['tailw'] * L * tf ** 0.75 * (0.8 + 0.2 * math.cos(ph - 4.2))
    fw = fw * (1 + flow * np.sin(tt * 26 - ph * 2))
    fu = np.abs(s) / np.maximum(fw, 0.5)
    t_edge = 1.0 + flow * 0.4 - sp['fork'] * (1 - clamp01(fu)) ** 1.3
    tail = np.maximum(np.maximum(np.abs(s) - fw, (tt - t_edge) * L), (tb0 - tt) * L)
    ray = 0.5 + 0.5 * np.cos(s / np.maximum(tt - tb0 + 0.04, 0.02) / L * 40)
    tcol = mix(rgb(sp['fin_in']), rgb(sp['fin_out']), smoothstep(0.2, 1.0, tf)[..., None])
    if sp.get('tang') == 'blue':
        tcol = mix(rgb('#ffd21a'), rgb('#ffb000'), tf[..., None])
        tcol = mix(tcol, rgb('#0b1640'), (smoothstep(0.85, 0.98, fu) * 0.8)[..., None])
    tcol = tcol * (0.82 + 0.22 * ray)[..., None]
    talpha = 0.68 if flow else 0.85

    # ---- pectoral + pelvic fins (under the body) ------------------------
    flap = math.sin(ph) * 0.22
    for side in (-1, 1):
        for tpos, ln, wd, spread, alpha in [(0.24, sp['pect'] * L, sp['pect'] * L * 0.42, 0.75, 0.8),
                                            (0.5, sp['pect'] * L * 0.55, sp['pect'] * L * 0.24, 0.55, 0.75)]:
            bx_, by_ = F.point(tpos)
            wloc = float(Wb * 0.8)
            ang0 = F.angle(tpos)
            ang = ang0 + side * (spread + (flap if tpos < 0.3 else -flap * 0.5))
            # side=-1 -> screen-up side
            nx, ny = math.cos(ang0 - math.pi / 2), math.sin(ang0 - math.pi / 2)
            base = (bx_ + side * nx * wloc * 0.6, by_ + side * ny * wloc * 0.6)
            ang = ang0 - side * (spread + (flap if tpos < 0.3 else -flap * 0.5))
            fin_fan(c, base, ang, ln, wd, sp['fin_in'], sp['fin_out'] if not sp.get('tang') == 'blue' else '#1a4fc8',
                    alpha=alpha * (0.85 if flow else 1.0), rays=7, bend=0.15 * side, wave=flow * 0.3, phase=ph)

    c.over(clamp01(tcol), c.cover(tail) * talpha)
    c.over(WHITE, c.cover(np.abs(tail + 0.6) - 0.6) * 0.35 * smoothstep(0.1, 0.35, tf))

    # ---- body -------------------------------------------------------------
    hgt = np.sqrt(clamp01(1 - (s / w) ** 2)) * w * 0.8 * (body < 1)
    n = normals(c, hgt)
    au = np.abs(u)
    col = np.broadcast_to(rgb(sp['base']), tt.shape + (3,)).copy()
    if sp['patches']:
        m = koi_pattern(tt, u, sp['patches'])
        pc = mix(rgb(sp['patch']), rgb(sp['patch2']), (0.5 + 0.5 * u * 0.5)[..., None])
        col = mix(col, pc, m[..., None])
    if sp.get('gold'):
        g = koi_pattern(tt, u, sp['gold'])
        col = mix(col, rgb('#ffc94a'), (g * 0.9)[..., None])
    if sp.get('tang') == 'yellow':
        col = mix(rgb('#fff04a'), rgb('#ffcc00'), (au ** 2)[..., None])
        # white scalpel spine near the tail
        spn = np.hypot((tt - 0.66) / 0.035, (np.abs(u) - 0.55) / 0.25) - 1
        col = mix(col, WHITE, (smoothstep(0.1, -0.2, spn))[..., None])
    if sp.get('tang') == 'blue':
        col = gradient_map(clamp01(1 - au), [(0.0, rgb('#0d3fb0')), (0.5, rgb('#1f74f2')), (1.0, rgb('#4aa8ff'))])
        # black palette band on both sides
        band = np.abs(np.abs(u) - 0.62 + 0.18 * np.sin(tt * 9)) - 0.17
        col = mix(col, rgb('#0a1236'), (smoothstep(0.04, -0.04, band) * smoothstep(0.08, 0.2, tt)
                                         * smoothstep(0.75, 0.6, tt))[..., None])
        col = mix(col, rgb('#ffd21a'), (smoothstep(0.62, 0.7, tt) * smoothstep(0.5, 0.2, au))[..., None])
    # subtle scales
    sc = np.sin(tt * L / 4.2 + au * 6) * np.sin(u * 11)
    col = col * (1 - 0.05 * sc * smoothstep(0.12, 0.3, tt) * (1 - au))[..., None]
    lam = lambert(n)
    shade = 0.62 + 0.45 * lam
    col = col * shade[..., None]
    col = mix(col, rgb('#2a6f9a'), (au ** 4 * 0.25)[..., None])
    col = col + spec(n, 50)[..., None] * 0.65 + spec(n, 10)[..., None] * 0.08
    # glossy stripe along the back
    stripe = np.exp(-((u - 0.28) / 0.13) ** 2) * smoothstep(0.02, 0.15, tt) * smoothstep(0.8, 0.45, tt)
    col = col + stripe[..., None] * 0.28
    c.over(clamp01(col), c.cover(body))
    # dorsal fin ridge seen from above
    if sp.get('tang') or True:
        dr = op_inter(np.abs(s + 0.5) - (1.4 if not sp.get('tang') else 2.0),
                      op_inter((0.28 - tt) * L, (tt - 0.68) * L))
        dcol = rgb(sp['fin_out']) * 0.8 if not sp.get('tang') == 'blue' else rgb('#0a1236')
        c.over(dcol, c.cover(dr) * 0.45)
    # eyes on the sides of the head
    for side in (-1, 1):
        ex_, ey_ = F.point(0.085)
        ang0 = F.angle(0.085)
        nx, ny = math.cos(ang0 - math.pi / 2), math.sin(ang0 - math.pi / 2)
        wl = float(Wb * 0.55)
        exx, eyy = ex_ + side * nx * wl, ey_ + side * ny * wl
        er = max(2.2, L * 0.022)
        c.over(rgb('#101a2a'), c.cover(sd_circle(c, exx, eyy, er)))
        c.over(WHITE, c.cover(sd_circle(c, exx - er * 0.3, eyy - er * 0.35, er * 0.38)) * 0.95)
    if sp.get('barbels'):
        for side in (-1, 1):
            x0, y0 = F.point(0.01)
            pts = [(x0 - 2 + 6 * t, y0 + side * (2 + 7 * t) + side * 2 * t * t) for t in np.linspace(0, 1, 6)]
            dist, t_, s_ = spine(c, pts)
            c.over(rgb('#f3d6bd'), c.cover(dist - 0.7 * (1 - t_)) * 0.8)
    img = c.image()
    return drop_shadow(img, 5, 7, 4, 0.18)


for _n in SPECIES:
    FAMILIES[_n] = ((lambda nm: (lambda f: draw_fish(nm, f)))(_n), 4)


# ============================================================================
# Sky fish (side view, glassy)
# ============================================================================

SKY = {
    'skyfish_aqua': dict(L=150, H=0.24, canvas=(250, 168), tail_len=0.42, tail_w=0.36, fork=0.25,
                         body=[(0.0, '#eafffd'), (0.35, '#7ff2ff'), (0.65, '#45b8ff'), (0.85, '#a48bff'), (1.0, '#ff9fe6')],
                         fin='#8ff8ff', fin2='#c9a6ff', glow='#7ff8ff', dorsal=0.3, pect=0.33, long=False),
    'skyfish_koi': dict(L=118, H=0.30, canvas=(270, 200), tail_len=0.75, tail_w=0.5, fork=0.5,
                        body=[(0.0, '#ffe7a0'), (0.3, '#ffb03a'), (0.6, '#ff7a1c'), (0.85, '#ff4f6a'), (1.0, '#ffb3e6')],
                        fin='#ffc08a', fin2='#ff6fb8', glow='#ffb08a', dorsal=0.36, pect=0.48, long=True),
}


def draw_skyfish(name, frame):
    sp = SKY[name]
    W, H = sp['canvas']
    c = Canvas(W, H, ss=3)
    L = sp['L']
    TLn = sp['tail_len']
    cx = W / 2 + L * (1 + TLn) / 2 - L * 0.5
    cy = H / 2 - (6 if sp['long'] else 0)
    ph = 2 * math.pi * frame / 4
    A = 0.045 * L

    def off(t):
        tc = max(t, 0.0)
        return A * (tc ** 1.6 * math.sin(ph - 3.2 * tc)) - A * 0.25 * math.sin(ph + 0.8)

    t1 = 1.0 + sp['tail_len'] + 0.1
    F = FishFrame(c, cx, cy, L, off, t1=t1, n=60)
    tt, s = F.tt, F.s
    Hb = sp['H'] * L
    b = clamp01(tt)
    nr, pk = 0.5, 0.33
    front = np.sqrt(clamp01(1 - ((b - pk) / pk) ** 2)) ** 0.8
    back = 0.14 + 0.86 * np.cos(np.pi / 2 * clamp01((b - pk) / (1 - pk))) ** 0.85
    h = Hb * np.where(b < pk, front, back)
    h = np.maximum(h, 0.3)
    h0 = 1.0
    body = np.where(tt < 0, np.hypot(s, L * tt), np.abs(s) - h)
    body = np.maximum(body, (tt - 1.02) * L)
    u = np.clip(s / h, -1, 1)
    glow_c = rgb(sp['glow'])

    # ---- tail ------------------------------------------------------------
    tb0 = 0.9
    TL = sp['tail_len']
    tf = clamp01((tt - tb0) / TL)
    fw = sp['tail_w'] * L * np.sin(np.pi * 0.5 * clamp01(tf * 1.6)) ** 0.8 * (0.75 + 0.25 * math.cos(ph - 3.2))
    if sp['long']:
        fw = fw * (1 + 0.14 * np.sin(tt * 14 - ph * 2 + s / L * 6))
    fu = np.abs(s) / np.maximum(fw, 0.5)
    t_edge = tb0 + TL - sp['fork'] * TL * (1 - clamp01(fu)) ** 1.1
    tail = np.maximum(np.maximum(np.abs(s) - fw, (tt - t_edge) * L), (tb0 - tt) * L)

    def fin_paint(sdf, along, col_a, col_b, alpha=0.62, rays=0.0):
        halo(c, sdf, glow_c, 14, 0.4)
        col = mix(rgb(col_a), rgb(col_b), clamp01(along)[..., None])
        r = 0.5 + 0.5 * np.cos(rays) if np.ndim(rays) else 1.0
        col = col * (0.8 + 0.28 * r)[..., None] if np.ndim(rays) else col
        a = c.cover(sdf) * alpha * ((0.7 + 0.3 * r) if np.ndim(rays) else 1.0)
        c.over(clamp01(col), a)
        c.over(WHITE, c.cover(np.abs(sdf + 0.7) - 0.7) * 0.6)
        c.add(rgb(col_a), c.cover(sdf) * 0.12)

    # far-side pectoral fin (behind body)
    flap = math.sin(ph) * 0.35
    px_, py_ = F.point(0.3)
    a0 = F.angle(0.3)
    fin_fan(c, (px_ - 4, py_ + Hb * 0.25), a0 + 0.95 + flap * 0.6, sp['pect'] * L * 0.85, sp['pect'] * L * 0.26,
            sp['fin'], sp['fin2'], alpha=0.4, rays=6, bend=0.1, glow=sp['glow'], wave=0.06 if sp['long'] else 0.0,
            phase=ph)
    ray_t = (s / np.maximum(tt - tb0 + 0.05, 0.03)) / L * 30
    fin_paint(tail, tf, sp['fin'], sp['fin2'], 0.6, ray_t)
    # dorsal fin
    dt = clamp01((tt - 0.22) / 0.5)
    dh = sp['dorsal'] * L * np.sin(np.pi * dt) ** 0.7 * (1 - 0.4 * dt) * (1 + 0.1 * np.sin(tt * 20 - ph * 2))
    if sp['long']:
        dh = dh * (1 + 0.5 * dt)
    dors = np.maximum(np.maximum(h * 0.7 - s, s - (h * 0.7 + dh)), np.maximum((0.22 - tt) * L, (tt - 0.72) * L))
    fin_paint(dors, dt, sp['fin'], sp['fin2'], 0.55, (tt * L) / 2.8)
    # ventral / anal fins
    for t0, t1_, size in [(0.38, 0.55, 0.16), (0.62, 0.8, 0.14)]:
        vt = clamp01((tt - t0) / (t1_ - t0))
        vh = size * L * np.sin(np.pi * vt) ** 0.7 * (1.8 if sp['long'] else 1.0) * (1 + 0.15 * np.sin(tt * 18 - ph * 2))
        ven = np.maximum(np.maximum(-s - (h * 0.75 + vh), s + h * 0.6), np.maximum((t0 - tt) * L, (tt - t1_) * L))
        fin_paint(ven, vt, sp['fin'], sp['fin2'], 0.5, (tt * L) / 2.6)

    # ---- glass body --------------------------------------------------------
    hgt = np.sqrt(clamp01(1 - (s / h) ** 2)) * h * (body < 1)
    n = normals(c, hgt)
    fres = (1 - n[..., 2]) ** 1.6
    iri = (0.35 * n[..., 0] + 0.45 * tt + 0.4 * (-n[..., 1]) * 0.5 + 0.3 + 0.25 * fres) % 1.0
    col = gradient_map(iri, [(p, rgb(cc)) for p, cc in sp['body']])
    if sp['long']:
        # koi: white glassy patches
        pm = koi_pattern(tt, u, [(0.15, 0.5, 0.14, 0.7, 0.4), (0.55, 0.3, 0.1, 0.9, 1.7)])
        col = mix(col, rgb('#fff8f0'), (pm * 0.75)[..., None])
    col = mix(col, WHITE, (fres * 0.45)[..., None])
    col = col * (0.75 + 0.35 * lambert(n))[..., None]
    cov = c.cover(body)
    c.over(clamp01(col), cov * clamp01((0.68 if sp['long'] else 0.5) + 0.4 * fres))
    # glowing core along the spine
    core = np.exp(-(s / (h * 0.45 + 1e-3)) ** 2) * smoothstep(-0.05, 0.2, tt) * smoothstep(1.0, 0.6, tt)
    c.add(mix(glow_c, WHITE, 0.4), core * cov * 0.35)
    # gill line
    gx, gy = F.point(0.22)
    gill = np.abs(np.hypot(c.X - gx - L * 0.07, (c.Y - gy) * 0.8) - L * 0.1) - 0.8
    c.over(WHITE, c.cover(gill) * cov * 0.4 * smoothstep(0.1, -0.6, u * 0 + (np.abs(c.Y - gy) / (Hb * 0.8) - 1)))
    # specular
    c.add(WHITE, spec(n, 60) * cov * 0.9)
    hl = op_inter(sd_ellipse(c, F.point(0.3)[0], F.point(0.3)[1] - Hb * 0.5, L * 0.2, Hb * 0.16), body + 2)
    c.over(WHITE, c.cover(hl, 3) * 0.6)
    c.over(WHITE, c.cover(np.abs(body + 0.8) - 0.8) * 0.65)
    # eye
    ex, ey = F.point(0.11)
    ey -= Hb * 0.12
    er = L * 0.045
    c.over(rgb('#e9fbff'), c.cover(sd_circle(c, ex, ey, er * 1.35)) * 0.9)
    en = sphere_normals(c, ex, ey, er)
    c.over(clamp01(mix(rgb('#0a1a3a'), rgb('#2a4f9a'), (1 - lambert(en))[..., None] * 0.5) + spec(en, 30)[..., None]),
           c.cover(sd_circle(c, ex, ey, er)))
    c.over(WHITE, c.cover(sd_circle(c, ex - er * 0.35, ey - er * 0.35, er * 0.38)))
    # near-side pectoral fin (in front)
    fin_fan(c, (px_ + 2, py_ + Hb * 0.35), a0 + 0.75 + flap, sp['pect'] * L, sp['pect'] * L * 0.3,
            sp['fin'], sp['fin2'], alpha=0.55, rays=6, bend=0.12, glow=sp['glow'], wave=0.08 if sp['long'] else 0.0,
            phase=ph)
    # sparkles + trailing bubbles
    sparkle(c, F.point(0.25)[0], F.point(0.25)[1] - Hb * 0.55, 9, 0.8)
    fade_edges(c, 3)
    return c.image()


for _n in SKY:
    FAMILIES[_n] = ((lambda nm: (lambda f: draw_skyfish(nm, f)))(_n), 4)


# ============================================================================
# Blue morpho butterfly (top-down)
# ============================================================================

def draw_butterfly(frame):
    W = H = 96
    c = Canvas(W, H, ss=4)
    cx, cy = W / 2, H / 2
    o = 1.0 if frame == 0 else 0.3
    # remap x so wings fold toward the body
    Xs = cx + (c.X - cx) / o
    v = view(c, Xs, c.Y)
    halo(c, sd_circle(c, cx, cy, 20), rgb('#6fd0ff'), 26, 0.2 * o)
    for side in (-1, 1):
        # hind wing then fore wing
        for (wx, wy, rx, ry, rot, k) in [(15, 10, 14, 13, 0.5, 0), (19, -8, 21, 14, -0.45, 1)]:
            ccx, ccy = cx + side * wx, cy + wy
            ca, sa = math.cos(rot * side), math.sin(rot * side)
            dx, dy = v.X - ccx, v.Y - ccy
            lx, ly = dx * ca + dy * sa, -dx * sa + dy * ca
            kk = np.hypot(lx / rx, ly / ry)
            d = (kk - 1) * min(rx, ry)
            if k == 1:
                d = np.maximum(d, -(np.hypot(v.X - (cx + side * 46), v.Y - (cy - 32)) - 18))
            rr = np.hypot((v.X - cx) / 36, (v.Y - cy) / 30)
            col = gradient_map(clamp01(rr), [(0.0, rgb('#0a2a8a')), (0.25, rgb('#1d6dff')), (0.6, rgb('#3fc0ff')),
                                             (0.8, rgb('#7fe8ff')), (0.86, rgb('#0b1430')), (1.0, rgb('#0b1430'))])
            # black border along the outer margin
            border = smoothstep(-3.5, -2.0, d)
            col = mix(col, rgb('#0b1430'), border[..., None])
            if o < 1:
                col = col * 0.72 + rgb('#3a2f6a') * 0.12
            # iridescent sheen
            sh = np.exp(-((ly + lx * 0.4 * side) / (ry * 0.35)) ** 2) * (1 - border)
            col = col + sh[..., None] * rgb('#a8f4ff') * 0.35
            c.over(clamp01(col), c.cover(d))
            # white margin dots
            if k == 1:
                for j in range(4):
                    a = -0.9 + j * 0.45
                    dxx = ccx + side * (math.cos(a) * rx * 0.86)
                    dyy = ccy + math.sin(a) * ry * 0.86
                    c.over(WHITE, c.cover(sd_circle(v, dxx, dyy, 1.2)) * 0.9 * c.cover(d))
            c.over(WHITE, c.cover(np.abs(d + 0.5) - 0.4) * 0.25)
    # glossy wing highlight
    sheen(c, op_union(sd_ellipse(v, cx - 19, cy - 9, 20, 13), sd_ellipse(v, cx + 19, cy - 9, 20, 13)),
          cx - 18 * o, cy - 14, 9 * o + 1, 4, 0.5)
    # body
    bd = sd_capsule(c, cx, cy - 12, cx, cy + 16, 3.2, 2.0)
    bn = sphere_normals(c, cx, cy, 3.5, 18)
    c.over(clamp01(mix(rgb('#0a0f22'), rgb('#3a4f7a'), lambert(bn)[..., None]) + spec(bn, 30)[..., None] * 0.6),
           c.cover(bd))
    c.over(rgb('#141a30'), c.cover(sd_circle(c, cx, cy - 14, 3.4)))
    for side in (-1, 1):
        pts = [(cx + side * (1 + 8 * t), cy - 16 - 12 * t - 2 * t * t) for t in np.linspace(0, 1, 8)]
        dist, t_, s_ = spine(c, pts)
        c.over(rgb('#141a30'), c.cover(dist - 0.6))
        c.over(rgb('#141a30'), c.cover(sd_circle(c, pts[-1][0], pts[-1][1], 1.3)))
    fade_edges(c, 2)
    return c.image()


FAMILIES['butterfly'] = (draw_butterfly, 2)


# ============================================================================
# Runner
# ============================================================================

def _job(arg):
    name, f = arg
    fn, _ = FAMILIES[name]
    img = fn(f)
    save(img, f'Creatures/{name}_{f}.png')
    check_padding(img, f'{name}_{f}')
    return name, f, img.size


def contact_sheet():
    os.makedirs(PREV, exist_ok=True)
    rows = []
    for name, (_, nf) in FAMILIES.items():
        ims = [Image.open(os.path.join(ART, f'Creatures/{name}_{f}.png')) for f in range(nf)]
        scale = 2 if name == 'butterfly' else 1
        ims = [im.resize((im.width * scale, im.height * scale), Image.LANCZOS) for im in ims]
        rows.append(ims)
    gap = 10
    Wd = max(sum(im.width + gap for im in r) for r in rows) + gap
    Ht = sum(max(im.height for im in r) + gap for r in rows) + gap
    for bg, tag in [((40, 190, 215), 'turq'), ((14, 24, 52), 'navy')]:
        sheet = Image.new('RGBA', (Wd * 1, Ht), bg + (255,))
        y = gap
        for r in rows:
            x = gap
            for im in r:
                sheet.alpha_composite(im, (x, y))
                x += im.width + gap
            y += max(im.height for im in r) + gap
        sheet.convert('RGB').save(os.path.join(PREV, f'creatures_{tag}.png'))


def main():
    from multiprocessing import Pool
    names = sys.argv[1:] or list(FAMILIES)
    jobs = [(n, f) for n in names for f in range(FAMILIES[n][1])]
    with Pool(8) as p:
        res = p.map(_job, jobs)
    for name, f, size in res:
        print(f'{name}_{f}: {size[0]}x{size[1]}')
    contact_sheet()


if __name__ == '__main__':
    main()
