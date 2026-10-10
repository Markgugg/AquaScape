"""
synth.py -- a tiny procedural audio toolkit for AquaScape (Python 3.9 + numpy only).

Everything in the game's soundtrack and SFX is built from the pieces in this file:

  * oscillators   : sine / triangle / band-limited (polyBLEP) saw, with per-sample pitch
  * envelopes     : percussive, attack-release, ADSR, smooth ramps
  * filters       : zero-phase FFT filters (static) and an STFT overlap-add filter whose
                    response can change over time (filter sweeps, whooshes, pad movement).
                    Both have a `circular=True` mode so loops stay perfectly seamless.
  * effects       : synthetic-impulse-response convolution reverb, chorus, ping-pong delay
  * instruments   : glass bell, celesta, vibraphone, FM e-piano, glassy pluck, supersaw pad,
                    sub bass, soft kick, shaker, brush
  * utilities     : placement of events into (optionally wrapping) buffers, panning,
                    normalising, trimming, 16-bit WAV writing via the stdlib `wave` module

Design notes
------------
* Filters are done in the frequency domain instead of with per-sample IIR loops, which keeps
  generation fast (a whole 23 s stereo stem renders in seconds).
* "Circular" processing treats a buffer as one period of an infinitely repeating signal.
  Events that run past the end of a loop are wrapped onto its start, reverb/delay are applied
  with circular convolution, and every LFO completes an integer number of cycles per loop.
  The result is a loop whose last sample flows into its first sample with no seam at all.
"""

import os
import wave

import numpy as np

SR = 44100
TWO_PI = 2.0 * np.pi


# --------------------------------------------------------------------------------------
# basic helpers
# --------------------------------------------------------------------------------------
def ns(seconds):
    """Seconds -> integer sample count."""
    return int(round(seconds * SR))


def midi_hz(m):
    """MIDI note number -> frequency in Hz (A4 = 69 = 440 Hz)."""
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def dbamp(db):
    return 10.0 ** (db / 20.0)


def ampdb(a):
    return 20.0 * np.log10(max(float(a), 1e-12))


def tvec(n):
    """Time axis (seconds) for n samples."""
    return np.arange(n) / SR


def loop_hz(approx_hz, loop_seconds):
    """Snap a frequency so it completes a whole number of cycles in one loop."""
    k = max(1, int(round(approx_hz * loop_seconds)))
    return k / loop_seconds


# --------------------------------------------------------------------------------------
# oscillators
# --------------------------------------------------------------------------------------
def phase_cycles(freq, n, phase0=0.0):
    """Unwrapped phase in cycles for a constant or per-sample frequency."""
    if np.ndim(freq) == 0:
        return phase0 + float(freq) * np.arange(n) / SR
    f = np.asarray(freq, dtype=float)
    assert len(f) == n, "per-sample frequency array must have n samples"
    ph = np.empty(n)
    ph[0] = 0.0
    np.cumsum(f[:-1] / SR, out=ph[1:])
    return phase0 + ph


def sine(freq, n, phase0=0.0):
    return np.sin(TWO_PI * phase_cycles(freq, n, phase0))


def tri(freq, n, phase0=0.0):
    p = phase_cycles(freq, n, phase0) % 1.0
    return 4.0 * np.abs(p - 0.5) - 1.0


def saw(freq, n, phase0=0.0):
    """Band-limited sawtooth using polyBLEP correction (vectorised)."""
    p = phase_cycles(freq, n, phase0) % 1.0
    dt = np.broadcast_to(np.asarray(freq, dtype=float) / SR, (n,))
    y = 2.0 * p - 1.0
    m = p < dt
    t = p[m] / dt[m]
    y[m] -= t + t - t * t - 1.0
    m = p > 1.0 - dt
    t = (p[m] - 1.0) / dt[m]
    y[m] -= t * t + t + t + 1.0
    return y


def noise(n, seed=0):
    return np.random.default_rng(seed).standard_normal(n)


def pink_noise(n, seed=0, circular=True):
    """1/f noise made by spectral shaping (naturally periodic in n when circular)."""
    w = noise(n, seed)
    X = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    f[0] = f[1]
    X /= np.sqrt(f / 100.0)
    X[0] = 0.0
    y = np.fft.irfft(X, n)
    return y / (np.std(y) + 1e-12)


