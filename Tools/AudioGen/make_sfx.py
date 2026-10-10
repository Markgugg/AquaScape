"""
make_sfx.py -- every AquaScape sound effect, synthesised from scratch (mono, 16-bit, 44.1 kHz).

Each sound is a small function returning a mono float array. `finish()` then removes DC,
trims leading/trailing silence, de-clicks the ends and normalises the peak.

Tonal SFX are pitched in D major pentatonic (D E F# A B) so they always sit inside the
music. The bubble collect chain climbs D5 E5 F#5 A5 B5 D6 E6 F#6 for combo streaks.
"""

import os
import time

import numpy as np

from synth import (SR, TWO_PI, ns, midi_hz, dbamp, tvec, sine, tri, saw, noise, smooth_step,
                   env_perc, env_ar, release_tail, ramp, g_lp, g_hp, g_bp, g_peak, fft_filter,
                   stft_filter, dc_block, make_ir, reverb, pan, place, peak, normalize, trim,
                   fade, write_wav, glass_bell, celesta, vibes, fm_epiano, glass_pluck,
                   supersaw, soft_clip)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "Assets", "AquaScape", "Audio", "SFX"))

ROOM = make_ir(0.9, 0.55, predelay=0.006, bright=6000, seed=201, stereo=False)   # small glassy room
HALL = make_ir(2.6, 1.9, predelay=0.018, bright=6000, seed=202, stereo=False)    # big airy space

BUBBLE_NOTES = [74, 76, 78, 81, 83, 86, 88, 90]     # D5 E5 F#5 A5 B5 D6 E6 F#6


# --------------------------------------------------------------------------------------
# small building blocks
# --------------------------------------------------------------------------------------
def buf(seconds):
    return np.zeros(ns(seconds))


def put(b, sig, at_seconds, gain=1.0):
    place(b, sig * gain, ns(at_seconds))
    return b


def bloop(f, dur=0.07, rise=2.0, tau=0.024, glide=0.014):
    """Water-drop 'bloop': a sine whose pitch springs up from f/rise to f."""
    n = ns(dur)
    t = tvec(n)
    fr = f / rise * (1.0 + (rise - 1.0) * (1.0 - np.exp(-t / glide)))
    y = sine(fr, n) + 0.15 * sine(2 * fr, n)
    return y * env_perc(n, 0.0015, tau)


def click(dur=0.012, lo=2000, hi=9000, tau=0.0015, seed=0):
    n = ns(dur)
    t = tvec(n)
    return fft_filter(noise(n, seed), lambda f: g_bp(f, lo, hi, 2)) * np.exp(-t / tau) * smooth_step(t / 0.0003)


def swept_band(x, times, fcs, width=1.6, order=2, n_win=512, hop=128):
    """Band-pass x with a centre frequency that follows (times, fcs) breakpoints."""
    times = np.asarray(times, float)
    fcs = np.log(np.asarray(fcs, float))

    def g(t, f):
        fc = np.exp(np.interp(t, times, fcs))
        return g_bp(f, fc / width, fc * width, order)

    return stft_filter(x, g, n_win=n_win, hop=hop)


def swept_lp(x, times, fcs, order=2, n_win=512, hop=128):
    times = np.asarray(times, float)
    fcs = np.log(np.asarray(fcs, float))
    return stft_filter(x, lambda t, f: g_lp(f, np.exp(np.interp(t, times, fcs)), order), n_win=n_win, hop=hop)


def shape(n, points):
    """Piecewise envelope from (time_s, level) points, smooth between points."""
    t = tvec(n)
    pts = np.asarray(points, float)
    return np.interp(t, pts[:, 0], pts[:, 1])


def sparkle(dur, density=40, lo=3500, hi=9000, seed=0, tau=0.012):
    """Granular glitter: many tiny random high sine blips."""
    rng = np.random.default_rng(seed)
    b = buf(dur)
    for _ in range(int(density * dur)):
        f = rng.uniform(lo, hi)
        n = ns(0.04)
        t = tvec(n)
        g = np.sin(TWO_PI * f * t) * smooth_step(t / 0.002) * np.exp(-t / tau) * rng.uniform(0.3, 1.0)
        place(b, g, ns(rng.uniform(0, dur - 0.04)))
    return b


def finish(x, name, peak_db=-1.5, thresh_db=-60.0, max_len=None):
    x = dc_block(x, 25.0)
    x = trim(x, thresh_db)
    if max_len is not None and len(x) > ns(max_len):
        x = fade(x[:ns(max_len)], 0.0, min(0.08, max_len * 0.3))
    # very short transients can't be fully DC-filtered; remove the residual mean with a
    # smooth (inaudible, sub-10 Hz) window so the file averages to exactly zero
    w = np.hanning(len(x) + 2)[1:-1]
    x = x - w * (x.sum() / w.sum())
    x = normalize(x, peak_db)
    write_wav(os.path.join(OUT, name + ".wav"), x)
    return name, len(x) / SR


