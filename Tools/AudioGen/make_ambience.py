"""
make_ambience.py -- seamless 24 s stereo ambience loops for AquaScape.

  amb_ocean.wav : lagoon by day -- slow wave swells (pink noise through a filter that opens
                  with each swell), small laps/splashes after each crest, low surf bed.
  amb_city.wav  : glass city -- soft wandering wind, faint glass hum drone, sparse wind chimes.
  amb_night.wav : Moonpool -- gentle water lapping, subtle cricket chirps, sparse celesta twinkles.

All three are built circularly (wrapped events, circular filters/reverb, loop-periodic LFOs
and drones snapped to whole cycles per loop), so they repeat without a seam. Every tonal
element uses D major pentatonic so the ambience never clashes with the music.
"""

import os
import time

import numpy as np

from synth import (SR, TWO_PI, ns, midi_hz, dbamp, tvec, loop_hz, sine, noise, pink_noise,
                   smooth_step, env_ar, env_perc, release_tail, g_lp, g_hp, g_bp, g_peak,
                   fft_filter, stft_filter, dc_block, make_ir, reverb, pingpong, pan, place,
                   peak, rms, write_wav, glass_bell, celesta)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "Assets", "AquaScape", "Audio", "Music"))

L = 24 * SR                      # 1,058,400 samples
LS = L / SR
TARGET_RMS_DB = -25.0
PEAK_LIMIT_DB = -4.0
PENTA_HIGH = [86, 88, 90, 93, 95, 98, 100]     # D6 E6 F#6 A6 B6 D7 E7


def stereo_noise(seed, corr=0.35, pink=True):
    """Two noise channels with partial correlation (wide but not disjointed)."""
    gen = pink_noise if pink else (lambda n, s: noise(n, s))
    a, b, c = gen(L, seed), gen(L, seed + 1), gen(L, seed + 2)
    return np.stack([np.sqrt(1 - corr) * a + np.sqrt(corr) * c,
                     np.sqrt(1 - corr) * b + np.sqrt(corr) * c], 1)


def wave_envelope(seed, count, rise=(1.3, 2.2), fall=(1.2, 1.9), amp=(0.6, 1.0)):
    """Intensity curve of `count` swells spread around the loop (wrapped)."""
    rng = np.random.default_rng(seed)
    E = np.zeros(L)
    crests = []
    spacing = L / count
    for k in range(count):
        pos = int(k * spacing + rng.uniform(-0.2, 0.2) * spacing)
        r = rng.uniform(*rise)
        n = ns(r + 5.0)
        t = tvec(n)
        e = np.where(t < r, smooth_step(t / r) ** 1.5, np.exp(-(t - r) / rng.uniform(*fall)))
        a = rng.uniform(*amp)
        place(E, e * a, pos, wrap=True)
        crests.append((pos + ns(r)) % L)
    return E, crests


def wash(E, seed, base_fc, span_fc, floor=0.12, hp=60.0):
    """Noise whose loudness AND brightness follow the intensity envelope E."""
    x = stereo_noise(seed) * (floor + E)[:, None]
    tg = np.arange(L) / SR

    def g(t, f):
        e = np.interp(t, tg, E)
        fc = base_fc + span_fc * e
        return g_lp(f, fc, 2) * g_hp(f, hp, 1)

    return stft_filter(x, g, n_win=2048, hop=512, circular=True)


def laps(crests, seed, level=0.5, band=(700, 3500), count=(2, 4)):
    """Little splashes/laps shortly after each wave crest."""
    rng = np.random.default_rng(seed)
    out = np.zeros((L, 2))
    for c in crests:
        for k in range(int(rng.integers(count[0], count[1] + 1))):
            n = ns(0.5)
            t = tvec(n)
            burst = fft_filter(noise(n, int(rng.integers(1e6))),
                               lambda f: g_bp(f, band[0] * rng.uniform(0.8, 1.2), band[1], 2))
            burst *= smooth_step(t / 0.025) * np.exp(-t / rng.uniform(0.07, 0.16))
            pos = c + ns(rng.uniform(0.05, 0.9))
            place(out, pan(burst * level * rng.uniform(0.4, 1.0), rng.uniform(-0.6, 0.6)), pos, wrap=True)
    return out


def finish(x, name):
    x = dc_block(x, 20.0, circular=True)
    x *= dbamp(TARGET_RMS_DB) / rms(x)
    if peak(x) > dbamp(PEAK_LIMIT_DB):
        x *= dbamp(PEAK_LIMIT_DB) / peak(x)
    write_wav(os.path.join(OUT, name), x)
    print("  %-14s %.2fs  peak %.2f dBFS  rms %.1f dBFS" % (name, len(x) / SR, 20 * np.log10(peak(x)),
                                                        20 * np.log10(rms(x))))


# --------------------------------------------------------------------------------------
def ocean():
    E, crests = wave_envelope(seed=3, count=5)
    surf = wash(E, seed=100, base_fc=280, span_fc=2300)
    E2, _ = wave_envelope(seed=4, count=7, amp=(0.2, 0.45))           # smaller cross-waves
    surf2 = wash(E2, seed=200, base_fc=350, span_fc=1500) * 0.6
    bed = fft_filter(stereo_noise(300), lambda f: g_lp(f, 260, 2) * g_hp(f, 40, 1), circular=True) * 0.12
    lap = laps(crests, seed=5, level=0.35)
    mix = surf + surf2 + bed + lap
    ir = make_ir(1.6, 1.0, predelay=0.01, bright=5000, seed=81)
    return reverb(mix, ir, wet=0.15, dry=1.0, circular=True)


