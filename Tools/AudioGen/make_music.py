"""
make_music.py -- renders AquaScape's adaptive music stems + level-complete jingle.

Musical setting
  Key      : D major pentatonic (D E F# A B)
  Tempo    : 84 BPM, 4/4
  Loop     : 8 bars = 32 beats = 32*60/84 s = exactly 1,008,000 samples @ 44.1 kHz
             (one beat = 31,500 samples, so every grid position is an integer sample)
  Chords   : | Dmaj9 | Dmaj9 | Bm9 | Bm9 | Gmaj7(#11) | Gmaj7(#11) | A6sus | Aadd9 |

Stems (all exactly LOOP samples, stereo, seamless, designed to be played in sync):
  music_pad.wav     base layer (always on)         - detuned saw pad + shimmer + air
  music_keys.wav    layer 1 (after beacon 1)       - FM e-piano comping + round sub bass
  music_arp.wav     layer 2 (after beacon 2)       - glass pluck arpeggio w/ ping-pong + soft lo-fi drums
  music_melody.wav  layer 3 (after beacon 3)       - vibraphone lead melody
  music_night.wav   alternate base for night zone  - darker sine pad, huge reverb, celesta twinkles
  jingle_complete.wav  ~4 s level-complete fanfare in D (not a loop)

Seamlessness: every event is mixed into a circular buffer (tails wrap onto the start), the
pad filter LFOs complete whole cycles per loop, and reverb/delay/chorus are circular.
"""

import os
import time

import numpy as np

from synth import (SR, TWO_PI, ns, midi_hz, dbamp, tvec, loop_hz, sine, tri, noise,
                   smooth_step, env_ar, release_tail, g_lp, g_hp, g_bp, g_peak,
                   fft_filter, stft_filter, dc_block, make_ir, reverb, chorus, pingpong,
                   pan, place, peak, rms, normalize, fade, write_wav, supersaw, sub_bass,
                   fm_epiano, glass_pluck, vibes, celesta, glass_bell, soft_kick, shaker,
                   brush, soft_clip)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "Assets", "AquaScape", "Audio", "Music"))

BPM = 84
BEAT = SR * 60 // BPM            # 31500 samples, exact
BAR = 4 * BEAT
LOOP = 32 * BEAT                 # 1,008,000 samples
LOOP_S = LOOP / SR               # 22.857142... s
BEAT_S = 60.0 / BPM

# start beat, length (beats), name, bass root, pad voicing, e-piano voicing, arp note pool
SEGMENTS = [
    (0, 8, "Dmaj9", 38, [50, 57, 61, 64, 66], [61, 64, 66, 69], [69, 74, 76, 78, 81]),
    (8, 8, "Bm9", 35, [47, 54, 57, 61, 62], [61, 62, 66, 69], [71, 74, 78, 81, 83]),
    (16, 8, "Gmaj7#11", 43, [43, 50, 54, 59, 61], [59, 61, 62, 66], [71, 74, 78, 83, 86]),
    (24, 4, "A6sus", 45, [45, 52, 54, 62, 64], [62, 64, 66, 69], [69, 71, 74, 76, 81]),
    (28, 4, "Aadd9", 45, [45, 52, 57, 59, 61, 64], [61, 64, 69, 71], [69, 71, 76, 81, 83]),
]

# Lead melody (beat, length in beats, MIDI note, velocity) -- D major pentatonic only.
# A simple question/answer phrase; the last two pickups lead back into the first F#5.
MELODY = [
    (0, 1.5, 78, 1.0), (1.5, 0.5, 76, 0.75), (2, 1, 74, 0.8), (3, 1, 81, 0.9),
    (4, 3, 78, 0.95), (7.5, 0.5, 69, 0.7),
    (8, 1.5, 74, 1.0), (9.5, 0.5, 76, 0.75), (10, 1, 78, 0.8), (11, 1, 83, 0.9),
    (12, 3, 81, 0.95), (15.5, 0.5, 78, 0.7),
    (16, 1.5, 83, 1.0), (17.5, 0.5, 81, 0.75), (18, 1, 78, 0.8), (19, 1, 86, 0.95),
    (20, 1.5, 81, 0.9), (21.5, 0.5, 78, 0.75), (22, 2, 76, 0.85),
    (24, 1, 78, 0.85), (25, 1, 76, 0.75), (26, 1, 74, 0.8), (27, 1, 76, 0.8),
    (28, 2.5, 76, 0.9), (31, 0.5, 74, 0.7), (31.5, 0.5, 76, 0.75),
]