# --------------------------------------------------------------------------------------
# footsteps
# --------------------------------------------------------------------------------------
def footstep_plaza(i):
    """Soft tap on smooth ceramic: low heel thump + bright tap + faint ceramic ring."""
    rng = np.random.default_rng(10 + i)
    v = rng.uniform(0.93, 1.07)
    n = ns(0.11)
    t = tvec(n)
    thump = sine(150 * v * (0.65 + 0.35 * np.exp(-t / 0.012)), n) * env_perc(n, 0.001, 0.016)
    tap = click(0.11, 1500, 6500, 0.0035, seed=i) * rng.uniform(0.5, 0.7)
    ring = (np.sin(TWO_PI * 2150 * v * t) + 0.6 * np.sin(TWO_PI * 3420 * v * t)) * np.exp(-t / 0.014) * 0.06
    y = 0.8 * thump + tap + ring
    return fft_filter(y, lambda f: g_lp(f, 8000, 2))


def footstep_grass(i):
    """Soft rustle: a cluster of tiny leaf crackles over a muffled foot thud."""
    rng = np.random.default_rng(20 + i)
    b = buf(0.15)
    for k in range(int(rng.integers(6, 10))):
        n = ns(0.03)
        t = tvec(n)
        lo = rng.uniform(1500, 2600)
        c = fft_filter(noise(n, 100 * i + k), lambda f: g_bp(f, lo, 7500, 2))
        c *= smooth_step(t / 0.001) * np.exp(-t / rng.uniform(0.004, 0.011)) * rng.uniform(0.3, 1.0)
        place(b, c, ns(rng.uniform(0.0, 0.085) ** 1.3 * 2.2 if False else rng.uniform(0.0, 0.09)))
    n = len(b)
    t = tvec(n)
    thud = fft_filter(noise(n, 300 + i), lambda f: g_lp(f, 350, 2)) * env_perc(n, 0.004, 0.03) * 1.2
    swish = fft_filter(noise(n, 400 + i), lambda f: g_bp(f, 900, 5000, 1)) * env_perc(n, 0.012, 0.04) * 0.25
    return b * 0.8 + thud + swish


def footstep_glass(i):
    """Light glassy tap with a tiny ring."""
    rng = np.random.default_rng(30 + i)
    v = rng.uniform(0.96, 1.04)
    n = ns(0.16)
    t = tvec(n)
    tick = click(0.16, 3000, 11000, 0.0012, seed=50 + i) * 0.5
    ring = glass_bell(2350 * v, 0.16, decay=0.045, bright=0.6, seed=i) * 0.35
    ring += glass_bell(3520 * v * rng.uniform(0.99, 1.01), 0.16, decay=0.025, bright=0.5, seed=i + 9) * 0.15
    thump = sine(170 * v, n) * env_perc(n, 0.001, 0.012) * 0.5
    return tick + ring + thump


# --------------------------------------------------------------------------------------
# bubbles
# --------------------------------------------------------------------------------------
def bubble_collect(idx):
    """Bloop + glass chime at the combo pitch. Bright and short."""
    m = BUBBLE_NOTES[idx]
    f = float(midi_hz(m))
    b = buf(0.6)
    bf = f * 0.5 if f < 1000 else f * 0.35          # keep the bloop in a 'watery' range
    put(b, bloop(bf, 0.08, rise=1.9, tau=0.022), 0.0, 0.75)
    chime = glass_bell(f, 0.5, decay=0.16, bright=0.85, seed=idx)
    chime += 0.35 * glass_pluck(f, 0.5, 1.0, decay=0.09)
    chime += 0.22 * glass_bell(f * 2, 0.5, decay=0.07, bright=0.6, seed=idx + 20)   # sparkle octave
    put(b, chime, 0.012, 0.75)
    b = reverb(b, ROOM, wet=0.12)
    return b


def bubble_drop():
    """Losing bubbles: a descending scatter of little bloops."""
    rng = np.random.default_rng(61)
    notes = [83, 81, 78, 76, 74, 71, 69, 66, 62]
    b = buf(1.0)
    tpos = 0.0
    for k, m in enumerate(notes):
        f = float(midi_hz(m))
        g = 0.95 - 0.07 * k
        put(b, bloop(f * 0.6, 0.07, rise=1.7, tau=0.02), tpos, g)
        put(b, glass_bell(f, 0.25, decay=0.05, bright=0.5, seed=k), tpos + 0.008, 0.25 * g)
        tpos += rng.uniform(0.045, 0.075)
    return reverb(b, ROOM, wet=0.15)


