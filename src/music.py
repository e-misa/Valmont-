"""Trilha original da campanha VALMONT Gênese (15 s, 120 BPM, Ré menor).

Toda a música é sintetizada aqui, nota por nota, sem samples de terceiros:
a trilha é uma obra original deste projeto e pode ser usada comercialmente
pela VALMONT Brasil sem licenças adicionais.

Estrutura sincronizada com os cortes do vídeo (1 tempo = 0,5 s):
  0,0 s  impacto grave + pad + "tique-taque" de relógio (gancho)
  2,0 s  entra o groove (kick meio-tempo, estalo, baixo)
  3,25 / 4,5 / 5,75 s  whooshes nas transições entre modelos
  7,0 s  impacto da composição dos 4 modelos / preço
  10,0 s impacto da oferta (riser antes)
  12,0 s assinatura da marca: bateria sai, acorde final com sino

Saída: build/trilha.wav (48 kHz, estéreo, 32-bit float).
"""
from pathlib import Path
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/trilha.wav"

SR = 48000
DUR = 15.0
N = int(SR * DUR)
BPM = 120
BEAT = 60.0 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(7)


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def t_axis(n):
    return np.arange(n) / SR


def add(buf, sig, start, gain=1.0, pan=0.0):
    """Mistura um sinal mono ou estéreo em buf a partir de start (s)."""
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


def fft_filter(x, lo=None, hi=None, slope=2):
    """Filtro de fase zero por FFT (passa-alta lo / passa-baixa hi)."""
    n = len(x)
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if hi is not None:
        g *= 1 / np.sqrt(1 + (f / hi) ** (2 * slope))
    if lo is not None:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * slope))
    if X.ndim == 2:
        g = g[:, None]
    return np.fft.irfft(X * g, n=n, axis=0)


def one_pole_lp_sweep(x, f0, f1):
    """Passa-baixa de 1 polo com corte varrendo de f0 a f1 (Hz, exponencial)."""
    n = len(x)
    fc = f0 * (f1 / f0) ** (np.arange(n) / max(n - 1, 1))
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    s = 0.0
    for i in range(n):
        s = a[i] * s + (1 - a[i]) * x[i]
        y[i] = s
    return y


def env_adsr(n, a, d, s, r, sustain_len=None):
    t = t_axis(n)
    e = np.ones(n) * s
    ai = int(a * SR)
    di = int(d * SR)
    if ai > 0:
        e[:ai] = np.linspace(0, 1, ai) ** 1.5
    e[ai:ai + di] = np.linspace(1, s, len(e[ai:ai + di]))
    ri = int(r * SR)
    if ri > 0 and ri < n:
        e[-ri:] *= np.linspace(1, 0, ri) ** 2
    return e


# --------------------------------------------------------------------- vozes
def supersaw(freq, n, voices=5, detune=0.012, harmonics=28):
    t = t_axis(n)
    out = np.zeros(n)
    for v in range(voices):
        dv = (v - (voices - 1) / 2) / ((voices - 1) / 2) * detune
        f = freq * (1 + dv)
        ph = rng.uniform(0, 2 * np.pi)
        for k in range(1, harmonics + 1):
            if f * k > 9000:
                break
            out += np.sin(2 * np.pi * f * k * t + ph * k) / k * np.exp(-k / 9.0)
    return out / voices


def pad_chord(notes, length, attack=0.6, release=0.9):
    n = int((length + release) * SR)
    sig_l = np.zeros(n)
    sig_r = np.zeros(n)
    for i, m in enumerate(notes):
        f = mtof(m)
        a = supersaw(f, n)
        b = supersaw(f * 1.003, n)
        p = (i / max(len(notes) - 1, 1)) * 2 - 1
        sig_l += a * (1 - 0.35 * p) + b * 0.4
        sig_r += b * (1 + 0.35 * p) + a * 0.4
    env = env_adsr(n, attack, 0.4, 0.85, release)
    st = np.stack([sig_l * env, sig_r * env], axis=1)
    st = fft_filter(st, lo=110, hi=1500, slope=2)
    return st / (len(notes) * 1.6)


