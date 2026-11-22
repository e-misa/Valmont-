"""Trilha original de Natal — VALMONT "Presenteie com elegância" (15 s, 120 BPM, Ré maior).

Composição própria deste projeto, sintetizada nota por nota (sem samples, sem
melodias de canções natalinas existentes): uso comercial livre para a VALMONT.

Clima: glockenspiel/celesta na melodia, pizzicato, guizos (sleigh bells),
cordas suaves e um acorde menor "iv" (Sol menor) que dá a nostalgia típica
de Natal. Sincronia com o vídeo (1 tempo = 0,5 s):
  0,0 s  glissando de sinos + abertura do presente
  2,0 / 3,0 / 4,0 / 5,0 / 6,0 s  "swish" das fitas nas trocas de cena
  6,0 s  caixa VALMONT · 8,0 s preço · 10,0 s oferta · 12,5 s assinatura
Saída: build/trilha_natal.wav
"""
from pathlib import Path
import wave

import numpy as np

import music as m  # reaproveita os sintetizadores da trilha principal
from music import SR, N, BEAT, add, fft_filter, mtof, t_axis

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/trilha_natal.wav"
rng = np.random.default_rng(25)


# ------------------------------------------------------------- instrumentos
def glock(freq, length=1.6, vel=1.0):
    n = int(length * SR)
    t = t_axis(n)
    parts = [(1.0, 1.0, 2.4), (2.76, 0.32, 5.0), (5.40, 0.14, 9.0), (8.93, 0.05, 14.0)]
    s = np.zeros(n)
    for r, a, d in parts:
        s += a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * d)
    s += 0.35 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 3.5)  # corpo de celesta
    return s * (1 - np.exp(-t * 1500)) * vel


def pizz(freq, length=0.6, vel=1.0):
    n = int(length * SR)
    t = t_axis(n)
    s = np.zeros(n)
    for k in range(1, 9):
        if freq * k > 8000:
            break
        s += (1 / k ** 1.25) * np.sin(2 * np.pi * freq * k * t + rng.uniform(0, 6.28)) * np.exp(-t * (7 + 4 * k))
    return s * (1 - np.exp(-t * 2500)) * vel


SLEIGH = []
for _v in range(5):
    n = int(0.16 * SR)
    t = t_axis(n)
    s = np.zeros(n)
    for _b in range(7):
        j = int(rng.uniform(0, 0.014) * SR)
        f = rng.uniform(4800, 9800)
        a = rng.uniform(0.4, 1.0)
        d = rng.uniform(28, 60)
        tone = a * np.sin(2 * np.pi * f * t) * np.exp(-t * d)
        tone += 0.5 * a * np.sin(2 * np.pi * f * 1.51 * t) * np.exp(-t * d * 1.4)
        s[j:] += tone[: n - j]
    s += fft_filter(rng.standard_normal(n), lo=6000, hi=14000) * np.exp(-t * 70) * 0.6
    SLEIGH.append(s / np.max(np.abs(s)))


def sleigh(vel=1.0):
    return SLEIGH[rng.integers(len(SLEIGH))] * vel