# --------------------------------------------------------------------------------------
# abilities
# --------------------------------------------------------------------------------------
def pulse():
    """Aqua Pulse: soft sonar 'whoom' + an expanding shimmering glass ring."""
    dur = 1.0
    n = ns(dur)
    t = tvec(n)
    # sonar whoom: sine falling 190 -> 62 Hz with a soft swell
    whoom = sine(62 + 128 * np.exp(-t / 0.12), n) * shape(n, [(0, 0), (0.03, 1), (0.25, 0.5), (0.6, 0.0), (dur, 0)])
    whoom = soft_clip(whoom * 1.2, 1.4)
    air = swept_lp(noise(n, 71), [0, 0.05, 0.5], [2500, 1200, 200]) * shape(n, [(0, 0), (0.02, 1), (0.3, 0.2), (0.6, 0)]) * 0.35
    pf = midi_hz(74) * (1 + 0.012 * (1 - np.exp(-t / 0.2)))
    ping = (sine(pf, n) + 0.35 * sine(2 * pf, n)) * env_perc(n, 0.004, 0.25) * 0.5
    # expanding ring: D6 A6 E7 F#7 bells with rising pitch (+50 cents) and 16 Hz shimmer
    ring = np.zeros(n)
    bend = 2 ** ((50.0 / 1200.0) * (t / dur))
    for j, m in enumerate((86, 93, 100, 102)):
        f = float(midi_hz(m))
        shim = 0.65 + 0.35 * np.sin(TWO_PI * (14 + 3 * j) * t + j)
        ring += sine(f * bend, n) * shim * (0.5 ** j)
    ring *= shape(n, [(0, 0), (0.06, 1), (0.3, 0.6), (dur - 0.05, 0.0), (dur, 0)]) * 0.5
    hiss = swept_band(noise(n, 72), [0, 0.6], [2000, 9000], 1.4) * shape(n, [(0, 0), (0.08, 1), (0.6, 0)]) * 0.12
    y = 0.5 * whoom + air + ping + ring + hiss
    return reverb(y, HALL, wet=0.22)


def dash():
    """Airy whoosh with a bubbly sparkle."""
    n = ns(0.4)
    t = tvec(n)
    w = swept_band(noise(n, 81), [0, 0.12, 0.35], [500, 3200, 1200], 1.8)
    w *= shape(n, [(0, 0), (0.06, 1), (0.16, 0.7), (0.34, 0.0), (0.4, 0)])
    lowpuff = swept_lp(noise(n, 82), [0, 0.2], [700, 250]) * shape(n, [(0, 0), (0.03, 1), (0.2, 0)]) * 0.6
    b = w + lowpuff
    rng = np.random.default_rng(83)
    for k in range(5):
        f0 = rng.uniform(1200, 2400)
        put(b, bloop(f0, 0.05, rise=1.8, tau=0.012), 0.05 + 0.035 * k, 0.22)
    return reverb(b, ROOM, wet=0.1)


# --------------------------------------------------------------------------------------
# world interactions
# --------------------------------------------------------------------------------------
def clam_open():
    """Shell creak -> pop -> sparkly bubble release."""
    b = buf(1.3)
    # creak: accelerating click train through a woody/shelly resonance
    n = ns(0.36)
    t = tvec(n)
    rate = 22 + 45 * (t / t[-1]) ** 1.5
    ph = np.cumsum(rate / SR)
    imp = np.zeros(n)
    imp[np.nonzero(np.diff(np.floor(ph)) > 0)[0]] = 1.0
    creak = fft_filter(imp + 0.02 * noise(n, 91), lambda f: g_bp(f, 350, 2200, 2) * g_peak(f, 820, 9.0, 0.4)
                       * g_peak(f, 1500, 5.0, 0.3))
    creak *= shape(n, [(0, 0), (0.05, 0.6), (0.3, 1.0), (0.36, 0.0)])
    put(b, creak / (peak(creak) + 1e-9), 0.0, 0.55)
    # pop
    n = ns(0.12)
    t = tvec(n)
    pop = sine(140 + 420 * np.exp(-t / 0.018), n) * env_perc(n, 0.001, 0.035)
    pop += fft_filter(noise(n, 92), lambda f: g_lp(f, 3500, 2)) * np.exp(-t / 0.006) * 0.5
    put(b, pop, 0.36, 0.9)
    # bubbles rising + sparkle
    rng = np.random.default_rng(93)
    tp = 0.40
    for k in range(9):
        m = int(rng.choice([74, 76, 78, 81, 83, 86, 88]))
        put(b, bloop(float(midi_hz(m)) * 0.55, 0.07, rise=1.8, tau=0.02), tp, 0.45 * (1 - 0.05 * k))
        tp += rng.uniform(0.03, 0.06)
    for j, m in enumerate((93, 98, 102)):
        put(b, glass_bell(float(midi_hz(m)), 0.7, decay=0.22, seed=j), 0.45 + 0.07 * j, 0.22)
    put(b, sparkle(0.6, 45, seed=94), 0.42, 0.12)
    return reverb(b, ROOM, wet=0.15)