def epiano(freq, length=1.2, vel=1.0):
    """Tecla elétrica/sino suave (FM leve) para o arpejo."""
    n = int(length * SR)
    t = t_axis(n)
    mod = np.sin(2 * np.pi * freq * 3.0 * t) * (1.6 * np.exp(-t * 9))
    car = np.sin(2 * np.pi * freq * t + mod)
    car += 0.25 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 6)
    env = np.exp(-t * 3.2) * (1 - np.exp(-t * 900))
    return car * env * vel


def bell(freq, length=3.5):
    n = int(length * SR)
    t = t_axis(n)
    partials = [(1, 1.0, 1.2), (2.0, 0.45, 1.8), (2.76, 0.3, 2.6), (5.4, 0.12, 4.0), (8.93, 0.05, 6.0)]
    out = np.zeros(n)
    for ratio, amp, dec in partials:
        out += amp * np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t * dec)
    return out * (1 - np.exp(-t * 2000))


def bass_note(freq, length):
    n = int(length * SR)
    t = t_axis(n)
    s = np.sin(2 * np.pi * freq * t) + 0.18 * np.sin(2 * np.pi * freq * 2 * t)
    s = np.tanh(1.6 * s) / np.tanh(1.6)
    env = (1 - np.exp(-t * 300)) * np.exp(-t * 0.9)
    rel = int(0.06 * SR)
    env[-rel:] *= np.linspace(1, 0, rel)
    return s * env


def kick(length=0.6):
    n = int(length * SR)
    t = t_axis(n)
    f = 46 + 95 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 6.5)
    click = fft_filter(rng.standard_normal(n), lo=2500, hi=7000) * np.exp(-t * 250) * 0.25
    return np.tanh(1.4 * (body + click))


def snap(length=0.35):
    """Estalo de dedos/rim seco (elegante, sem caixa pesada)."""
    n = int(length * SR)
    t = t_axis(n)
    noise = fft_filter(rng.standard_normal(n), lo=1200, hi=6500)
    env = np.exp(-t * 38)
    body = np.sin(2 * np.pi * 1850 * t) * np.exp(-t * 60) * 0.3
    return (noise * env + body) * 0.9


def tick(pitch=1.0, length=0.08):
    """Tique de relógio: transiente metálico curto."""
    n = int(length * SR)
    t = t_axis(n)
    s = np.sin(2 * np.pi * 4200 * pitch * t) * np.exp(-t * 180)
    s += 0.6 * np.sin(2 * np.pi * 6900 * pitch * t) * np.exp(-t * 260)
    s += fft_filter(rng.standard_normal(n), lo=5000, hi=12000) * np.exp(-t * 300) * 0.5
    return s


def impact(length=2.8, depth=1.0):
    n = int(length * SR)
    t = t_axis(n)
    f = 32 + 60 * np.exp(-t * 9)
    ph = 2 * np.pi * np.cumsum(f) / SR
    boom = np.sin(ph) * np.exp(-t * 2.2) * depth
    air = fft_filter(rng.standard_normal(n), lo=300, hi=3000) * np.exp(-t * 5) * 0.18
    return np.tanh(1.2 * (boom + air))


def whoosh(length=0.45, up=False):
    n = int(length * SR)
    x = rng.standard_normal(n)
    f0, f1 = (500, 7000) if up else (7000, 600)
    y = one_pole_lp_sweep(x, f0, f1)
    y = fft_filter(y, lo=250)
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t) ** 2
    return y * env


def riser(length=1.0):
    n = int(length * SR)
    x = rng.standard_normal(n)
    y = one_pole_lp_sweep(x, 300, 9000)
    y = fft_filter(y, lo=200)
    t = np.linspace(0, 1, n)
    return y * t ** 2.2


