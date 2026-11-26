"""Trilha original da campanha de vendas VALMONT (18 s, 120 BPM, Ré menor).

Composição própria (sem samples de terceiros), livre para uso publicitário.
Moderna e sofisticada, com batida discreta e acentos nas viradas de cena:
  0 s gancho · 2 s demonstração · 6 s Rosé/Black · 10 s preço · 13 s oferta · 16 s final
Saída: build/trilha_campanha.wav
"""
from pathlib import Path
import wave

import numpy as np

import music as m
from music import SR, BEAT, fft_filter, mtof

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/trilha_campanha.wav"
DUR = 18.0
N = int(SR * DUR)
rng = np.random.default_rng(18)


def add(buf, sig, start, gain=1.0, pan=0.0):
    i0 = int(round(start * SR))
    if i0 >= N:
        return
    if sig.ndim == 1:
        l = np.cos((pan + 1) * np.pi / 4)
        r = np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l * np.sqrt(2), sig * r * np.sqrt(2)], axis=1)
    if i0 < 0:
        sig = sig[-i0:]
        i0 = 0
    n = min(len(sig), N - i0)
    buf[i0:i0 + n] += sig[:n] * gain


CHORDS = [
    (0.0, 2.0, [50, 53, 57, 60, 64]),    # Dm9
    (2.0, 2.0, [46, 50, 53, 57, 60]),    # Bbmaj9
    (4.0, 2.0, [43, 46, 50, 53, 57]),    # Gm9
    (6.0, 2.0, [41, 48, 52, 55, 57]),    # Fmaj9
    (8.0, 1.0, [43, 46, 50, 53, 57]),    # Gm9
    (9.0, 1.0, [45, 49, 52, 55, 64]),    # A7
    (10.0, 2.0, [50, 53, 57, 60, 64]),   # Dm9  (preço)
    (12.0, 2.0, [46, 50, 53, 57, 62]),   # Bbmaj7 (oferta em 13 s)
    (14.0, 1.0, [43, 46, 50, 53, 57]),   # Gm9
    (15.0, 1.0, [45, 50, 52, 55, 64]),   # A7sus4
    (16.0, 2.0, [41, 48, 52, 55, 57, 64]),  # Fmaj9 (assinatura)
]
BASS = [38, 34, 31, 29, 31, 33, 38, 34, 31, 33, 29]


def main():
    dry = np.zeros((N, 2))
    wet = np.zeros((N, 2))
    pad = np.zeros((N, 2))
    low = np.zeros((N, 2))

    for start, length, notes in CHORDS:
        p = m.pad_chord(notes, length + 0.12, attack=0.3 if start == 0 else 0.22,
                        release=1.3 if start >= 16 else 0.45)
        add(pad, p, start - (0 if start == 0 else 0.04), gain=0.5)

    pattern = [0, 2, 4, 3, 1, 3, 2, 4]
    for start, length, notes in CHORDS:
        if start >= 16:
            continue
        up = [x + 12 for x in notes[1:]] + [notes[1] + 24]
        steps = int(round(length / (BEAT / 2)))
        for k in range(steps):
            t0 = start + k * BEAT / 2
            note = m.epiano(mtof(up[pattern[k % 8] % len(up)]), 1.1, 0.55 + 0.25 * (k % 4 == 0))
            pan = [-0.45, 0.45][k % 2]
            add(dry, note, t0, gain=0.10, pan=pan)
            add(wet, note, t0, gain=0.08, pan=pan)

    for mm, d in [(74, 0.0), (81, 0.02)]:
        b = m.bell(mtof(mm), 3.0)
        add(dry, b, d, gain=0.06)
        add(wet, b, d, gain=0.10)
    for mm, d in [(65, 0.0), (72, 0.03), (76, 0.06), (79, 0.09)]:
        b = m.bell(mtof(mm), 2.6)
        add(dry, b, 16.0 + d, gain=0.06, pan=d * 8 - 0.3)
        add(wet, b, 16.0 + d, gain=0.12)

    for i, (start, length, _) in enumerate(CHORDS):
        root = mtof(BASS[i])
        if start < 2.0:
            add(low, m.bass_note(root, 1.9) * 0.6, 0.0, gain=0.34)
            continue
        if start >= 16.0:
            add(low, m.bass_note(root, 1.9), start, gain=0.36)
            continue
        hits = [0.0, 0.75, 1.5] if length >= 2.0 else [0.0, 0.5]
        for h in hits:
            if h < length:
                add(low, m.bass_note(root, 0.42 if h < length - 0.5 else length - h - 0.02), start + h, gain=0.40)

    kicks = []
    for b0 in np.arange(2.0, 16.0, 2.0):
        kicks += [b0, b0 + 1.0]
        if int(b0) % 4 == 0:
            kicks.append(b0 + 1.75)
    kicks = sorted(set(round(k, 3) for k in kicks + [10.0, 13.0]))
    for kt in kicks:
        add(dry, m.kick(), kt, gain=0.55)
    for st in np.arange(2.5, 16.0, 1.0):
        s = m.snap()
        add(dry, s, st, gain=0.17)
        add(wet, s, st, gain=0.18)

    tt, k = 0.0, 0
    while tt < 16.0 - 1e-6:
        dense = 10.0 <= tt < 16.0
        step = BEAT / 4 if dense else BEAT / 2
        vel = (0.9 if k % 2 == 0 else 0.6) * (0.5 if dense and k % 2 else 1.0)
        add(dry, m.tick(1.0 if k % 2 == 0 else 0.84), tt, gain=0.05 * vel, pan=0.35 if k % 2 else -0.35)
        tt += step
        k += 1

    add(dry, m.impact(2.4, 1.0), 0.0, gain=0.45)
    add(dry, m.impact(2.4, 0.9), 10.0, gain=0.40)
    add(dry, m.impact(2.4, 0.9), 13.0, gain=0.36)
    add(dry, m.impact(2.8, 1.1), 16.0, gain=0.50)
    add(wet, m.riser(1.0), 9.0, gain=0.09)
    add(wet, m.reverse_swell(0.9), 12.1, gain=0.08)
    add(wet, m.reverse_swell(1.0), 15.0, gain=0.10)
    for wt in (2.0, 6.0):
        add(dry, m.whoosh(0.4), wt - 0.2, gain=0.05)

    duck = np.ones(N)
    rel = int(0.3 * SR)
    curve = 1 - 0.5 * np.exp(-np.linspace(0, 5, rel))
    for kt in kicks:
        i0 = int(kt * SR)
        nn = min(rel, N - i0)
        duck[i0:i0 + nn] = np.minimum(duck[i0:i0 + nn], curve[:nn])
    pad *= duck[:, None]
    low *= duck[:, None]

    rev = m.convolve(wet + pad * 0.35, m.reverb_ir(2.6, 3.4))
    mix = dry + pad + low + rev * 0.55
    mix = fft_filter(mix, lo=28)
    mix = mix / np.max(np.abs(mix)) * 0.9
    mix = np.tanh(1.3 * mix) / np.tanh(1.3)
    fade = int(0.7 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 1.5
    fin = int(0.004 * SR)
    mix[:fin] *= np.linspace(0, 1, fin)[:, None]
    mix *= 0.89 / np.max(np.abs(mix))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
    print("trilha da campanha:", OUT)


if __name__ == "__main__":
    main()