def shard_pickup():
    """Magical crystal sparkle arpeggio (D6 F#6 A6 D7 F#7)."""
    b = buf(1.5)
    for k, m in enumerate((86, 90, 93, 98, 102)):
        f = float(midi_hz(m))
        put(b, glass_bell(f, 1.2, decay=0.45, bright=0.85, seed=k), 0.055 * k, 0.5)
        put(b, celesta(f * 0.5, 1.0, decay=0.4, seed=k), 0.055 * k, 0.18)
    put(b, sparkle(0.9, 60, 4000, 10000, seed=101), 0.02, 0.1)
    return reverb(b, HALL, wet=0.3)[:ns(1.5)]


def beacon_light():
    """Big reward: rising shimmer swell into a bright Dmaj9 bloom (~3 s)."""
    dur = 3.4
    b = buf(dur)
    rise = 1.0
    # -- swell
    n = ns(rise + 0.1)
    t = tvec(n)
    swell = swept_band(noise(n, 111), [0, rise], [400, 7000], 1.5) * (t / t[-1]) ** 2 * 0.35
    gl = sine(ramp(n, float(midi_hz(62)), float(midi_hz(86))) * (1 + 0.006 * np.sin(TWO_PI * 6 * t)), n)
    gl *= smooth_step(t / rise) ** 2 * 0.18 * release_tail(n, 0.06)
    put(b, swell + gl, 0.0)
    # accelerating pentatonic run into the bloom
    run = [74, 76, 78, 81, 83, 86, 88, 90, 93]
    tp = 0.42
    for k, m in enumerate(run):
        put(b, glass_bell(float(midi_hz(m)), 0.5, decay=0.15, seed=k), tp, 0.18 + 0.02 * k)
        tp += 0.075 * (0.88 ** k)
    # -- bloom
    n = ns(dur - rise)
    t = tvec(n)
    env = smooth_step(t / 0.06) * (0.45 * np.exp(-t / 0.35) + 0.55 * np.exp(-t / 1.4))
    chord = [50, 57, 61, 64, 66, 69, 74]            # D3 A3 C#4 E4 F#4 A4 D5  (Dmaj9)
    pad = np.zeros(n)
    for j, m in enumerate(chord):
        pad += supersaw(float(midi_hz(m)), n, 5, 9, seed=500 + j).mean(1)
    pad = fft_filter(pad * env, lambda f: g_lp(f, 4200, 2) * g_hp(f, 90, 2))
    put(b, pad, rise, 0.35)
    for j, m in enumerate(chord[1:]):
        put(b, fm_epiano(float(midi_hz(m + 12)), 1.6, 0.8, seed=j), rise + 0.012 * j, 0.12)
    for j, m in enumerate((86, 90, 93, 100)):       # glass crown D6 F#6 A6 E7
        put(b, glass_bell(float(midi_hz(m)), 2.2, decay=0.8, bright=0.9, seed=60 + j), rise + 0.03 * j, 0.22)
    boom = sine(midi_hz(38) * (1 + 0.6 * np.exp(-t / 0.03)), n) * env_perc(n, 0.004, 0.45)
    put(b, boom, rise, 0.3)
    put(b, sparkle(1.4, 50, 4000, 10000, seed=112), rise, 0.08)
    y = reverb(b, HALL, wet=0.35)[:ns(dur)]
    tt = tvec(len(y))
    return y * np.where(tt > 2.6, smooth_step((dur - tt) / (dur - 2.6)), 1.0)


def beacon_denied():
    """Gentle 'not yet' double boop: A4 then F#4, soft and round."""
    b = buf(0.5)
    for k, m in enumerate((69, 66)):
        n = ns(0.16)
        t = tvec(n)
        f = float(midi_hz(m)) * (1 - 0.03 * (t / t[-1]))
        y = (0.7 * sine(f, n) + 0.3 * tri(f, n)) * env_perc(n, 0.006, 0.06)
        put(b, y, 0.17 * k, 1.0 if k == 0 else 0.85)
    b = fft_filter(b, lambda f: g_lp(f, 2200, 2))
    return reverb(b, ROOM, wet=0.12)


def bridge_tile():
    """Single short glass 'tink' (base pitch D6; code pitches it up per tile)."""
    n = ns(0.15)
    t = tvec(n)
    y = glass_bell(float(midi_hz(86)), 0.15, decay=0.05, bright=0.8, seed=3)
    y += click(0.15, 3000, 10000, 0.001, seed=4) * 0.3
    y += sine(float(midi_hz(74)), n) * env_perc(n, 0.001, 0.018) * 0.25
    return y * release_tail(n, 0.03)