# --------------------------------------------------------------------------------------
# envelopes
# --------------------------------------------------------------------------------------
def smooth_step(x):
    x = np.clip(x, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * x)


def env_perc(n, attack, tau, curve_tau2=None, mix2=0.0):
    """Short smooth attack then exponential decay (time constant tau seconds).
    Optionally a second slower decay component for a 'bloom' tail."""
    t = tvec(n)
    a = smooth_step(t / max(attack, 1e-4))
    d = np.exp(-t / tau)
    if curve_tau2 is not None:
        d = (1.0 - mix2) * d + mix2 * np.exp(-t / curve_tau2)
    e = a * d
    return e * release_tail(n, 0.004)


def release_tail(n, seconds):
    """Multiplier that fades the last `seconds` to zero (anti-click)."""
    e = np.ones(n)
    r = min(n, max(1, ns(seconds)))
    e[n - r:] = smooth_step(np.linspace(1.0, 0.0, r))
    return e


def env_ar(n, attack, release):
    """Smooth attack, sustain at 1, smooth release at the end."""
    t = tvec(n)
    e = smooth_step(t / max(attack, 1e-4))
    r = min(n, max(1, ns(release)))
    e[n - r:] *= smooth_step(np.linspace(1.0, 0.0, r))
    return e


def env_adsr(n, attack, decay, sustain, release):
    t = tvec(n)
    e = np.where(t < attack, smooth_step(t / max(attack, 1e-4)),
                 sustain + (1 - sustain) * np.exp(-(t - attack) / max(decay, 1e-4)))
    r = min(n, max(1, ns(release)))
    e[n - r:] *= np.linspace(1.0, 0.0, r) ** 1.5
    return e


def ramp(n, a, b, curve="exp"):
    """Ramp from a to b over n samples ('exp' = geometric, good for pitch)."""
    x = np.linspace(0.0, 1.0, n)
    if curve == "exp":
        return a * (b / a) ** x
    if curve == "smooth":
        return a + (b - a) * smooth_step(x)
    return a + (b - a) * x


# --------------------------------------------------------------------------------------
# filters (frequency-domain magnitude responses, zero phase)
# --------------------------------------------------------------------------------------
def g_lp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (np.asarray(f) / fc) ** (2 * order))


def g_hp(f, fc, order=2):
    f = np.maximum(np.asarray(f, dtype=float), 1e-3)
    return 1.0 / np.sqrt(1.0 + (fc / f) ** (2 * order))


def g_bp(f, lo, hi, order=2):
    return g_hp(f, lo, order) * g_lp(f, hi, order)


def g_peak(f, fc, gain_db, width_oct=0.5):
    """Bell-shaped boost/cut on a log-frequency axis."""
    f = np.maximum(np.asarray(f, dtype=float), 1e-3)
    x = np.log2(f / fc) / width_oct
    return 1.0 + (dbamp(gain_db) - 1.0) * np.exp(-0.5 * x * x)


def fft_filter(x, gain_fn, circular=False):
    """Apply a static zero-phase filter. gain_fn(freqs) -> magnitude array.
    Works on mono (n,) or multichannel (n, ch)."""
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:
        return np.stack([fft_filter(x[:, c], gain_fn, circular) for c in range(x.shape[1])], 1)
    n = len(x)
    if circular:
        X = np.fft.rfft(x)
        return np.fft.irfft(X * gain_fn(np.fft.rfftfreq(n, 1.0 / SR)), n)
    pad = 8192
    buf = np.concatenate([np.zeros(pad), x, np.zeros(pad)])
    m = len(buf)
    X = np.fft.rfft(buf)
    y = np.fft.irfft(X * gain_fn(np.fft.rfftfreq(m, 1.0 / SR)), m)
    return y[pad:pad + n]


