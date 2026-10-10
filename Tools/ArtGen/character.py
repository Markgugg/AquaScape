"""
character.py - renders the AquaScape chrome explorer ("Aqua") in three views
(down / up / side) with idle and walk cycles.

Output: Assets/AquaScape/Art/Character/<anim>_<dir>_<frame>.png
"""
import math
import os
import sys
import numpy as np
from aqua import *

OUT = os.path.join(os.path.dirname(__file__), '../../Assets/AquaScape/Art/Character')
W, H = 192, 224
CX = 96

# --- palette -----------------------------------------------------------------
CYAN = rgb('#5ff3ff')
CYAN_DEEP = rgb('#16b9ff')
GLOW = rgb('#7ff8ff')

HELMET_SKY = [
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
    return mat_chrome(n, sky=HELMET_SKY)


def white_plastic(n):
    return mat_plastic(n, '#fbfdff', '#93abcf', gloss=0.85)


def grey_plastic(n):
    return mat_plastic(n, '#dfe7f2', '#7d91b3', gloss=0.6)


def glow_dot(c, cx, cy, r, core='#e9ffff', strength=0.9):
    d = sd_circle(c, cx, cy, r)
    c.glow(d, GLOW, r * 1.6, strength * 0.55)
    n = sphere_normals(c, cx, cy, r)
    col = mix(CYAN_DEEP, rgb(core), clamp01(1 - np.hypot(c.X - cx, c.Y - cy) / r)[..., None])
    col = col + spec(n, 60)[..., None]
    c.over(clamp01(col), c.cover(d))


# --- body parts ------------------------------------------------------------------

def draw_shadow(c, scale=1.0):
    d = sd_ellipse(c, CX, 207, 36 * scale, 9 * scale)
    c.shadow(d, 7, 0.32, (0.02, 0.18, 0.30))


def draw_boot(c, x, y, facing, lift=0.0):
    """Rounded futuristic boot; `facing` is 'front' or 'side'."""
    y -= lift
    if facing == 'side':
        d = op_smooth_union(sd_box(c, x + 4, y + 2, 15, 8, 7.5), sd_circle(c, x - 2, y - 3, 9), 4)
    else:
        d = op_smooth_union(sd_box(c, x, y + 2, 12.5, 8.5, 8), sd_circle(c, x, y - 4, 9), 4)
    paint_shaded(c, d, white_plastic, bevel=7)
    # glowing cyan sole line
    sole = op_inter(d, -(c.Y - (y + 6.5)))
    paint(c, op_inter(sole, (c.Y - (y + 10.5))), CYAN, 0.95)
    c.glow(op_inter(sole, c.Y - (y + 10.5)), GLOW, 3, 0.25)
    # chrome toe band
    band = op_inter(d, np.abs(c.Y - (y - 1)) - 2.0)
    paint_shaded(c, band, chrome, bevel=2, alpha=0.9)


def draw_leg(c, x0, y0, x1, y1):
    d = sd_capsule(c, x0, y0, x1, y1, 7.5, 7)
    paint_shaded(c, d, grey_plastic, bevel=6)


def draw_arm(c, sx, sy, hx, hy, far=False):
    d = sd_capsule(c, sx, sy, hx, hy, 8.5, 7.5)
    paint_shaded(c, d, white_plastic if not far else grey_plastic, bevel=7)
    # cyan cuff
    cuff = sd_capsule(c, hx + (sx - hx) * 0.25, hy + (sy - hy) * 0.25, hx, hy, 8.2, 7.6)
    cuff = op_inter(cuff, -sd_capsule(c, hx, hy, hx, hy, 5.5))
    hand = sd_circle(c, hx, hy + 3, 8.5)
    paint_shaded(c, hand, chrome, normals_override=sphere_normals(c, hx, hy + 3, 8.5))
    ring = op_inter(sd_capsule(c, sx, sy, hx, hy, 9), np.abs(np.hypot(c.X - hx, c.Y - hy) - 9) - 1.6)
    paint(c, ring, CYAN, 0.9)


def draw_torso(c, cx, cy, view, breath=0.0):
    hw = 24 if view != 'side' else 18
    hh = 21 + breath
    d = op_smooth_union(sd_box(c, cx, cy, hw, hh, 15),
                        sd_ellipse(c, cx, cy + hh * 0.35, hw + 2, hh * 0.8), 6)
    paint_shaded(c, d, white_plastic, bevel=14)
    # waist trim
    trim = op_inter(d, np.abs(c.Y - (cy + hh * 0.55)) - 2.2)
    paint_shaded(c, trim, chrome, bevel=2, alpha=0.95)
    if view == 'down':
        # chest power light
        ring = sd_circle(c, cx, cy - 2, 9.5)
        paint_shaded(c, ring, chrome, normals_override=sphere_normals(c, cx, cy - 2, 9.5))
        glow_dot(c, cx, cy - 2, 6.5)
    elif view == 'up':
        # little backpack with a cyan stripe
        bp = sd_box(c, cx, cy - 1, 17, 16, 9)
        paint_shaded(c, bp, grey_plastic, bevel=7)
        stripe = op_inter(bp, np.abs(c.X - cx) - 2.5)
        paint(c, stripe, CYAN, 0.9)
        c.glow(stripe, GLOW, 4, 0.25)
    else:
        # side vent light
        glow_dot(c, cx + 9, cy - 3, 4.5)
    return d


def draw_headphone(c, x, y, rx, ry, glow_side=0.0):
    d = sd_ellipse(c, x, y, rx, ry)
    paint_shaded(c, d, chrome, normals_override=sphere_normals(c, x, y, rx, ry))
    inner = sd_ellipse(c, x + glow_side, y, rx * 0.62, ry * 0.62)
    paint_shaded(c, inner, white_plastic, normals_override=sphere_normals(c, x + glow_side, y, rx * 0.62, ry * 0.62))
    ring = np.abs(sd_ellipse(c, x + glow_side, y, rx * 0.45, ry * 0.45)) - 1.6
    paint(c, ring, CYAN, 1.0)
    c.glow(ring, GLOW, 4, 0.45)
    glow_dot(c, x + glow_side, y, min(rx, ry) * 0.22, strength=0.6)


def draw_helmet(c, hx, hy, view, blink=0.0, squash=1.0, glint=0.0):
    R = 58
    ry = R * squash
    helmet = sd_ellipse(c, hx, hy, R, ry)
    hn = sphere_normals(c, hx, hy, R, ry)

    # neck shadow onto the body is handled by caller; here the helmet itself
    if view == 'side':
        draw_headphone(c, hx - 50, hy + 8, 9, 19)  # far cup peeking out (behind)

    paint_shaded(c, helmet, chrome, normals_override=hn)
    inner_shadow(c, helmet, 10, 0.22, (0.30, 0.42, 0.62))

    if view == 'down':
        vx, vy, vrx, vry = hx, hy + 6, 45, 35
    elif view == 'side':
        vx, vy, vrx, vry = hx + 26, hy + 6, 30, 34
    else:
        vx = None

    if vx is not None:
        visor = sd_ellipse(c, vx, vy, vrx, vry)
        visor = op_smooth_union(visor, sd_box(c, vx, vy + 4, vrx * 0.92, vry * 0.8, vry * 0.6), 6)
        if view == 'side':
            visor = op_inter(visor, helmet + 3)
        # white bezel
        bezel = visor - 5.5
        if view == 'side':
            bezel = op_inter(bezel, helmet + 1)
        paint_shaded(c, bezel, white_plastic, bevel=5)
        # glass
        vn = sphere_normals(c, vx, vy, vrx * 1.25, vry * 1.35)
        t = clamp01((c.Y - (vy - vry)) / (2 * vry))
        col = gradient_map(t, [(0.0, rgb('#071447')), (0.45, rgb('#0d2f9e')),
                               (0.8, rgb('#1d6ff0')), (1.0, rgb('#4fd2ff'))])
        fres = (1 - vn[..., 2]) ** 2
        col = mix(col, rgb('#76cfff'), (fres * 0.5)[..., None])
        col = col + spec(vn, 140)[..., None] * 1.4
        c.over(clamp01(col), c.cover(visor))
        inner_shadow(c, visor, 6, 0.55, (0.01, 0.04, 0.18))

        # glowing eyes
        if view == 'down':
            eyes = [(vx - 15, vy + 2), (vx + 15, vy + 2)]
            erx = 5.6
        else:
            eyes = [(vx + 10, vy + 2)]
            erx = 4.6
        ery = max(1.4, 8.5 * (1 - blink))
        for ex, ey in eyes:
            e = sd_ellipse(c, ex, ey, erx, ery)
            c.glow(e, GLOW, 5, 0.55)
            paint(c, e, rgb('#c8fbff'))
        # cheek blush glow
        if view == 'down' and blink < 0.5:
            for ex in (vx - 27, vx + 27):
                b = sd_ellipse(c, ex, vy + 14, 6, 3.5)
                c.over(rgb('#7fe4ff'), c.cover(b, 3) * 0.35)

        # reflections: big soft window highlight + small sparkle
        hl = op_inter(sd_ellipse(c, vx - vrx * 0.28, vy - vry * 0.42, vrx * 0.55, vry * 0.32), visor + 3)
        c.over(np.array([1, 1, 1.0]), c.cover(hl, 4) * 0.42 * smoothstep(vy + 4, vy - vry, c.Y))
        highlight_arc(c, vx, vy, vrx - 6, vry - 6, 1.6, 200, 250, 0.85)
        highlight_arc(c, vx, vy, vrx - 5, vry - 5, 1.2, 20, 70, 0.35, color=(0.5, 0.95, 1.0))
        s = sd_circle(c, vx + vrx * 0.45, vy - vry * 0.38, 2.6)
        paint(c, s, np.array([1, 1, 1.0]), 0.95)
        if glint > 0:
            # animated specular sweep across the visor
            gx = vx - vrx + glint * vrx * 2
            band = op_inter(np.abs((c.X - gx) + (c.Y - vy) * 0.6) - 5, visor + 2)
            c.over(np.array([1, 1, 1.0]), c.cover(band, 3) * 0.45)
    else:
        # back of the helmet: vent strip with soft cyan light
        vent = sd_box(c, hx, hy + 30, 16, 5, 5)
        paint_shaded(c, vent, white_plastic, bevel=4)
        glow_dot(c, hx - 8, hy + 30, 2.6, strength=0.5)
        glow_dot(c, hx, hy + 30, 2.6, strength=0.5)
        glow_dot(c, hx + 8, hy + 30, 2.6, strength=0.5)

    # crisp rim + top highlight on the helmet
    highlight_arc(c, hx, hy, R - 8, ry - 8, 2.2, 205, 255, 0.75)
    s = sd_ellipse(c, hx - 24, hy - 34, 9, 5)
    c.over(np.array([1, 1, 1.0]), c.cover(s, 3) * 0.8)

    # headphones
    if view in ('down', 'up'):
        draw_headphone(c, hx - R + 2, hy + 8, 12, 21, glow_side=-3)
        draw_headphone(c, hx + R - 2, hy + 8, 12, 21, glow_side=3)
    else:
        draw_headphone(c, hx - 8, hy + 8, 19, 22)


def render(view, pose):
    """pose: bob, lL, lR (foot lift), sL, sR (stride), aL, aR (arm swing),
    blink, squash, breath, glint"""
    c = Canvas(W, H, ss=3)
    bob = pose.get('bob', 0.0)
    draw_shadow(c, pose.get('shadow', 1.0))

    by = 160 + bob           # torso centre
    hy = 92 + bob * 1.25      # helmet centre (helmet lags slightly)
    if view == 'side':
        # far arm and far leg first
        sF, sN = pose.get('sL', 0), pose.get('sR', 0)
        draw_leg(c, CX - 4, by + 16, CX - 4 + sF, 192 - pose.get('lL', 0))
        draw_boot(c, CX - 4 + sF, 198, 'side', pose.get('lL', 0))
        draw_arm(c, CX - 6, by - 12, CX - 6 + pose.get('aL', 0), by + 10, far=True)
        draw_leg(c, CX + 4, by + 16, CX + 4 + sN, 192 - pose.get('lR', 0))
        draw_boot(c, CX + 4 + sN, 199, 'side', pose.get('lR', 0))
        torso = draw_torso(c, CX - 2, by, view, pose.get('breath', 0))
        c.shadow(op_inter(sd_ellipse(c, CX + 4, hy + 56, 40, 14), torso), 6, 0.35, (0.25, 0.35, 0.55))
        draw_arm(c, CX + 2, by - 12, CX + 2 + pose.get('aR', 0), by + 11)
    else:
        for side, key in ((-1, 'L'), (1, 'R')):
            lift = pose.get('l' + key, 0)
            draw_leg(c, CX + side * 11, by + 14, CX + side * 12, 191 - lift)
            draw_boot(c, CX + side * 13, 197, 'front', lift)
        torso = draw_torso(c, CX, by, view, pose.get('breath', 0))
        c.shadow(op_inter(sd_ellipse(c, CX, hy + 54, 44, 14), torso), 6, 0.35, (0.25, 0.35, 0.55))
        for side, key in ((-1, 'L'), (1, 'R')):
            sw = pose.get('a' + key, 0)
            draw_arm(c, CX + side * 23, by - 12, CX + side * 32, by + 10 + sw)

    draw_helmet(c, CX, hy, view, pose.get('blink', 0), pose.get('squash', 1.0), pose.get('glint', 0))
    return c.image()


def idle_poses(n=8):
    poses = []
    for i in range(n):
        p = i / n * 2 * math.pi
        poses.append(dict(bob=math.sin(p) * 2.2, breath=math.sin(p) * 0.8,
                          aL=math.sin(p) * 1.0, aR=math.sin(p) * 1.0,
                          blink=1.0 if i == 5 else 0.0,
                          shadow=1.0 - math.sin(p) * 0.03))
    return poses


def walk_poses(view, n=8):
    poses = []
    for i in range(n):
        p = i / n * 2 * math.pi
        s = math.sin(p)
        if view == 'side':
            poses.append(dict(bob=-abs(math.cos(p)) * 4 + 2,
                              sL=-s * 13, sR=s * 13,
                              lL=max(0, -math.cos(p)) * 7 * (s < 0.3),
                              lR=max(0, math.cos(p)) * 7 * (s > -0.3),
                              aL=s * 10, aR=-s * 10, breath=0))
        else:
            poses.append(dict(bob=-abs(s) * 4 + 2,
                              lL=max(0, s) * 9, lR=max(0, -s) * 9,
                              aL=-s * 5, aR=s * 5,
                              shadow=1.0 - abs(s) * 0.05))
    return poses


def _job(args):
    view, anim, i, pose = args
    render(view, pose).save(f'{OUT}/{anim}_{view}_{i}.png')


def main():
    from multiprocessing import Pool
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] or ['down', 'up', 'side']
    jobs = []
    for view in only:
        jobs += [(view, 'idle', i, p) for i, p in enumerate(idle_poses())]
        jobs += [(view, 'walk', i, p) for i, p in enumerate(walk_poses(view))]
    with Pool() as pool:
        pool.map(_job, jobs)
    print('rendered', len(jobs), 'frames')


if __name__ == '__main__':
    main()