def bridge_complete():
    """Resolution chime: A5 -> D6 -> F#6 -> A6 settling on a sparkling D chord."""
    b = buf(1.8)
    for k, m in enumerate((81, 86, 90, 93)):
        f = float(midi_hz(m))
        put(b, glass_bell(f, 1.5, decay=0.55 if k == 3 else 0.35, seed=k), 0.085 * k, 0.45)
        put(b, glass_pluck(f, 1.0, 0.7, decay=0.25), 0.085 * k, 0.2)
    for j, m in enumerate((74, 78, 81)):
        put(b, vibes(float(midi_hz(m)), 1.4, 0.7, decay=0.9), 0.34, 0.2)
    return reverb(b, HALL, wet=0.28)[:ns(1.8)]


def pylon_activate():
    """Electric-glass power-up: rising buzzy hum with crackle, then a chime."""
    dur = 1.8
    n = ns(dur)
    t = tvec(n)
    f = np.where(t < 0.9, 55 * 2 ** (t / 0.9), 110.0)
    hum = 0.6 * saw(f, n) + 0.4 * saw(f * 2.005, n)
    hum = stft_filter(hum, lambda tt, fr: g_lp(fr, np.exp(np.interp(tt, [0, 0.9, dur], np.log([180, 2600, 700]))), 2),
                      n_win=1024, hop=256)
    trem = 0.75 + 0.25 * np.sin(TWO_PI * np.cumsum(np.interp(t, [0, 0.9], [6, 22])) / SR)
    hum *= trem * shape(n, [(0, 0), (0.15, 0.5), (0.9, 1.0), (1.1, 0.55), (dur, 0.0)])
    rng = np.random.default_rng(121)
    crack = np.zeros(n)
    for _ in range(18):
        p = rng.uniform(0.1, 0.95)
        c = click(0.01, 2500, 9000, 0.0008, seed=int(rng.integers(1e6)))
        place(crack, c * rng.uniform(0.2, 0.6) * (p / 0.95), ns(p))
    glass = sine(np.interp(t, [0, 0.9], [880, 1760]), n) * shape(n, [(0, 0), (0.9, 0.12), (1.0, 0.0), (dur, 0)])
    b = 0.45 * hum + crack * 0.6 + glass
    for j, m in enumerate((81, 86, 88)):     # A5 D6 E6
        put(b, glass_bell(float(midi_hz(m)), 0.85, decay=0.35, seed=j), 0.9 + 0.04 * j, 0.32)
    return reverb(b, HALL, wet=0.22)[:ns(dur)]


