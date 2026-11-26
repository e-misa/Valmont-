"""Campanha de vendas VALMONT — 18 s, 1080x1920, 30 fps.

Fontes de imagem (somente produtos VALMONT reais):
  * Filmagem real enviada pela marca (assets/videos/valmont-referencias.mov):
    mão segurando cada modelo, vista lateral, fecho e mesa. Usada 1:1 no
    tempo, apenas recortada/ampliada (movimento de câmera). Nada é redesenhado.
  * Fotos de estúdio (assets/fotos): closes macro e composições de preço,
    oferta e final, sobre superfície de pedra clara (ver src/flatlay.py).

Uso:
  python3 src/render_campanha.py                 # vídeo completo
  python3 src/render_campanha.py --still 0.5 11  # quadros PNG de conferência
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render as base  # noqa: E402
import render_natal as rn  # noqa: E402
import flatlay as fl  # noqa: E402
from render import (  # noqa: E402
    GOLD, GOLD_HI, GOLD_LO, ROOT, e_cubic, e_out_cubic, e_sine, gold, gradient_fill,
    lerp, put, seg, text_layer,
)

W, H, FPS, DUR = 1080, 1920, 30, 18.0
NFRAMES = int(round(FPS * DUR))
BUILD = ROOT / "build"
OUTPUT = ROOT / "output"
FOOTAGE = ROOT / "assets/videos/valmont-referencias.mov"
SRC_W, SRC_H = 512, 910
BLACK = (10, 10, 11)
WHITE = (255, 255, 255)

# ------------------------------------------------------------------ roteiro
# (início, fim, tipo, parâmetros). Filmagem: src = segundo do vídeo original.
SHOTS = [
    (0.0, 1.0, "still", dict(key="macro_gold", z=(1.00, 1.07), c=(0.5, 0.50))),
    (1.0, 2.0, "clip", dict(src=7.00, z=(1.12, 1.16), c=(0.50, 0.50), label=None)),
    (2.0, 3.0, "clip", dict(src=0.45, z=(1.10, 1.14), c=(0.50, 0.55), label="SILVER")),
    (3.0, 4.0, "clip", dict(src=25.80, z=(1.12, 1.17), c=(0.52, 0.56), label="SILVER")),
    (4.0, 5.0, "clip", dict(src=31.20, z=(1.12, 1.18), c=(0.50, 0.50), label="GOLD")),
    (5.0, 6.0, "clip", dict(src=9.40, z=(1.15, 1.20), c=(0.52, 0.62), label="GOLD")),
    (6.0, 7.0, "clip", dict(src=19.55, z=(1.10, 1.14), c=(0.50, 0.58), label="ROSÉ")),
    (7.0, 8.0, "clip", dict(src=23.45, z=(1.12, 1.16), c=(0.50, 0.46), label="ROSÉ")),
    (8.0, 9.0, "clip", dict(src=14.05, z=(1.10, 1.15), c=(0.52, 0.58), label="BLACK")),
    (9.0, 10.0, "still", dict(key="macro_black", z=(1.00, 1.07), c=(0.5, 0.47), label="BLACK")),
    (10.0, 13.0, "still", dict(key="four", z=(1.00, 1.05), c=(0.5, 0.5))),
    (13.0, 16.0, "still", dict(key="duo", z=(1.00, 1.05), c=(0.5, 0.36))),
    (16.0, 18.0, "still", dict(key="four", z=(1.05, 1.08), c=(0.5, 0.5))),
]
# Cortes secos no tempo da música: nunca há dois relógios sobrepostos no mesmo quadro.


# Versão 2: mais fiel ao briefing (linho bege, profundidade de campo nos macros,
# aproximação suave no mostrador do Gold). Ative com --versao 2.
SHOTS_V2 = [
    (0.0, 1.2, "still", dict(key="macro_gold_linho", z=(1.00, 1.08), c=(0.5, 0.50))),
    (1.2, 2.0, "clip", dict(src=7.20, z=(1.12, 1.15), c=(0.50, 0.50), label=None)),
    (2.0, 3.0, "clip", dict(src=0.45, z=(1.10, 1.14), c=(0.50, 0.55), label="SILVER")),
    (3.0, 4.0, "clip", dict(src=25.80, z=(1.12, 1.17), c=(0.52, 0.56), label="SILVER")),
    (4.0, 5.0, "clip", dict(src=31.20, z=(1.12, 1.30), c=(0.50, 0.50), label="GOLD")),
    (5.0, 6.0, "clip", dict(src=9.40, z=(1.15, 1.20), c=(0.52, 0.62), label="GOLD")),
    (6.0, 7.0, "clip", dict(src=19.55, z=(1.10, 1.14), c=(0.50, 0.58), label="ROSÉ")),
    (7.0, 8.0, "clip", dict(src=23.45, z=(1.12, 1.16), c=(0.50, 0.46), label="ROSÉ")),
    (8.0, 9.0, "clip", dict(src=14.05, z=(1.10, 1.15), c=(0.52, 0.58), label="BLACK")),
    (9.0, 10.0, "still", dict(key="macro_black_linho", z=(1.00, 1.07), c=(0.5, 0.47), label="BLACK")),
    (10.0, 13.0, "still", dict(key="four_linho", z=(1.00, 1.05), c=(0.5, 0.5))),
    (13.0, 16.0, "still", dict(key="duo", z=(1.00, 1.05), c=(0.5, 0.36))),
    (16.0, 18.0, "still", dict(key="four_linho", z=(1.05, 1.08), c=(0.5, 0.5))),
]


# --------------------------------------------------------------- filmagem
def load_footage():
    """Extrai só os trechos usados (mais folga para os dissolves)."""
    cache = BUILD / "campanha_footage.npz"
    clips = {}
    if cache.exists():
        d = np.load(cache)
        clips = {float(k): d[k] for k in d.files}
        if all(p["src"] in clips for _a, _b, kind, p in SHOTS if kind == "clip"):
            return clips
    for _a, _b, kind, p in SHOTS:
        if kind != "clip" or p["src"] in clips:
            continue
        start = max(0.0, p["src"] - 0.1)
        n = int(round((1.0 + 0.3) * FPS))
        raw = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(FOOTAGE),
             "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, check=True).stdout
        arr = np.frombuffer(raw, np.uint8).reshape(-1, SRC_H, SRC_W, 3)
        clips[p["src"]] = arr
    BUILD.mkdir(exist_ok=True)
    np.savez(cache, **{str(k): v for k, v in clips.items()})
    return clips


CLIPS: dict = {}
STILLS: dict = {}


def init():
    if CLIPS:
        return
    fl.init()
    CLIPS.update(load_footage())
    for _a, _b, kind, p in SHOTS:
        if kind == "still" and p["key"] not in STILLS:
            STILLS[p["key"]] = still(p["key"])


def clip_frame(p, tl, z, c):
    arr = CLIPS[p["src"]]
    i = int(round((tl + 0.1) * FPS))
    i = max(0, min(len(arr) - 1, i))
    img = Image.fromarray(arr[i])
    cw, ch = SRC_W / z, SRC_H / z
    cx = min(max(c[0] * SRC_W, cw / 2), SRC_W - cw / 2)
    cy = min(max(c[1] * SRC_H, ch / 2), SRC_H - ch / 2)
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    out = img.resize((W, H), Image.LANCZOS, box=box)
    return out.filter(ImageFilter.UnsharpMask(radius=1.8, percent=55, threshold=2))


# --------------------------------------------------------- composições
def still(key):
    """Composições de estúdio (renderizadas 1x e guardadas em build/)."""
    path = BUILD / f"campanha_{key}.png"
    if path.exists():
        return Image.open(path).convert("RGB")
    if key == "macro_gold":
        w, h = 1296, 2304
        c = fl.stone(w, h, seed=11)
        c = fl.place(c, "gold", (w * 0.5, h * 0.60), 1130, -8.0)
    elif key == "macro_black":
        w, h = 1296, 2304
        c = fl.stone(w, h, seed=13)
        c = fl.place(c, "black", (w * 0.5, h * 0.56), 1060, 7.0)
    elif key == "four":
        w, h = 1188, 2112
        c = fl.stone(w, h, seed=21)
        sx = w / 1080
        for name, (x, y), a in [("silver", (290, 420), -4), ("gold", (800, 470), 3),
                                ("rose", (285, 1500), 2.5), ("black", (795, 1450), -3)]:
            c = fl.place(c, name, (x * sx, y * sx), 380 * sx, a)
    elif key == "macro_gold_linho":
        w, h = 1296, 2304
        c = fl.linen(w, h, seed=11)
        c = fl.place(c, "gold", (w * 0.5, h * 0.60), 1130, -8.0)
        c = fl.depth_of_field(c, (w * 0.5, h * 0.60), 600, 3.2)
    elif key == "macro_black_linho":
        w, h = 1296, 2304
        c = fl.linen(w, h, seed=13)
        c = fl.place(c, "black", (w * 0.5, h * 0.56), 1060, 7.0)
        c = fl.depth_of_field(c, (w * 0.5, h * 0.56), 560, 3.2)
    elif key == "four_linho":
        w, h = 1188, 2112
        c = fl.linen(w, h, seed=21)
        sx = w / 1080
        for name, (x, y), a in [("silver", (290, 420), -4), ("gold", (800, 470), 3),
                                ("rose", (285, 1500), 2.5), ("black", (795, 1450), -3)]:
            c = fl.place(c, name, (x * sx, y * sx), 380 * sx, a)
    elif key == "duo":
        w, h = 1166, 2074
        c = fl.stone(w, h, seed=31, base_col=(226, 214, 196))
        sx = w / 1080
        for name, (x, y), a in [("gold", (285, 640), -2), ("black", (795, 640), 2)]:
            c = fl.place(c, name, (x * sx, y * sx), 440 * sx, a)
    else:
        raise KeyError(key)
    img = Image.fromarray(np.clip(c + 0.5, 0, 255).astype(np.uint8))
    BUILD.mkdir(exist_ok=True)
    img.save(path)
    return img


def still_frame(key, z, c):
    """Movimento de câmera sobre a composição (zoom relativo ao quadro 9:16)."""
    img = STILLS[key]
    sw, sh = img.size  # composição maior que o quadro (folga para o zoom)
    cw, ch = sw / z, sh / z
    cx = min(max(c[0] * sw, cw / 2), sw - cw / 2)
    cy = min(max(c[1] * sh, ch / 2), sh - ch / 2)
    return img.resize((W, H), Image.LANCZOS, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))


# --------------------------------------------------------------- tipografia
def black_box(img, x0, y0, x1, y1, alpha=0.9, r=10):
    if alpha <= 0:
        return
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=BLACK + (int(255 * alpha),))


@lru_cache(maxsize=1)
def logo_img(width=300):
    lh = int(base.LOGO_MASK.height * width / base.LOGO_MASK.width)
    m = base.LOGO_MASK.resize((width, lh), Image.LANCZOS)
    logo = Image.new("RGBA", (width, lh), GOLD + (0,))
    logo.putalpha(m)
    return gradient_fill(logo, GOLD_HI, GOLD_LO, mid=GOLD)


def paste_logo(img, cx, cy, alpha, width=300):
    logo = logo_img(width)
    a = logo.getchannel("A").point(lambda v, o=alpha: int(v * o + 0.5))
    img.paste(logo.convert("RGB"), (int(cx - logo.width / 2), int(cy - logo.height / 2)), a)


def label(img, text, a):
    """Etiqueta do modelo, estilo faixa preta com letras brancas."""
    if a <= 0:
        return
    lay = text_layer(f"GÊNESE  ·  {text}", "sans_m", 30, WHITE, 6.0)
    bb = lay[0].getchannel("A").getbbox()
    tw = bb[2] - bb[0]
    x0, x1 = 540 - tw / 2 - 30, 540 + tw / 2 + 30
    black_box(img, x0, 290, x1, 362, 0.85 * a, r=8)
    put(img, lay, 540, 339, a)


@lru_cache(maxsize=1)
def button_img(w=560, h=100):
    S = 3
    m = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=h * S // 2, fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    body = gradient_fill(Image.merge("RGBA", (m, m, m, m)), GOLD_HI, GOLD_LO, mid=GOLD).convert("RGB")
    li, lox, loy = text_layer("COMPRE AGORA", "sans_sb", 32, (14, 14, 14), 5.0)
    a = li.getchannel("A")
    bb = a.getbbox()
    body.paste(li.convert("RGB"), (int(round(w / 2 - lox)), int(round(h / 2 - (bb[1] + bb[3]) / 2))), a)
    return body, m


# ------------------------------------------------------------- sobreposições
def overlays(img, t):
    # Cena 1: VALMONT + frase (0–2 s)
    if t < 2.0:
        a = e_out_cubic(seg(t, 0.06, 0.40)) * (1 - e_sine(seg(t, 1.86, 1.98)))
        black_box(img, 170, 286, 910, 540, 0.88 * a, r=12)
        paste_logo(img, 540, 372, a, 300)
        a2 = e_out_cubic(seg(t, 0.22, 0.60)) * (1 - e_sine(seg(t, 1.86, 1.98)))
        put(img, text_layer("A elegância está nos detalhes.", "serif_it", 52, WHITE), 540, 500 + 10 * (1 - a2), a2)

    # Etiquetas dos modelos (2–10 s)
    for a0, b0, kind, p in SHOTS:
        lab = p.get("label")
        if lab and a0 <= t < b0:
            la = e_out_cubic(seg(t, a0 + 0.05, a0 + 0.25)) * (1 - e_sine(seg(t, b0 - 0.08, b0)))
            label(img, lab, la)

    # Cena 4: preço (10–13 s)
    if 10.0 <= t < 13.0:
        grow = e_cubic(seg(t, 10.0, 10.3))
        out = e_sine(seg(t, 12.88, 13.0))
        if grow > 0:
            hw = 540 * grow
            black_box(img, 540 - hw, 858, 540 + hw, 1122, 0.93 * (1 - out), r=0)
        ta = e_out_cubic(seg(t, 10.18, 10.5)) * (1 - out)
        tb = e_out_cubic(seg(t, 10.28, 10.62)) * (1 - out)
        put(img, text_layer("COLEÇÃO GÊNESE", "sans_m", 28, WHITE, 9.0), 540, 920 + 8 * (1 - ta), ta)
        rs = text_layer("R$", "sans_sb", 58, WHITE)
        val = text_layer("180,00", "sans_sb", 138, WHITE)
        cada = text_layer("cada", "sans_r", 42, WHITE)
        bbs = [l[0].getchannel("A").getbbox() for l in (rs, val, cada)]
        ws = [b[2] - b[0] for b in bbs]
        gap1, gap2 = 18, 22
        left = 540 - (ws[0] + gap1 + ws[1] + gap2 + ws[2]) / 2
        base_y = 1078 + 10 * (1 - tb)
        put(img, rs, left, base_y, tb, align="left")
        put(img, val, left + ws[0] + gap1, base_y, tb, align="left")
        put(img, cada, left + ws[0] + gap1 + ws[1] + gap2, base_y, tb, align="left")

    # Cena 5: oferta (13–16 s)
    if 13.0 <= t < 16.0:
        out = e_sine(seg(t, 15.88, 16.0))
        ba = e_out_cubic(seg(t, 13.0, 13.25)) * (1 - out)
        black_box(img, 120, 1100, 960, 1346, 0.93 * ba, r=12)
        a1 = e_out_cubic(seg(t, 13.12, 13.42)) * (1 - out)
        put(img, text_layer("LEVE 2 OU MAIS", "sans_m", 40, WHITE, 8.0), 540, 1166 + 8 * (1 - a1), a1)
        a2 = seg(t, 13.30, 13.62)
        ap = e_out_cubic(a2) * (1 - out)
        if ap > 0:
            g1 = text_layer("GANHE ", "sans_sb", 84, WHITE)
            pc = gold(text_layer("10%", "sans_sb", 84, GOLD))
            g2 = text_layer(" OFF", "sans_sb", 84, WHITE)
            bbs = [l[0].getchannel("A").getbbox() for l in (g1, pc, g2)]
            sp = 22
            ws = [bbs[0][2] - bbs[0][0], bbs[1][2] - bbs[1][0], bbs[2][2] - bbs[2][0]]
            left = 540 - (ws[0] + sp + ws[1] + sp + ws[2]) / 2
            y = 1296
            put(img, g1, left, y, ap, align="left")
            pcx = left + ws[0] + sp + ws[1] / 2
            pop = lerp(1.35, 1.0, e_out_cubic(a2))
            put(img, pc, pcx, y, ap, scale=pop)
            put(img, g2, left + ws[0] + sp + ws[1] + sp, y, ap, align="left")
            ul = e_out_cubic(seg(t, 13.55, 13.85)) * (1 - out)
            if ul > 0:
                d = ImageDraw.Draw(img)
                half = ws[1] / 2 * ul
                d.rectangle((pcx - half, y + 16, pcx + half, y + 20), fill=GOLD)

    # Cena 6: assinatura (16–18 s)
    if t >= 16.0:
        grow = e_cubic(seg(t, 16.0, 16.32))
        hh = 270 * grow
        black_box(img, 0, 990 - hh, W, 990 + hh, 0.94, r=0)
        la = e_out_cubic(seg(t, 16.15, 16.55))
        paste_logo(img, 540, 828, la, 360)
        ta = e_out_cubic(seg(t, 16.35, 16.75))
        put(img, text_layer("A simplicidade é a base da elegância.", "serif_it", 52, WHITE), 540, 1000 + 10 * (1 - ta), ta)
        bt = e_out_cubic(seg(t, 16.55, 16.95))
        if bt > 0:
            body, m = button_img()
            sw = seg(t, 17.15, 17.7)
            if 0 < sw < 1:
                arr = np.asarray(body).astype(np.float32)
                hh_, ww_ = arr.shape[:2]
                xx = np.arange(ww_)[None, :] + 0.6 * np.arange(hh_)[:, None]
                cpos = lerp(-0.25 * ww_, 1.3 * ww_, sw)
                g = np.exp(-((xx - cpos) / (0.07 * ww_)) ** 2)[..., None] * 0.45
                body = Image.fromarray((arr + (255 - arr) * g).astype(np.uint8))
            a = m.point(lambda v, o=bt: int(v * o + 0.5))
            img.paste(body, (540 - body.width // 2, int(1140 + 14 * (1 - bt) - body.height / 2)), a)


# ------------------------------------------------------------------ quadros
def shot_image(i, t):
    a, b, kind, p = SHOTS[i]
    pr = e_sine((t - a) / (b - a))
    z = lerp(p["z"][0], p["z"][1], pr)
    if kind == "clip":
        return clip_frame(p, t - a, z, p["c"])
    return still_frame(p["key"], z, p["c"])


def shot_index(t):
    for i, (a, b, _k, _p) in enumerate(SHOTS):
        if a <= t < b:
            return i
    return len(SHOTS) - 1


def render_frame(fi):
    init()
    t = fi / FPS
    i = shot_index(t)
    img = shot_image(i, t)
    overlays(img, t)
    return np.asarray(img, np.uint8).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", nargs="*", type=float)
    ap.add_argument("--out", default=str(OUTPUT / "valmont-campanha-18s-1080x1920.mp4"))
    ap.add_argument("--audio", default=str(BUILD / "trilha_campanha.wav"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--versao", type=int, default=1, choices=(1, 2))
    args = ap.parse_args()
    global SHOTS
    if args.versao == 2:
        SHOTS = SHOTS_V2
        if args.out == str(OUTPUT / "valmont-campanha-18s-1080x1920.mp4"):
            args.out = str(OUTPUT / "valmont-campanha-18s-v2-1080x1920.mp4")
    init()
    if args.still is not None:
        for ts in args.still:
            arr = np.frombuffer(render_frame(int(round(ts * FPS))), np.uint8).reshape(H, W, 3)
            pth = BUILD / f"camp_v{args.versao}_{ts:05.2f}.png"
            Image.fromarray(arr).save(pth)
            print(pth)
        return
    gain = rn.loudness_gain(args.audio)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", args.audio, "-map", "0:v", "-map", "1:a",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high", "-level", "4.2",
        "-x264-params", "keyint=30:min-keyint=1",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-af", f"volume={gain:.2f}dB,afade=t=out:st=17.4:d=0.6",
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
        "-t", f"{DUR}", "-movflags", "+faststart", args.out,
    ]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(args.workers, initializer=init) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=4)):
            proc.stdin.write(buf)
            if k % 60 == 0:
                print(f"  quadro {k}/{NFRAMES}", file=sys.stderr, flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg falhou")
    print("vídeo:", args.out)


if __name__ == "__main__":
    main()