def reverse_swell(length=1.0):
    n = int(length * SR)
    x = fft_filter(rng.standard_normal(n), lo=1500, hi=11000)
    t = np.linspace(0, 1, n)
    return x * t ** 3


def reverb_ir(rt60=2.4, length=3.2):
    n = int(length * SR)
    t = t_axis(n)
    decay = np.exp(-6.91 * t / rt60)
    ir = rng.standard_normal((n, 2)) * decay[:, None]
    ir = fft_filter(ir, lo=180, hi=6500)
    ir[: int(0.012 * SR)] = 0  # pré-delay
    return ir / np.sqrt((ir ** 2).sum(axis=0, keepdims=True))


def convolve(x, ir):
    n = len(x) + len(ir) - 1
    nfft = 1 << (n - 1).bit_length()
    X = np.fft.rfft(x, nfft, axis=0)
    H = np.fft.rfft(ir, nfft, axis=0)
    return np.fft.irfft(X * H, nfft, axis=0)[: len(x)]


# ------------------------------------------------------------------- arranjo
CHORDS = [
    (0.0, 2.0, [50, 53, 57, 60, 64]),   # Dm9
    (2.0, 2.0, [46, 50, 53, 57, 60]),   # Bbmaj9
    (4.0, 2.0, [43, 46, 50, 53, 57]),   # Gm9
    (6.0, 1.0, [45, 50, 52, 55]),       # A7sus4
    (7.0, 1.0, [45, 49, 52, 55, 64]),   # A7
    (8.0, 2.0, [50, 53, 57, 60, 64]),   # Dm9
    (10.0, 2.0, [46, 50, 53, 57, 62]),  # Bbmaj7(9)
    (12.0, 3.0, [41, 48, 52, 55, 57, 64]),  # Fmaj9 (resolução)
]
BASS = [38, 34, 31, 33, 33, 38, 34, 29]