def chime_gliss(start_midi=74, steps=14, length=0.5):
    scale = [0, 2, 4, 7, 9]  # pentatônica de Ré
    notes = []
    k = 0
    while len(notes) < steps:
        notes.append(start_midi + 12 * (k // 5) + scale[k % 5])
        k += 1
    out = np.zeros(int((length + 2.0) * SR))
    for i, mm in enumerate(notes):
        g = glock(mtof(mm), 2.0, 0.55 + 0.3 * i / steps)
        i0 = int(i * length / steps * SR)
        out[i0:i0 + len(g)] += g[: len(out) - i0]
    return out


def swish(length=0.34):
    n = int(length * SR)
    x = rng.standard_normal(n)
    y = m.one_pole_lp_sweep(x, 9000, 1500)
    y = fft_filter(y, lo=900)
    tt = np.linspace(0, 1, n)
    return y * np.sin(np.pi * tt) ** 1.5


# ------------------------------------------------------------------ harmonia
CHORDS = [
    (0.0, 2.0, [50, 54, 57, 61, 64]),    # Dmaj9
    (2.0, 1.0, [47, 54, 57, 62, 66]),    # Bm7
    (3.0, 1.0, [43, 50, 54, 59, 62]),    # Gmaj7
    (4.0, 1.0, [40, 55, 59, 62, 66]),    # Em9
    (5.0, 1.0, [45, 52, 55, 61, 64]),    # A7
    (6.0, 1.0, [42, 50, 54, 57, 61]),    # Dmaj7/F#
    (7.0, 1.0, [43, 50, 54, 59, 62]),    # Gmaj7
    (8.0, 1.0, [43, 50, 55, 58, 64]),    # Gm6 (iv menor)
    (9.0, 1.0, [45, 50, 54, 57, 62]),    # D/A
    (10.0, 1.0, [47, 54, 57, 62, 66]),   # Bm7
    (11.0, 0.75, [40, 55, 59, 62, 66]),  # Em9
    (11.75, 0.75, [45, 52, 55, 61, 64]),  # A7
    (12.5, 2.5, [38, 50, 54, 57, 61, 64]),  # Dmaj9 final
]
BASS = [38, 35, 31, 28, 33, 30, 31, 31, 33, 35, 28, 33, 26]

MELODY = [
    (0.5, 78, .25), (0.75, 81, .25), (1.0, 86, .5), (1.5, 85, .25), (1.75, 81, .25),
    (2.0, 83, .5), (2.5, 81, .25), (2.75, 78, .25),
    (3.0, 79, .5), (3.5, 83, .25), (3.75, 86, .25),
    (4.0, 83, .5), (4.5, 79, .25), (4.75, 76, .25),
    (5.0, 81, .5), (5.5, 85, .25), (5.75, 88, .25),
    (6.0, 86, .75), (6.75, 85, .25),
    (7.0, 83, .5), (7.5, 81, .25), (7.75, 79, .25),
    (8.0, 82, .75), (8.75, 81, .25),
    (9.0, 78, .5), (9.5, 81, .5),
    (10.0, 86, .5), (10.5, 85, .25), (10.75, 83, .25),
    (11.0, 79, .5), (11.5, 78, .25), (11.75, 76, .25),
    (12.0, 85, .5),
    (12.5, 86, 2.2), (12.5, 81, 2.2), (12.5, 78, 2.2),
]


def main():
    dry = np.zeros((N, 2))
    wet = np.zeros((N, 2))
    pad = np.zeros((N, 2))
    low = np.zeros((N, 2))

    for start, length, notes in CHORDS:
        p = m.pad_chord(notes, length + 0.12, attack=0.4 if start == 0 else 0.22,
                        release=1.6 if start >= 12.5 else 0.45)
        p = fft_filter(p, hi=1300)
        add(pad, p, start - (0 if start == 0 else 0.04), gain=0.5)

    # Melodia (glockenspiel/celesta)
    for st, mm, du in MELODY:
        g = glock(mtof(mm), max(1.4, du + 1.2), 0.9 if du >= 0.5 else 0.75)
        add(dry, g, st, gain=0.10, pan=0.12)
        add(wet, g, st, gain=0.12, pan=-0.12)

    # Pizzicato em colcheias (2,0–12,5 s)
    pat = [1, 2, 3, 2, 4, 3, 2, 3]
    for start, length, notes in CHORDS:
        if start < 2.0 or start >= 12.5:
            continue
        steps = int(round(length / (BEAT / 2)))
        for k in range(steps):
            note = notes[pat[k % len(pat)] % len(notes)]
            pz = pizz(mtof(note + 12), 0.5, 0.8 if k % 2 == 0 else 0.55)
            pan = -0.4 if k % 2 == 0 else 0.4
            add(dry, pz, start + k * BEAT / 2, gain=0.13, pan=pan)
            add(wet, pz, start + k * BEAT / 2, gain=0.05, pan=-pan)

    # Baixo (pizz grave) nos tempos 1 e 3
    for i, (start, length, _) in enumerate(CHORDS):
        root = mtof(BASS[i])
        if start < 2.0:
            add(low, m.bass_note(root, 1.9) * 0.5, 0.0, gain=0.32)
            continue
        if start >= 12.5:
            add(low, m.bass_note(root, 2.4), start, gain=0.36)
            continue
        hits = np.arange(0, length - 1e-6, 1.0) if length >= 1.0 else [0.0]
        for h in hits:
            add(low, pizz(root, 0.9, 1.0), start + h, gain=0.30)
            add(low, m.bass_note(root, 0.45), start + h, gain=0.18)

    # Guizos: colcheias de 2,0 a 10,0; semicolcheias no trecho da oferta
    tt = 2.0
    k = 0
    while tt < 12.5 - 1e-6:
        dense = 10.0 <= tt < 12.5
        step = BEAT / 4 if dense else BEAT / 2
        accent = (k % (4 if dense else 2)) == (2 if dense else 1)
        v = 1.0 if accent else 0.55
        add(dry, sleigh(v), tt + rng.uniform(-0.004, 0.004), gain=0.05, pan=0.25 if k % 2 else -0.25)
        tt += step
        k += 1

    # Percussão leve
    kicks = [b for b in np.arange(2.0, 12.5, 1.0)]
    for kt in kicks:
        add(dry, m.kick(), kt, gain=0.42)
    for st in np.arange(2.5, 12.5, 1.0):
        if st >= 4.0:
            s = m.snap()
            add(dry, s, st, gain=0.14)
            add(wet, s, st, gain=0.16)

    # Sinos, impactos e transições
    for when in (0.0, 12.5):
        g = chime_gliss(74, 14, 0.45)
        add(dry, g, when, gain=0.06)
        add(wet, g, when, gain=0.10)
    add(dry, m.impact(2.4, 0.7), 0.0, gain=0.34)
    add(dry, m.impact(2.4, 0.7), 6.0, gain=0.26)
    add(dry, m.impact(2.4, 0.8), 10.0, gain=0.34)
    add(dry, m.impact(3.0, 0.9), 12.5, gain=0.40)
    add(wet, m.reverse_swell(0.9), 9.1, gain=0.08)
    add(wet, m.reverse_swell(0.9), 11.6, gain=0.09)
    for wt in (2.0, 3.0, 4.0, 5.0, 6.0):
        add(dry, swish(0.34), wt - 0.17, gain=0.07, pan=0.0)
    add(dry, swish(0.5), 0.05, gain=0.05)

    # Sidechain suave
    duck = np.ones(N)
    rel = int(0.28 * SR)
    curve = 1 - 0.35 * np.exp(-np.linspace(0, 5, rel))
    for kt in kicks:
        i0 = int(kt * SR)
        nn = min(rel, N - i0)
        duck[i0:i0 + nn] = np.minimum(duck[i0:i0 + nn], curve[:nn])
    pad *= duck[:, None]
    low *= duck[:, None]

    ir = m.reverb_ir(3.0, 3.8)
    rev = m.convolve(wet + pad * 0.4, ir)
    mix = dry + pad + low + rev * 0.6
    mix = fft_filter(mix, lo=30)
    mix = mix / np.max(np.abs(mix)) * 0.9
    mix = np.tanh(1.25 * mix) / np.tanh(1.25)
    fade = int(0.8 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 1.5
    fin = int(0.004 * SR)
    mix[:fin] *= np.linspace(0, 1, fin)[:, None]
    mix *= 0.89 / np.max(np.abs(mix))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("trilha de Natal:", OUT)


if __name__ == "__main__":
    main()