def city():
    t = tvec(L)
    w = stereo_noise(400)
    k1, k2 = loop_hz(0.09, LS), loop_hz(0.04, LS)
    tg = np.arange(L) / SR

    def wind_filter(tt, f):
        fc = 650 * 2 ** (0.8 * np.sin(TWO_PI * k1 * tt) + 0.45 * np.sin(TWO_PI * k2 * tt + 1.3))
        return g_bp(f, fc / 1.7, fc * 1.7, 2) * g_peak(f, fc, 4.0, 0.3)

    wind = stft_filter(w, wind_filter, n_win=2048, hop=512, circular=True)
    gust = 0.55 + 0.45 * np.sin(TWO_PI * loop_hz(0.07, LS) * t + 0.5) * np.sin(TWO_PI * loop_hz(0.125, LS) * t)
    wind *= gust[:, None]
    # faint high "whistle" band riding the wind
    whistle = stft_filter(stereo_noise(450, pink=False),
                          lambda tt, f: g_peak(f, 2400 * 2 ** (0.3 * np.sin(TWO_PI * k2 * tt)), 18.0, 0.06)
                          * g_bp(f, 1500, 4000, 2) * 0.05, n_win=2048, hop=512, circular=True)
    # glass hum: D3 / A3 / D4 drones with slow beating, swelling gently
    hum = np.zeros((L, 2))
    for j, m in enumerate((50, 57, 62)):
        f = loop_hz(float(midi_hz(m)), LS)
        fb = f + loop_hz(0.2 + 0.07 * j, LS)
        sw = 0.6 + 0.4 * np.sin(TWO_PI * loop_hz(0.05 + 0.02 * j, LS) * t + j)
        hum += pan((np.sin(TWO_PI * f * t) + 0.7 * np.sin(TWO_PI * fb * t)) * sw, -0.5 + 0.5 * j) * 0.035
    # sparse wind chimes
    rng = np.random.default_rng(12)
    chimes = np.zeros((L, 2))
    pos = 0.0
    while pos < LS - 1.0:
        pos += rng.uniform(3.5, 6.5)
        if pos > LS:
            break
        p0 = rng.uniform(-0.7, 0.7)
        tt = pos
        for k in range(int(rng.integers(3, 7))):
            m = int(rng.choice(PENTA_HIGH))
            b = glass_bell(midi_hz(m), 2.5, decay=0.9, bright=0.7, seed=int(rng.integers(1e6)))
            place(chimes, pan(b * rng.uniform(0.25, 0.6), p0 + rng.uniform(-0.2, 0.2)), ns(tt), wrap=True)
            tt += rng.uniform(0.07, 0.3)
    ir = make_ir(4.0, 3.2, predelay=0.03, bright=5000, seed=82)
    tonal = reverb(hum + chimes * 0.12, ir, wet=0.6, dry=0.5, circular=True)
    return wind * 1.0 + whistle + tonal


def night():
    E, crests = wave_envelope(seed=21, count=6, rise=(1.0, 1.8), fall=(0.9, 1.4), amp=(0.35, 0.7))
    water = wash(E, seed=500, base_fc=220, span_fc=1300, floor=0.1)
    lap = laps(crests, seed=22, level=0.22, band=(500, 2500), count=(1, 3))
    bed = fft_filter(stereo_noise(550), lambda f: g_lp(f, 200, 2) * g_hp(f, 40, 1), circular=True) * 0.08
    # crickets: bursts of 3-4 tiny chirps; each cricket sings in phrases with rests
    rng = np.random.default_rng(23)
    crick = np.zeros((L, 2))
    for ci, (fc, p) in enumerate(((4300.0, -0.55), (4850.0, 0.6), (3900.0, 0.1))):
        tt = rng.uniform(0, 2)
        while tt < LS:
            phrase_end = tt + rng.uniform(3.0, 7.0)
            while tt < phrase_end and tt < LS:
                for k in range(int(rng.integers(3, 5))):
                    n = ns(0.022)
                    tc = tvec(n)
                    ch = np.sin(TWO_PI * fc * tc) * np.sin(np.pi * tc / tc[-1]) ** 2
                    place(crick, pan(ch * (0.8 if ci < 2 else 0.5), p), ns(tt + k * 0.042), wrap=True)
                tt += rng.uniform(0.75, 1.2)
            tt = phrase_end + rng.uniform(1.5, 4.0)
    crick = fft_filter(crick, lambda f: g_lp(f, 6500, 2), circular=True)
    # sparse twinkles (celesta) with echoes
    tw = np.zeros((L, 2))
    tt = 1.0
    while tt < LS - 0.5:
        m = int(rng.choice(PENTA_HIGH))
        c = celesta(midi_hz(m), 2.0, decay=0.8, seed=int(rng.integers(1e6))) * rng.uniform(0.4, 0.8)
        place(tw, pan(c, rng.uniform(-0.6, 0.6)), ns(tt), wrap=True)
        tt += rng.uniform(2.5, 5.0)
    tw = tw + pingpong(tw.mean(1), ns(0.535), feedback=0.5, taps=5, lp_hz=3000, circular=True) * 0.5
    ir = make_ir(5.0, 4.0, predelay=0.03, bright=4500, seed=83)
    tw = reverb(tw, ir, wet=0.7, dry=0.6, circular=True)
    ir2 = make_ir(1.5, 1.0, predelay=0.01, bright=5000, seed=84)
    return reverb(water + lap + bed, ir2, wet=0.15, circular=True) + crick * 0.035 + tw * 0.11


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("amb_ocean.wav", ocean), ("amb_city.wav", city), ("amb_night.wav", night)):
        t0 = time.time()
        x = fn()
        print("rendered %s in %.1fs" % (name, time.time() - t0))
        finish(x, name)


if __name__ == "__main__":
    main()