def main():
    dry = np.zeros((N, 2))
    wet_send = np.zeros((N, 2))
    pad_bus = np.zeros((N, 2))
    bass_bus = np.zeros((N, 2))

    # Pad
    for (start, length, notes) in CHORDS:
        p = pad_chord(notes, length + 0.15, attack=0.35 if start == 0 else 0.25, release=1.2 if start >= 12 else 0.5)
        add(pad_bus, p, start - (0.0 if start == 0 else 0.05), gain=0.55)

    # Arpejo (colcheias), registro agudo
    pattern = [0, 2, 4, 3, 1, 3, 2, 4]
    for (start, length, notes) in CHORDS:
        if start >= 12:
            continue
        up = [m + 12 for m in notes[1:]] + [notes[1] + 24]
        steps = int(length / (BEAT / 2))
        for k in range(steps):
            t0 = start + k * BEAT / 2
            m = up[pattern[k % len(pattern)] % len(up)]
            vel = 0.55 + 0.25 * ((k % 4) == 0) + rng.uniform(-0.05, 0.05)
            pan = [-0.45, 0.45][k % 2]
            note = epiano(mtof(m), 1.1, vel)
            add(dry, note, t0, gain=0.11, pan=pan)
            add(wet_send, note, t0, gain=0.09, pan=pan)

    # Sinos na abertura e no final
    for m, d in [(74, 0.0), (81, 0.02)]:
        b = bell(mtof(m), 3.0)
        add(dry, b, d, gain=0.06, pan=-0.2)
        add(wet_send, b, d, gain=0.10, pan=0.2)
    for m, d in [(65, 0.0), (72, 0.03), (76, 0.06), (79, 0.09)]:
        b = bell(mtof(m), 3.2)
        add(dry, b, 12.0 + d, gain=0.06, pan=(d * 8 - 0.3))
        add(wet_send, b, 12.0 + d, gain=0.12, pan=-(d * 8 - 0.3))

    # Baixo (do compasso 2 ao 6), ritmo sincopado
    for i, (start, length, _) in enumerate(CHORDS):
        root = mtof(BASS[i])
        if start < 2.0:
            add(bass_bus, bass_note(root, 1.9) * 0.6, 0.0, gain=0.35)
            continue
        if start >= 12.0:
            add(bass_bus, bass_note(root, 2.9), start, gain=0.38)
            continue
        hits = [0.0, 0.75, 1.5] if length >= 2.0 else [0.0, 0.5]
        for h in hits:
            if h >= length:
                continue
            add(bass_bus, bass_note(root, 0.42 if h < length - 0.5 else length - h - 0.02), start + h, gain=0.42)

    # Bateria
    kick_times = []
    for bar in range(1, 6):  # 2,0 s a 12,0 s
        b0 = bar * BAR
        kick_times += [b0, b0 + 2 * BEAT]
        if bar in (2, 4):
            kick_times.append(b0 + 3.5 * BEAT)
    kick_times = sorted(set(round(k, 4) for k in kick_times + [7.0, 10.0]))
    for kt in kick_times:
        add(dry, kick(), kt, gain=0.62)

    for bar in range(1, 6):
        b0 = bar * BAR
        for bt in (1, 3):
            s = snap()
            add(dry, s, b0 + bt * BEAT, gain=0.20, pan=0.1)
            add(wet_send, s, b0 + bt * BEAT, gain=0.22)

    # Tique-taque (colcheias, semicolcheias no clímax)
    t0 = 0.0
    k = 0
    while t0 < 12.0 - 1e-6:
        dense = 8.0 <= t0 < 12.0
        step = BEAT / 4 if dense else BEAT / 2
        pitch = 1.0 if k % 2 == 0 else 0.84
        vel = 0.9 if k % 2 == 0 else 0.6
        if dense and k % 2:
            vel = 0.35
        add(dry, tick(pitch), t0, gain=0.055 * vel, pan=0.35 if k % 2 else -0.35)
        t0 += step
        k += 1

    # Impactos, risers e whooshes nas viradas
    add(dry, impact(2.6, 1.0), 0.0, gain=0.5)
    add(dry, impact(2.6, 0.9), 7.0, gain=0.42)
    add(dry, impact(2.6, 1.0), 10.0, gain=0.45)
    add(dry, impact(3.0, 1.1), 12.0, gain=0.55)
    add(wet_send, riser(1.0), 9.0, gain=0.10)
    add(dry, riser(1.0), 9.0, gain=0.06)
    add(wet_send, reverse_swell(1.0), 11.0, gain=0.10)
    for wt in (2.0, 3.25, 4.5, 5.75):
        w = whoosh(0.42)
        add(dry, w, wt - 0.21, gain=0.06, pan=0.0)
    add(dry, whoosh(0.6, up=True), 6.7, gain=0.05)

    # Sidechain (o kick "respira" o pad e o baixo)
    duck = np.ones(N)
    rel = int(0.32 * SR)
    curve = 1 - 0.55 * np.exp(-np.linspace(0, 5, rel))
    for kt in kick_times:
        i0 = int(kt * SR)
        n = min(rel, N - i0)
        duck[i0:i0 + n] = np.minimum(duck[i0:i0 + n], curve[:n])
    pad_bus *= duck[:, None]
    bass_bus *= duck[:, None]

    # Reverb
    ir = reverb_ir(2.6, 3.4)
    wet = convolve(wet_send + pad_bus * 0.35, ir)
    mix = dry + pad_bus + bass_bus + wet * 0.55

    # Master: leve cola + limitação suave
    mix = fft_filter(mix, lo=28)
    peak = np.max(np.abs(mix))
    mix = mix / peak * 0.9
    mix = np.tanh(1.3 * mix) / np.tanh(1.3)

    # Fade final para não cortar seco
    fade = int(0.7 * SR)
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
    print("trilha:", OUT, f"{DUR:.1f}s")


if __name__ == "__main__":
    main()
