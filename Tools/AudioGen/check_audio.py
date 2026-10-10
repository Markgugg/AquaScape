"""
check_audio.py -- numeric sanity checks for every generated WAV, plus spectrograms.

For each file: channels, length, peak dBFS, RMS dBFS, DC offset, and (for loops) a seam
score = |last sample -> first sample jump| divided by the median sample-to-sample step.
A seam score near 1 (anything below ~5) means the wrap point is as smooth as the
rest of the signal. Also verifies the music stems share an identical sample count.

Usage:  python3 check_audio.py [spectrogram_out_dir]
"""

import glob
import os
import sys

import numpy as np

from synth import SR, read_wav

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.normpath(os.path.join(HERE, "..", "..", "Assets", "AquaScape", "Audio"))
LOOPS = ("music_pad", "music_keys", "music_arp", "music_melody", "music_night",
         "amb_ocean", "amb_city", "amb_night")


def db(x):
    return 20 * np.log10(max(x, 1e-12))


def seam_score(x):
    m = x if x.ndim == 1 else x.mean(1)
    steps = np.abs(np.diff(m))
    med = np.median(steps) + 1e-9
    return float(abs(m[0] - m[-1]) / med), float(np.percentile(steps, 99.9) / med)


def spectrogram(x, path, fmax=12000, width=1000, height=360):
    from PIL import Image
    m = x if x.ndim == 1 else x.mean(1)
    n_fft, hop = 2048, max(64, len(m) // width)
    win = np.hanning(n_fft)
    if len(m) < n_fft:
        m = np.concatenate([m, np.zeros(n_fft - len(m))])
    frames = np.lib.stride_tricks.sliding_window_view(m, n_fft)[::hop] * win
    S = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(n_fft, 1 / SR)
    # log-frequency axis 40 Hz .. fmax
    rows = np.geomspace(40, fmax, height)
    idx = np.searchsorted(freqs, rows).clip(0, len(freqs) - 1)
    img = 20 * np.log10(S[:, idx].T + 1e-9)
    img = np.clip((img - (img.max() - 75)) / 75, 0, 1)[::-1]
    # simple colour map: black -> blue -> cyan -> white (white = loudest ~10 dB)
    r = np.clip(img * 4 - 3, 0, 1)
    g = np.clip(img * 2 - 0.8, 0, 1)
    b = np.clip(img * 1.4, 0, 1)
    rgb = (np.stack([r, g, b], -1) * 255).astype(np.uint8)
    Image.fromarray(rgb).resize((width, height)).save(path)


def main():
    spec_dir = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(glob.glob(os.path.join(AUDIO, "*", "*.wav")))
    lengths = {}
    print("%-26s %2s %8s %7s %7s %8s %s" % ("file", "ch", "seconds", "peak", "rms", "dc", "seam"))
    for p in files:
        x, sr = read_wav(p)
        name = os.path.splitext(os.path.basename(p))[0]
        ch = 1 if x.ndim == 1 else x.shape[1]
        dc = float(np.mean(x))
        seam = ""
        if name in LOOPS:
            s, p999 = seam_score(x)
            seam = "seam %.2f (p99.9 step %.1f)" % (s, p999)
        if name.startswith("music_"):
            lengths[name] = len(x)
        flag = ""
        if sr != SR:
            flag += " !SR"
        if abs(dc) > 0.002:
            flag += " !DC"
        print("%-26s %2d %8.3f %7.2f %7.2f %8.5f %s%s" % (name, ch, len(x) / sr, db(np.max(np.abs(x))),
                                                       db(np.sqrt(np.mean(x ** 2))), dc, seam, flag))
        if spec_dir:
            os.makedirs(spec_dir, exist_ok=True)
            if name in ("pulse", "bubble_1", "beacon_light", "dash", "jelly_hit", "portal_enter",
                        "music_pad", "amb_ocean", "amb_night"):
                spectrogram(x, os.path.join(spec_dir, name + ".png"))
    print("music stem lengths:", sorted(set(lengths.values())), "(must be a single value)")
    if spec_dir:
        mix = None
        for n in ("music_pad", "music_keys", "music_arp", "music_melody"):
            x, _ = read_wav(os.path.join(AUDIO, "Music", n + ".wav"))
            mix = x if mix is None else mix + x
        print("full day mix: peak %.2f dBFS rms %.2f dBFS" % (db(np.max(np.abs(mix))), db(np.sqrt(np.mean(mix ** 2)))))
        spectrogram(mix, os.path.join(spec_dir, "music_full_mix.png"))
        from synth import write_wav
        write_wav(os.path.join(spec_dir, "music_full_mix.wav"), mix)


if __name__ == "__main__":
    main()