def stft_filter(x, gain_fn, n_win=1024, hop=256, circular=False):
    """Time-varying zero-phase filter using windowed overlap-add.

    gain_fn(t, f) receives frame-centre times t (frames, 1) in seconds and bin
    frequencies f (1, bins) and returns the magnitude response (frames, bins).
    Frames are zero-padded to 2*n_win so filtering is linear inside each frame.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:
        return np.stack([stft_filter(x[:, c], gain_fn, n_win, hop, circular)
                         for c in range(x.shape[1])], 1)
    n = len(x)
    pad = n_win
    if circular:
        xp = np.concatenate([x[-pad:], x, x[:pad]])
    else:
        xp = np.concatenate([np.zeros(pad), x, np.zeros(pad + hop)])
    nfft = 2 * n_win
    win = np.hanning(n_win + 1)[:-1]                       # periodic Hann
    frames = np.lib.stride_tricks.sliding_window_view(xp, n_win)[::hop] * win
    nf = frames.shape[0]
    buf = np.zeros((nf, nfft))
    off = n_win // 2
    buf[:, off:off + n_win] = frames
    S = np.fft.rfft(buf, axis=1)
    freqs = np.fft.rfftfreq(nfft, 1.0 / SR)[None, :]
    centers = ((np.arange(nf) * hop + off - pad) / SR)[:, None]
    if circular:
        centers = centers % (n / SR)
    G = gain_fn(centers, freqs)
    Y = np.fft.irfft(S * G, n=nfft, axis=1)
    out = np.zeros(len(xp) + nfft)
    for k in range(nf):
        out[k * hop:k * hop + nfft] += Y[k]
    out = out[off:off + len(xp)] / (win.sum() / hop)
    return out[pad:pad + n]


def dc_block(x, fc=20.0, circular=False):
    return fft_filter(x, lambda f: g_hp(f, fc, 2) * (f > 0), circular)


# --------------------------------------------------------------------------------------
# effects
# --------------------------------------------------------------------------------------
def make_ir(seconds=3.0, rt60=2.5, predelay=0.015, bright=6000.0, seed=1, stereo=True):
    """Synthetic reverb impulse response: band-split exponentially decaying noise
    (highs decay faster than lows, like a real room) plus a few early reflections."""
    n = ns(seconds)
    t = tvec(n)
    chans = []
    rng = np.random.default_rng(seed)
    for ch in range(2 if stereo else 1):
        w = rng.standard_normal(n)
        W = np.fft.rfft(w)
        f = np.fft.rfftfreq(n, 1.0 / SR)
        lo = np.fft.irfft(W * g_lp(f, 700, 2), n)
        mid = np.fft.irfft(W * g_bp(f, 700, bright, 2), n)
        hi = np.fft.irfft(W * g_hp(f, bright, 2), n)
        k = 6.91 / rt60
        ir = lo * np.exp(-t * k * 0.9) + mid * np.exp(-t * k) + 0.5 * hi * np.exp(-t * k * 2.2)
        # fade-in so the tail swells rather than starting abruptly (diffuse feel)
        ir *= smooth_step(t / 0.03)
        # early reflections
        for _ in range(8):
            d = ns(rng.uniform(0.005, 0.07))
            ir[d] += rng.uniform(-1, 1) * 2.0 * np.sqrt(np.mean(ir[:ns(0.1)] ** 2))
        pd = ns(predelay)
        ir = np.concatenate([np.zeros(pd), ir])[:n]
        ir *= release_tail(n, 0.05)
        ir /= np.sqrt(np.sum(ir ** 2))
        chans.append(ir)
    return np.stack(chans, 1) if stereo else chans[0]


def convolve(x, h, circular=False):
    """FFT convolution of 1-D x with 1-D h (linear, or circular in len(x))."""
    n = len(x)
    if circular:
        assert len(h) <= n
        H = np.fft.rfft(np.concatenate([h, np.zeros(n - len(h))]))
        return np.fft.irfft(np.fft.rfft(x) * H, n)
    m = n + len(h) - 1
    nfft = 1 << (m - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(h, nfft), nfft)[:m]


def to_stereo(x):
    return np.stack([x, x], 1) if x.ndim == 1 else x


def reverb(x, ir, wet=0.3, dry=1.0, circular=False):
    """Convolution reverb. Mono or stereo in; stereo out if ir is stereo.
    Non-circular output is extended by the IR length."""
    x = np.asarray(x, dtype=float)
    if ir.ndim == 1:
        xm = x if x.ndim == 1 else x.mean(1)
        w = convolve(xm, ir, circular)
        d = np.zeros_like(w)
        d[:len(xm)] = xm
        return dry * d + wet * w
    xs = to_stereo(x)
    outs = []
    for c in range(2):
        w = convolve(xs[:, c], ir[:, c], circular)
        d = np.zeros_like(w)
        d[:len(xs)] = xs[:, c]
        outs.append(dry * d + wet * w)
    return np.stack(outs, 1)


def frac_delay_read(x, delay_samples, circular=False):
    """Read x at (n - delay[n]) with linear interpolation (delay may vary per sample)."""
    n = len(x)
    idx = np.arange(n) - delay_samples
    if circular:
        idx = idx % n
        return np.interp(idx, np.arange(n + 1), np.concatenate([x, x[:1]]))
    return np.interp(idx, np.arange(n), x, left=0.0, right=0.0)


def chorus(x, rate=0.25, depth_ms=2.5, base_ms=14.0, mix=0.5, circular=False):
    """Stereo chorus: two modulated delay lines in quadrature (one per side)."""
    xm = x if x.ndim == 1 else x.mean(1)
    xs = to_stereo(x)
    n = len(xm)
    t = tvec(n)
    out = np.empty((n, 2))
    for c, ph in enumerate((0.0, 0.25)):
        d = (base_ms + depth_ms * np.sin(TWO_PI * (rate * t + ph))) * SR / 1000.0
        out[:, c] = (1 - mix) * xs[:, c] + mix * frac_delay_read(xm, d, circular)
    return out


def pingpong(x, delay, feedback=0.45, taps=6, lp_hz=5000.0, circular=False, spread=0.85):
    """Ping-pong echo of a mono or stereo source -> stereo echoes only (wet signal).
    Echo k alternates right/left and is progressively darker."""
    xm = x if x.ndim == 1 else x.mean(1)
    n = len(xm)
    total = n if circular else n + delay * taps
    out = np.zeros((total, 2))
    src = np.concatenate([xm, np.zeros(total - n)])
    cur = src
    for k in range(1, taps + 1):
        cur = fft_filter(cur, lambda f: g_lp(f, lp_hz, 1), circular=True)
        shifted = np.roll(cur, delay) if circular else np.concatenate([np.zeros(delay), cur[:-delay]])
        cur = shifted
        g = feedback ** (k - 1)
        side = (1 - spread, 1.0) if k % 2 == 1 else (1.0, 1 - spread)
        out[:, 0] += g * side[0] * cur
        out[:, 1] += g * side[1] * cur
    return out


def soft_clip(x, drive=1.5):
    return np.tanh(drive * x) / np.tanh(drive)


# --------------------------------------------------------------------------------------
# buffer utilities
# --------------------------------------------------------------------------------------
def pan(sig, p):
    """Equal-power pan of a mono signal, p in [-1 (left), +1 (right)]."""
    a = (np.clip(p, -1, 1) + 1.0) * np.pi / 4.0
    return np.stack([sig * np.cos(a), sig * np.sin(a)], 1) * np.sqrt(2.0)


def place(buf, sig, start, wrap=False):
    """Mix `sig` into `buf` at sample `start`. wrap=True treats buf as a loop."""
    start = int(round(start))
    L = len(buf)
    if sig.ndim == 1 and buf.ndim == 2:
        sig = to_stereo(sig) / np.sqrt(2.0)
    if wrap:
        pos = start % L
        off = 0
        rem = len(sig)
        while rem > 0:
            c = min(L - pos, rem)
            buf[pos:pos + c] += sig[off:off + c]
            off += c
            rem -= c
            pos = 0
        return buf
    s0 = max(0, start)
    e0 = min(L, start + len(sig))
    if e0 > s0:
        buf[s0:e0] += sig[s0 - start:e0 - start]
    return buf


def peak(x):
    return float(np.max(np.abs(x)))


def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=float) ** 2)))


def normalize(x, peak_db=-1.0):
    p = peak(x)
    return x * (dbamp(peak_db) / p) if p > 0 else x


def fade(x, fin=0.002, fout=0.01):
    x = np.array(x, dtype=float, copy=True)
    a, b = ns(fin), ns(fout)
    if a > 0:
        x[:a] *= smooth_step(np.linspace(0, 1, a))[:, None] if x.ndim == 2 else smooth_step(np.linspace(0, 1, a))
    if b > 0:
        r = smooth_step(np.linspace(1, 0, b))
        x[-b:] *= r[:, None] if x.ndim == 2 else r
    return x


def trim(x, thresh_db=-62.0, lead_keep=0.0005, fout=0.015):
    """Remove leading/trailing near-silence (relative to peak), then de-click the ends."""
    mono = np.abs(x) if x.ndim == 1 else np.max(np.abs(x), 1)
    thr = peak(x) * dbamp(thresh_db)
    idx = np.nonzero(mono > thr)[0]
    if len(idx) == 0:
        return x
    s = max(0, idx[0] - ns(lead_keep))
    e = min(len(x), idx[-1] + 1)
    return fade(x[s:e], 0.0015, fout)


def write_wav(path, x):
    """Write float audio (-1..1) as 16-bit PCM WAV, mono (n,) or stereo (n,2)."""
    x = np.asarray(x, dtype=float)
    ch = 1 if x.ndim == 1 else x.shape[1]
    pcm = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch)
    return data, sr


# --------------------------------------------------------------------------------------
# instruments (each returns a mono numpy array unless noted)
# --------------------------------------------------------------------------------------
GLASS_PARTIALS = [  # (ratio, amp, decay multiplier) -- slightly stretched, like a wine glass
    (1.0, 1.00, 1.00),
    (2.005, 0.45, 0.65),
    (3.01, 0.22, 0.45),
    (4.17, 0.14, 0.30),
    (5.43, 0.08, 0.22),
    (6.79, 0.05, 0.15),
]


def glass_bell(freq, dur, decay=0.6, bright=1.0, attack=0.0015, seed=0, partials=None):
    """Clear glass chime: stretched partials with faster decay up high and a gentle beat."""
    n = ns(dur)
    t = tvec(n)
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    for ratio, amp, dm in (partials or GLASS_PARTIALS):
        f = freq * ratio
        if f > 18000:
            continue
        a = amp * (bright ** (ratio - 1) if ratio > 1 else 1.0)
        beat = 1.0 + 0.004 * rng.uniform(-1, 1)
        y += a * np.exp(-t / (decay * dm)) * (
            0.6 * np.sin(TWO_PI * f * t + rng.uniform(0, 6.28)) +
            0.4 * np.sin(TWO_PI * f * beat * t + rng.uniform(0, 6.28)))
    return y * smooth_step(t / attack) * release_tail(n, 0.01)


def celesta(freq, dur, decay=0.9, seed=0):
    """Celesta / music-box tone: strong fundamental, quiet 2nd/3rd/4th, tiny hammer tick."""
    n = ns(dur)
    t = tvec(n)
    y = (np.sin(TWO_PI * freq * t) * np.exp(-t / decay)
         + 0.25 * np.sin(TWO_PI * 2 * freq * t) * np.exp(-t / (decay * 0.4))
         + 0.12 * np.sin(TWO_PI * 3.01 * freq * t) * np.exp(-t / (decay * 0.25))
         + 0.06 * np.sin(TWO_PI * 4.05 * freq * t) * np.exp(-t / (decay * 0.15)))
    tick = fft_filter(noise(n, seed), lambda f: g_bp(f, 2000, 7000, 2)) * np.exp(-t / 0.003) * 0.08
    return (y + tick) * smooth_step(t / 0.001) * release_tail(n, 0.01)


def vibes(freq, dur, vel=1.0, decay=1.8, trem_hz=5.2, trem_depth=0.22):
    """Vibraphone: partials 1, 4, 10 (bar modes) with motor tremolo and soft mallet."""
    n = ns(dur)
    t = tvec(n)
    y = (np.sin(TWO_PI * freq * t) * np.exp(-t / decay)
         + 0.30 * vel * np.sin(TWO_PI * 3.98 * freq * t) * np.exp(-t / (decay * 0.28))
         + 0.06 * vel * np.sin(TWO_PI * 9.9 * freq * t) * np.exp(-t / (decay * 0.07)))
    trem = 1.0 - trem_depth * (0.5 - 0.5 * np.cos(TWO_PI * trem_hz * t))
    return vel * y * trem * smooth_step(t / 0.003) * release_tail(n, 0.05)


def fm_epiano(freq, dur, vel=1.0, release=0.25, seed=0):
    """Soft FM electric piano (Rhodes-ish): ratio 1:1 modulation with decaying index,
    plus a faint high 'tine' partial, slightly detuned double for warmth."""
    n = ns(dur + release)
    t = tvec(n)
    index = (0.6 + 0.4 * vel) * (2.6 * np.exp(-t / 0.16) + 0.55)
    y = np.zeros(n)
    for det, g in ((1.0, 0.6), (1.0015, 0.4)):
        f = freq * det
        mod = np.sin(TWO_PI * f * t)
        y += g * np.sin(TWO_PI * f * t + index * mod)
    tine = 0.12 * vel * np.sin(TWO_PI * freq * 7.0 * t) * np.exp(-t / 0.06)
    amp = np.exp(-t / 1.6) * smooth_step(t / 0.004)
    off = ns(dur)
    rel = np.ones(n)
    rel[off:] = np.exp(-(t[off:] - t[off]) / (release / 4))
    return vel * (y + tine) * amp * rel * release_tail(n, 0.01)


def glass_pluck(freq, dur=0.6, vel=1.0, decay=0.32):
    """Glassy pluck for arpeggios: FM (2:1) with fast decaying index over a sine."""
    n = ns(dur)
    t = tvec(n)
    index = 1.4 * np.exp(-t / 0.045) + 0.15
    y = np.sin(TWO_PI * freq * t + index * np.sin(TWO_PI * 2.0 * freq * t))
    y += 0.25 * np.sin(TWO_PI * 3.0 * freq * t) * np.exp(-t / 0.06)
    return vel * y * np.exp(-t / decay) * smooth_step(t / 0.0015) * release_tail(n, 0.02)


def supersaw(freq, n, voices=6, detune_cents=11.0, seed=0, width=0.8):
    """Detuned stack of band-limited saws spread across the stereo field -> (n,2)."""
    rng = np.random.default_rng(seed)
    out = np.zeros((n, 2))
    for v in range(voices):
        x = v / (voices - 1) * 2 - 1
        cents = detune_cents * x + rng.uniform(-1.5, 1.5)
        s = saw(freq * 2 ** (cents / 1200), n, rng.random())
        p = width * (x if v % 2 == 0 else -x)
        out += pan(s, p)
    return out / voices


def sub_bass(freq, dur, vel=1.0, attack=0.02, release=0.12):
    """Round sub: sine + touch of 2nd/3rd harmonic (so it reads on small speakers)."""
    n = ns(dur + release)
    t = tvec(n)
    y = np.sin(TWO_PI * freq * t)
    y = soft_clip(y + 0.18 * np.sin(TWO_PI * 2 * freq * t), 1.3)
    e = env_ar(n, attack, release + 0.02) * (0.75 + 0.25 * np.exp(-t / 0.4))
    return vel * y * e


def soft_kick(vel=1.0, dur=0.32):
    n = ns(dur)
    t = tvec(n)
    f = 48 + 75 * np.exp(-t / 0.028)
    y = sine(f, n) * np.exp(-t / 0.13)
    click = fft_filter(noise(n, 7), lambda fr: g_bp(fr, 300, 2500, 1)) * np.exp(-t / 0.004) * 0.05
    y = fft_filter(y + click, lambda fr: g_lp(fr, 1800, 2))
    return vel * y * smooth_step(t / 0.002) * release_tail(n, 0.02)


def shaker(vel=1.0, dur=0.09, seed=0):
    n = ns(dur)
    t = tvec(n)
    y = fft_filter(noise(n, seed), lambda f: g_bp(f, 4500, 10000, 2))
    e = smooth_step(t / 0.006) * np.exp(-t / 0.022)
    return vel * y * e * release_tail(n, 0.01)


def brush(vel=1.0, dur=0.25, seed=0):
    n = ns(dur)
    t = tvec(n)
    y = fft_filter(noise(n, seed), lambda f: g_bp(f, 1200, 7000, 1))
    e = smooth_step(t / 0.012) * np.exp(-t / 0.07)
    return vel * y * e * release_tail(n, 0.02)