# Relative balance of the stems (RMS in dBFS before the global master scale)
TARGET_RMS_DB = {"pad": -20.0, "keys": -21.5, "arp": -22.5, "melody": -21.0, "night": -20.0}
MASTER_PEAK_DB = -3.0            # full mix (base + all layers) peaks here


def b2s(beats):
    """Beats -> samples (exact on the grid)."""
    return int(round(beats * BEAT))


def new_loop():
    return np.zeros((LOOP, 2))


# --------------------------------------------------------------------------------------
# stems
# --------------------------------------------------------------------------------------
def render_pad():
    """Warm lush detuned pad: 6-voice supersaw per chord tone, slow attack, breathing
    low-pass filter, airy shimmer partials two octaves up and a whisper of noise."""
    buf = new_loop()
    shimmer = new_loop()
    for i, (sb, nb, name, root, pad_notes, _, _) in enumerate(SEGMENTS):
        start = b2s(sb) - ns(0.12)
        n = b2s(nb) + ns(2.3)
        env = env_ar(n, 1.5, 2.5)[:, None]
        for j, m in enumerate(pad_notes):
            f = midi_hz(m)
            v = supersaw(f, n, voices=6, detune_cents=12, seed=100 * i + j)
            v += pan(tri(f * 0.5 if m > 52 else f, n, 0.3 * j), 0.0) * 0.22   # body
            place(buf, v * env * 0.5, start, wrap=True)
        # shimmer: the two top chord tones + 2 octaves, slow independent tremolo
        t = tvec(n)
        for j, m in enumerate(sorted(pad_notes)[-2:]):
            f = midi_hz(m + 24)
            trem = 0.55 + 0.45 * np.sin(TWO_PI * (0.23 + 0.11 * j) * t + j * 2.0)
            s = sine(f, n) * trem * env_ar(n, 2.0, 2.5)
            place(shimmer, pan(s, -0.6 if j == 0 else 0.6) * 0.06, start, wrap=True)

    lfo_hz = 2.0 / LOOP_S           # two filter "breaths" per loop
    seg_s = 8 * BEAT_S

    def pad_filter(t, f):
        lfo = np.sin(TWO_PI * lfo_hz * t)
        ph = (t % seg_s) / seg_s
        fc = 820.0 * 2 ** (0.75 * lfo) * (1.0 + 0.45 * np.sin(np.pi * ph))
        return g_lp(f, fc, 2) * g_peak(f, fc, 3.0, 0.5) * g_hp(f, 70, 2)

    buf = stft_filter(buf, pad_filter, circular=True)
    # airy noise "breath" band, swelling twice per loop
    air = np.stack([noise(LOOP, 11), noise(LOOP, 12)], 1)
    air = fft_filter(air, lambda f: g_bp(f, 5000, 12000, 2), circular=True)
    t = tvec(LOOP)
    air *= (0.5 + 0.5 * np.sin(TWO_PI * lfo_hz * t - 1.0))[:, None] * 0.012
    mix = buf + shimmer + air
    mix = chorus(mix, rate=loop_hz(0.22, LOOP_S), depth_ms=3.0, base_ms=15, mix=0.4, circular=True)
    ir = make_ir(4.5, 3.4, predelay=0.02, bright=5000, seed=21)
    return reverb(mix, ir, wet=0.55, dry=0.8, circular=True)