def cube_push():
    """Glass block sliding on ceramic: grainy scrape + low glassy hum."""
    dur = 0.42
    n = ns(dur)
    t = tvec(n)
    rng = np.random.default_rng(131)
    jitter = np.repeat(rng.uniform(0.4, 1.0, n // 300 + 1), 300)[:n]
    jitter = np.convolve(jitter, np.ones(120) / 120, mode="same")
    scrape = fft_filter(noise(n, 132), lambda f: g_bp(f, 600, 3500, 2) * g_peak(f, 2200, 6.0, 0.3))
    env = shape(n, [(0, 0), (0.04, 1), (dur - 0.09, 0.85), (dur, 0)])
    scrape *= jitter * env
    hum = (sine(float(midi_hz(50)) * (1 + 0.004 * np.sin(TWO_PI * 7 * t)), n)
           + 0.4 * sine(float(midi_hz(62)), n)) * env * 0.35
    thunk = sine(110 * (1 + 0.5 * np.exp(-t / 0.01)), n) * env_perc(n, 0.002, 0.03) * 0.5
    return scrape * 0.6 + hum + thunk


def cube_reset():
    """Magical poof / teleport: soft noise poof + upward sparkle sweep + chime."""
    dur = 0.9
    n = ns(dur)
    t = tvec(n)
    poof = swept_lp(noise(n, 141), [0, 0.05, 0.3], [4500, 2500, 400]) * shape(n, [(0, 0), (0.008, 1), (0.25, 0.0), (dur, 0)])
    sw = sine(np.interp(t, [0, 0.35], [400, 2400]) * (1 + 0.03 * np.sin(TWO_PI * 22 * t)), n)
    sw *= shape(n, [(0, 0), (0.05, 0.3), (0.32, 0.25), (0.42, 0), (dur, 0)])
    b = poof * 0.7 + sw
    for j, m in enumerate((86, 93, 98)):
        put(b, glass_bell(float(midi_hz(m)), 0.5, decay=0.18, seed=j), 0.28 + 0.06 * j, 0.32)
    put(b, sparkle(0.5, 50, seed=142), 0.2, 0.1)
    return reverb(b, ROOM, wet=0.18)


def pad_on():
    """Pressure pad down: soft click + rising two-note chime (A5 -> D6)."""
    b = buf(0.5)
    put(b, click(0.02, 1500, 8000, 0.0015, seed=151), 0.0, 0.7)
    n = ns(0.03)
    put(b, sine(1900, n) * env_perc(n, 0.0005, 0.004), 0.0, 0.3)
    put(b, glass_bell(float(midi_hz(81)), 0.4, decay=0.12, seed=1), 0.02, 0.5)
    put(b, glass_bell(float(midi_hz(86)), 0.45, decay=0.16, seed=2), 0.085, 0.55)
    return reverb(b, ROOM, wet=0.12)


def pad_off():
    """Pressure pad released: soft click + falling two-note chime (D6 -> A5), a bit darker."""
    b = buf(0.5)
    put(b, click(0.02, 1200, 6000, 0.0015, seed=152), 0.0, 0.6)
    put(b, glass_bell(float(midi_hz(86)), 0.4, decay=0.1, bright=0.6, seed=3), 0.02, 0.45)
    put(b, glass_bell(float(midi_hz(81)), 0.45, decay=0.14, bright=0.6, seed=4), 0.085, 0.5)
    return fft_filter(reverb(b, ROOM, wet=0.12), lambda f: g_lp(f, 6000, 1))


def gate_open():
    """Glass gate dissolving/sliding open: rising band sweep + upward shimmer glissando."""
    dur = 1.6
    n = ns(dur)
    t = tvec(n)
    sweep = swept_band(noise(n, 161), [0, 1.1, dur], [300, 5000, 7000], 1.5)
    sweep *= shape(n, [(0, 0), (0.15, 0.6), (0.9, 1.0), (1.3, 0.2), (dur, 0)]) * 0.45
    slide = sine(np.interp(t, [0, 1.1], [98, 196]), n) * shape(n, [(0, 0), (0.1, 1), (1.0, 0.6), (1.3, 0), (dur, 0)]) * 0.18
    shim = np.zeros(n)
    bend = 2 ** (np.clip(t / 1.1, 0, 1) * 1.0)          # up one octave
    for j, m in enumerate((74, 78, 81, 86, 88)):
        shim += sine(float(midi_hz(m)) * bend, n) * (0.7 + 0.3 * np.sin(TWO_PI * (11 + 2 * j) * t)) * 0.7 ** j
    shim *= shape(n, [(0, 0), (0.25, 0.25), (1.1, 0.35), (1.5, 0.0), (dur, 0)])
    b = sweep + slide + shim
    for j, m in enumerate((98, 102, 105)):
        put(b, glass_bell(float(midi_hz(m)), 0.5, decay=0.2, seed=j), 1.05 + 0.06 * j, 0.15)
    return reverb(b, HALL, wet=0.25)[:ns(dur + 0.4)]


def lantern_light():
    """Soft bell + warm glow whoosh (moon lanterns)."""
    dur = 2.0
    n = ns(dur)
    t = tvec(n)
    glow = swept_lp(noise(n, 171), [0, 0.3, 1.2], [300, 1600, 350], order=2) * shape(n, [(0, 0), (0.28, 1), (1.2, 0.0), (dur, 0)])
    fwoomp = sine(110 * (1 + 0.15 * (1 - np.exp(-t / 0.2))), n) * shape(n, [(0, 0), (0.12, 1), (0.7, 0), (dur, 0)])
    b = glow * 0.45 + fwoomp * 0.4
    put(b, vibes(float(midi_hz(74)), 1.8, 0.9, decay=1.1), 0.05, 0.55)
    put(b, glass_bell(float(midi_hz(81)), 1.5, decay=0.5, bright=0.6, seed=1), 0.06, 0.25)
    put(b, celesta(float(midi_hz(90)), 1.2, decay=0.5, seed=2), 0.2, 0.15)
    return reverb(b, HALL, wet=0.3)[:ns(dur)]


def jelly_hit():
    """Bumped by a jellyfish: cute electric 'bzzt' then a soft falling 'bloop'."""
    b = buf(0.6)
    n = ns(0.16)
    t = tvec(n)
    gate = 0.5 + 0.5 * np.tanh(4 * np.sin(TWO_PI * 34 * t))
    bz = (0.6 * saw(150 * (1 + 0.02 * np.sin(TWO_PI * 60 * t)), n) + 0.4 * saw(225, n)) * gate
    bz = fft_filter(bz, lambda f: g_bp(f, 300, 3000, 2) * g_peak(f, 1200, 5.0, 0.5))
    bz *= shape(n, [(0, 0), (0.008, 1), (0.13, 0.7), (0.16, 0)])
    put(b, bz, 0.0, 0.5)
    n = ns(0.36)
    t = tvec(n)
    f = (700 * np.exp(-t / 0.15) + 330) * (1 + 0.05 * np.sin(TWO_PI * 9 * t))
    bl = (sine(f, n) + 0.2 * sine(2 * f, n)) * env_perc(n, 0.01, 0.12)
    put(b, bl, 0.12, 0.85)
    return reverb(b, ROOM, wet=0.12)


def jelly_repel():
    """Jellyfish pushed away: wobbly rising bloop."""
    n = ns(0.5)
    t = tvec(n)
    f = (300 + 420 * (1 - np.exp(-t / 0.08))) * (1 + 0.08 * np.sin(TWO_PI * 11 * t) * np.exp(-t / 0.3))
    y = (sine(f, n) + 0.25 * sine(2 * f, n) + 0.1 * tri(0.5 * f, n)) * env_perc(n, 0.008, 0.15)
    y += 0.12 * glass_bell(float(midi_hz(81)), 0.5, decay=0.12, seed=5) * smooth_step((t - 0.05) / 0.01)
    return reverb(y, ROOM, wet=0.12)


def portal_open():
    """Mystical swell: blooming D-A-E-F# chord, rising filter, drone and twinkles (~2.4 s)."""
    dur = 2.4
    n = ns(dur)
    t = tvec(n)
    env = shape(n, [(0, 0), (1.2, 1.0), (1.7, 0.8), (dur, 0.0)])
    chord = np.zeros(n)
    for j, m in enumerate((62, 69, 76, 78, 86)):
        chord += supersaw(float(midi_hz(m)), n, 4, 8, seed=600 + j).mean(1) * (0.8 ** j)
    chord = stft_filter(chord, lambda tt, f: g_lp(f, np.exp(np.interp(tt, [0, 1.3, dur], np.log([250, 3500, 1200]))), 2),
                        n_win=1024, hop=256) * env
    drone = sine(float(midi_hz(38)), n) * env * 0.15
    swell = swept_band(noise(n, 181), [0, 1.3], [500, 6000], 1.6) * shape(n, [(0, 0), (1.2, 1.0), (1.4, 0), (dur, 0)]) * 0.25
    b = chord * 0.5 + drone + swell
    rng = np.random.default_rng(182)
    for k in range(7):
        m = int(rng.choice([86, 88, 90, 93, 95, 98]))
        put(b, celesta(float(midi_hz(m)), 0.8, decay=0.35, seed=k), 0.9 + 0.13 * k, 0.15)
    return reverb(b, HALL, wet=0.35)[:ns(dur + 0.3)]


def portal_enter():
    """Dive into moonlit water: falling whoosh, soft plunge, bubbles, sparkle tail."""
    dur = 1.9
    b = buf(dur)
    n = ns(0.6)
    t = tvec(n)
    wh = swept_band(noise(n, 191), [0, 0.45], [4500, 350], 1.8) * shape(n, [(0, 0), (0.12, 1), (0.4, 0.7), (0.6, 0)])
    put(b, wh, 0.0, 0.6)
    n = ns(0.5)
    t = tvec(n)
    plunge = sine(60 + 160 * np.exp(-t / 0.06), n) * env_perc(n, 0.004, 0.14)
    plunge += swept_lp(noise(n, 192), [0, 0.3], [2500, 300]) * env_perc(n, 0.003, 0.08) * 0.6
    put(b, plunge, 0.33, 0.8)
    rng = np.random.default_rng(193)
    tp = 0.38
    for k in range(12):
        put(b, bloop(rng.uniform(350, 1100), 0.06, rise=1.8, tau=0.018), tp, 0.3 * (1 - 0.05 * k))
        tp += rng.uniform(0.025, 0.06)
    for j, m in enumerate((98, 93, 90, 86)):        # D7 A6 F#6 D6 descending twinkle tail
        put(b, celesta(float(midi_hz(m)), 1.0, decay=0.4, seed=j), 0.6 + 0.14 * j, 0.25)
    return reverb(b, HALL, wet=0.33)[:ns(dur)]


def zone_enter():
    """Gentle chime swell when entering a new area."""
    dur = 2.4
    n = ns(dur)
    t = tvec(n)
    env = shape(n, [(0, 0), (0.6, 1.0), (1.4, 0.6), (dur, 0)])
    pad = np.zeros(n)
    for j, m in enumerate((62, 66, 69, 76)):
        f = float(midi_hz(m))
        pad += (sine(f, n) + 0.3 * tri(f * 1.002, n)) * 0.8 ** j
    b = pad * env * 0.25
    for k, m in enumerate((74, 81, 88, 90)):         # D5 A5 E6 F#6
        put(b, glass_bell(float(midi_hz(m)), 1.4, decay=0.5, bright=0.8, seed=k), 0.25 + 0.12 * k, 0.35)
    return reverb(b, HALL, wet=0.35)[:ns(dur)]


# --------------------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------------------
def ui_hover():
    n = ns(0.06)
    t = tvec(n)
    y = glass_bell(float(midi_hz(100)), 0.06, decay=0.012, bright=0.5, seed=7)
    y += click(0.06, 4000, 12000, 0.0006, seed=8) * 0.3
    return y * release_tail(n, 0.01)


def ui_click():
    n = ns(0.1)
    t = tvec(n)
    pop = sine(560 + 900 * np.exp(-t / 0.009), n) * env_perc(n, 0.0008, 0.018)
    body = sine(300, n) * env_perc(n, 0.001, 0.01) * 0.4
    tick = click(0.1, 3000, 10000, 0.0008, seed=9) * 0.35
    shine = glass_bell(float(midi_hz(93)), 0.1, decay=0.025, seed=10) * 0.2
    return pop + body + tick + shine


def ui_open():
    n = ns(0.4)
    t = tvec(n)
    w = swept_band(noise(n, 211), [0, 0.25], [800, 5000], 1.6) * shape(n, [(0, 0), (0.12, 1), (0.3, 0.2), (0.4, 0)]) * 0.5
    b = w
    put(b, glass_bell(float(midi_hz(81)), 0.3, decay=0.08, seed=1), 0.06, 0.3)
    put(b, glass_bell(float(midi_hz(88)), 0.3, decay=0.1, seed=2), 0.12, 0.35)
    return reverb(b, ROOM, wet=0.1)


def ui_close():
    n = ns(0.36)
    t = tvec(n)
    w = swept_band(noise(n, 212), [0, 0.22], [5000, 800], 1.6) * shape(n, [(0, 0), (0.05, 1), (0.25, 0.15), (0.36, 0)]) * 0.5
    b = w
    put(b, glass_bell(float(midi_hz(88)), 0.3, decay=0.07, bright=0.7, seed=3), 0.03, 0.3)
    put(b, glass_bell(float(midi_hz(81)), 0.3, decay=0.09, bright=0.7, seed=4), 0.09, 0.33)
    return reverb(b, ROOM, wet=0.1)


# --------------------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    done = []
    for i in range(4):
        done.append(finish(footstep_plaza(i), "footstep_plaza_%d" % (i + 1), -3.0))
        done.append(finish(footstep_grass(i), "footstep_grass_%d" % (i + 1), -3.0))
        done.append(finish(footstep_glass(i), "footstep_glass_%d" % (i + 1), -3.0))
    for i in range(8):
        done.append(finish(bubble_collect(i), "bubble_%d" % (i + 1), -1.5, -50, max_len=0.45))
    # (function, file name, peak dBFS, max length in s -- reverb tails beyond it are faded)
    jobs = [
        (bubble_drop, "bubble_drop", -1.5, 0.85), (pulse, "pulse", -1.0, 1.1), (dash, "dash", -1.5, 0.42),
        (clam_open, "clam_open", -1.5, 1.2), (shard_pickup, "shard_pickup", -1.5, 1.4),
        (beacon_light, "beacon_light", -1.0, 3.2), (beacon_denied, "beacon_denied", -2.0, 0.5),
        (bridge_tile, "bridge_tile", -2.0, 0.15), (bridge_complete, "bridge_complete", -1.5, 1.6),
        (pylon_activate, "pylon_activate", -1.5, 1.8), (cube_push, "cube_push", -2.0, 0.42),
        (cube_reset, "cube_reset", -1.5, 0.8), (pad_on, "pad_on", -2.0, 0.5), (pad_off, "pad_off", -2.5, 0.5),
        (gate_open, "gate_open", -1.5, 1.8), (lantern_light, "lantern_light", -1.5, 1.8),
        (jelly_hit, "jelly_hit", -1.5, 0.55), (jelly_repel, "jelly_repel", -1.5, 0.5),
        (portal_open, "portal_open", -1.5, 2.6), (portal_enter, "portal_enter", -1.5, 1.9),
        (zone_enter, "zone_enter", -2.0, 2.4),
        (ui_hover, "ui_hover", -4.0, 0.06), (ui_click, "ui_click", -2.5, 0.1),
        (ui_open, "ui_open", -3.0, 0.42), (ui_close, "ui_close", -3.0, 0.38),
    ]
    for fn, name, pk, mx in jobs:
        done.append(finish(fn(), name, pk, -54.0, max_len=mx))
    for name, d in done:
        print("  %-20s %6.3f s" % (name, d))
    print("%d SFX in %.1fs" % (len(done), time.time() - t0))


if __name__ == "__main__":
    main()