def render_keys():
    """Soft FM e-piano comping on the chords + a round sub bass on the roots."""
    ep = new_loop()
    bass = new_loop()
    rng = np.random.default_rng(5)
    pat_a = [(0.0, 1.4, 1.0), (2.5, 1.3, 0.7)]
    pat_b = [(0.0, 0.9, 0.85), (1.5, 0.9, 0.6), (3.0, 0.9, 0.7)]
    bass_pat = [(0.0, 2.3, 1.0), (2.5, 1.3, 0.75)]
    bar_index = 0
    for sb, nb, name, root, _, keys_notes, _ in SEGMENTS:
        for b in range(nb // 4):
            bar0 = sb + 4 * b
            pat = pat_a if bar_index % 2 == 0 else pat_b
            for (bt, dur, vel) in pat:
                for k, m in enumerate(keys_notes):
                    v = vel * (0.8 + 0.2 * rng.random()) * (0.8 if k == 0 else 1.0)
                    note = 0.5 * fm_epiano(midi_hz(m), dur * BEAT_S, v, seed=k)
                    st = b2s(bar0 + bt) + k * ns(0.011) + int(rng.integers(-60, 60))
                    place(ep, pan(note, -0.35 + 0.7 * k / (len(keys_notes) - 1)), st, wrap=True)
            for (bt, dur, vel) in bass_pat:
                s = sub_bass(midi_hz(root), dur * BEAT_S, vel, attack=0.025, release=0.15)
                place(bass, pan(s, 0.0), b2s(bar0 + bt), wrap=True)
            bar_index += 1
    # gentle tremolo-chorus and a soft roll-off for warmth
    ep = fft_filter(ep, lambda f: g_lp(f, 7000, 1) * g_hp(f, 150, 1) * g_peak(f, 1500, 3.0, 1.0), circular=True)
    ep = chorus(ep, rate=loop_hz(0.6, LOOP_S), depth_ms=1.8, base_ms=9, mix=0.45, circular=True)
    ir = make_ir(3.0, 2.2, predelay=0.015, bright=5000, seed=31)
    ep = reverb(ep, ir, wet=0.35, dry=0.9, circular=True)
    bass = fft_filter(bass, lambda f: g_lp(f, 380, 2), circular=True)
    return ep + bass * 0.3


def render_arp():
    """Glass pluck arpeggio (8ths, pentatonic chord notes) with dotted-8th ping-pong,
    plus a soft lo-fi groove: round kick, brushed snare, swung shaker 16ths."""
    arp = np.zeros(LOOP)
    arp_st = new_loop()
    rng = np.random.default_rng(9)
    patterns = [[0, 1, 2, 3, 4, 3, 2, 1], [0, 2, 1, 3, 2, 4, 3, 1]]
    bar_index = 0
    for sb, nb, name, root, _, _, pool in SEGMENTS:
        for b in range(nb // 4):
            pat = patterns[bar_index % 2]
            for k in range(8):
                beat = sb + 4 * b + 0.5 * k
                vel = 1.0 if k == 0 else (0.8 if k % 2 == 0 else 0.62)
                vel *= 0.92 + 0.08 * rng.random()
                note = glass_pluck(midi_hz(pool[pat[k]]), 0.9, vel)
                st = b2s(beat)
                place(arp, note, st, wrap=True)
                place(arp_st, pan(note, 0.25 if k % 2 else -0.25), st, wrap=True)
            bar_index += 1
    echoes = pingpong(arp, int(0.75 * BEAT), feedback=0.5, taps=6, lp_hz=4000, circular=True)
    ir = make_ir(3.2, 2.6, predelay=0.02, bright=6000, seed=41)
    arp_bus = reverb(arp_st + 0.5 * echoes, ir, wet=0.35, dry=0.85, circular=True)
    arp_bus = fft_filter(arp_bus, lambda f: g_hp(f, 200, 2), circular=True)

    # drums -- deliberately soft
    kick = new_loop()
    sn = new_loop()
    hat = new_loop()
    for bar in range(8):
        b0 = 4 * bar
        place(kick, pan(soft_kick(0.9), 0), b2s(b0), wrap=True)
        place(kick, pan(soft_kick(0.6), 0), b2s(b0 + 2.5), wrap=True)
        if bar % 4 == 3:
            place(kick, pan(soft_kick(0.4), 0), b2s(b0 + 3.75), wrap=True)
        for bt in (1, 3):
            place(sn, pan(brush(0.55, seed=bar * 2 + bt), 0.1), b2s(b0 + bt) + int(rng.integers(-80, 80)), wrap=True)
        for s in range(16):
            vel = [0.35, 0.16, 0.6, 0.2][s % 4] * (0.85 + 0.3 * rng.random())
            swing = 0.04 if s % 2 else 0.0
            place(hat, pan(shaker(vel, seed=bar * 16 + s), 0.35), b2s(b0 + 0.25 * s + swing), wrap=True)
    drums = kick * 0.85 + sn * 0.4 + hat * 0.5
    drums = fft_filter(drums, lambda f: g_lp(f, 9000, 2), circular=True)   # lo-fi top end
    ir_d = make_ir(1.2, 0.8, predelay=0.01, bright=5000, seed=43)
    drums = reverb(drums, ir_d, wet=0.15, dry=1.0, circular=True)
    return arp_bus + drums * 0.9


def render_melody():
    """Vibraphone lead with a faint glass-bell octave sparkle, short echoes and hall."""
    lead = new_loop()
    for i, (bt, dur, m, vel) in enumerate(MELODY):
        f = midi_hz(m)
        ring = dur * BEAT_S + 0.35            # let it ring a little past the written length
        n = ns(ring + 0.6)
        t = tvec(n)
        damp = np.where(t < ring, 1.0, np.exp(-(t - ring) / 0.12))
        v = vibes(f, ring + 0.6, vel, decay=1.7) * damp
        v += 0.12 * vel * glass_bell(f * 2, ring + 0.6, decay=0.35, seed=i) * damp
        place(lead, pan(v, 0.08), b2s(bt), wrap=True)
    echoes = pingpong(lead.mean(1), int(0.75 * BEAT), feedback=0.35, taps=4, lp_hz=3500, circular=True)
    ir = make_ir(3.6, 2.8, predelay=0.025, bright=6000, seed=51)
    out = reverb(lead + 0.3 * echoes, ir, wet=0.38, dry=0.9, circular=True)
    return fft_filter(out, lambda f: g_hp(f, 180, 2), circular=True)


def render_night():
    """Night base: same chords, soft sine/triangle pad, dark filter, very long reverb,
    sparse celesta twinkles echoing through a ping-pong delay."""
    pad = new_loop()
    for i, (sb, nb, name, root, pad_notes, _, _) in enumerate(SEGMENTS):
        start = b2s(sb) - ns(0.2)
        n = b2s(nb) + ns(3.0)
        env = env_ar(n, 2.2, 3.2)
        for j, m in enumerate(pad_notes):
            f = midi_hz(m)
            for det, p in ((-4.0, -0.5), (4.0, 0.5)):
                fd = f * 2 ** (det / 1200)
                s = 0.6 * sine(fd, n, 0.1 * j) + 0.4 * tri(fd, n, 0.37 * j)
                place(pad, pan(s * env, p) * 0.28, start, wrap=True)
        sub = sine(midi_hz(root), n) * env_ar(n, 2.5, 3.0)
        place(pad, pan(sub, 0) * 0.25, start, wrap=True)

    lfo_hz = 1.0 / LOOP_S

    def dark(t, f):
        fc = 650.0 * 2 ** (0.6 * np.sin(TWO_PI * lfo_hz * t))
        return g_lp(f, fc, 2) * g_hp(f, 45, 2)

    pad = stft_filter(pad, dark, circular=True)

    tw = np.zeros(LOOP)
    tw_st = new_loop()
    rng = np.random.default_rng(77)
    high = [86, 88, 90, 93, 95, 98]           # D6 E6 F#6 A6 B6 D7
    for bar in range(8):
        count = int(rng.integers(1, 4))
        slots = sorted(rng.choice(8, count, replace=False))
        for s in slots:
            m = int(rng.choice(high))
            c = celesta(midi_hz(m), 1.6, decay=0.7, seed=bar * 8 + s) * rng.uniform(0.45, 0.9)
            st = b2s(4 * bar + 0.5 * s)
            place(tw, c, st, wrap=True)
            place(tw_st, pan(c, rng.uniform(-0.7, 0.7)), st, wrap=True)
    echoes = pingpong(tw, int(0.75 * BEAT), feedback=0.55, taps=7, lp_hz=3000, circular=True)
    ir = make_ir(6.5, 5.5, predelay=0.04, bright=4000, seed=61)
    mix = pad + 0.35 * (tw_st + 0.6 * echoes)
    mix = chorus(mix, rate=loop_hz(0.15, LOOP_S), depth_ms=3.5, base_ms=18, mix=0.35, circular=True)
    return reverb(mix, ir, wet=0.75, dry=0.65, circular=True)


def render_jingle():
    """Level-complete fanfare: fast ascending glass arpeggio up D major pentatonic into
    a blooming Dmaj9 chord (pad + e-piano + bells + sub), ~4 s."""
    total = ns(4.0)
    buf = np.zeros((total + ns(4.0), 2))
    arp = [74, 78, 81, 83, 86, 88, 90, 93]       # D5 F#5 A5 B5 D6 E6 F#6 A6
    step = 0.085
    for k, m in enumerate(arp):
        f = midi_hz(m)
        s = glass_bell(f, 1.6, decay=0.5, bright=0.9, seed=k) + 0.5 * glass_pluck(f, 1.6, 0.8)
        place(buf, pan(s * (0.7 + 0.04 * k), -0.6 + 1.2 * k / (len(arp) - 1)) * 0.5, ns(k * step))
    bloom_t = ns(len(arp) * step + 0.02)
    chord = [50, 57, 61, 64, 66, 69]              # D3 A3 C#4 E4 F#4 A4
    n = ns(3.2)
    t = tvec(n)
    env = smooth_step(t / 0.25) * np.exp(-t / 1.6)
    for j, m in enumerate(chord):
        f = midi_hz(m)
        place(buf, supersaw(f, n, 5, 10, seed=300 + j) * env[:, None] * 0.28, bloom_t)
        place(buf, pan(fm_epiano(f * 2, 2.4, 0.5, seed=j), -0.4 + 0.16 * j) * 0.55, bloom_t + j * ns(0.018))
    for j, m in enumerate([86, 90, 93, 98]):      # bell crown D6 F#6 A6 D7
        place(buf, pan(glass_bell(midi_hz(m), 2.5, decay=0.9, seed=40 + j), -0.5 + j / 3) * 0.3,
              bloom_t + ns(0.05 + 0.06 * j))
    place(buf, pan(sub_bass(midi_hz(38), 2.2, 1.0, attack=0.03, release=0.8), 0) * 0.18, bloom_t)
    buf = fft_filter(buf, lambda f: g_lp(f, 9000, 1) * g_hp(f, 40, 2))
    ir = make_ir(3.5, 2.6, predelay=0.02, bright=6000, seed=71)
    out = reverb(buf, ir, wet=0.35, dry=0.9)[:total]
    tt = tvec(total)
    out *= np.where(tt > 3.0, smooth_step((4.0 - tt) / 1.0), 1.0)[:, None]
    out = dc_block(out)
    return normalize(fade(out, 0.0, 0.05), -3.0)


# --------------------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    renders = {}
    for name, fn in (("pad", render_pad), ("keys", render_keys), ("arp", render_arp),
                     ("melody", render_melody), ("night", render_night)):
        t0 = time.time()
        x = fn()
        assert x.shape == (LOOP, 2), (name, x.shape)
        x = dc_block(x, 25.0, circular=True)
        x *= dbamp(TARGET_RMS_DB[name]) / rms(x)
        renders[name] = x
        print("rendered %-7s in %5.1fs  rms %.1f dB" % (name, time.time() - t0, 20 * np.log10(rms(x))))

    layers = renders["keys"] + renders["arp"] + renders["melody"]
    day_mix = renders["pad"] + layers
    night_mix = renders["night"] + layers
    worst = max(peak(day_mix), peak(night_mix))
    master = dbamp(MASTER_PEAK_DB) / worst
    print("master gain %.2f dB" % (20 * np.log10(master)))
    for name, x in renders.items():
        x = x * master
        if peak(x) > dbamp(MASTER_PEAK_DB):              # safety: no stem above -3 dBFS
            x = normalize(x, MASTER_PEAK_DB)
        renders[name] = x
        write_wav(os.path.join(OUT, "music_%s.wav" % name), x)
        print("  music_%s.wav  peak %.2f dBFS  rms %.1f dBFS" % (name, 20 * np.log10(peak(x)),
                                                              20 * np.log10(rms(x))))
    jingle = render_jingle()
    write_wav(os.path.join(OUT, "jingle_complete.wav"), jingle)
    print("  jingle_complete.wav  %.2fs" % (len(jingle) / SR))


if __name__ == "__main__":
    main()
