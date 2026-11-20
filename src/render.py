"""Renderizador do vídeo VALMONT Gênese — 1080x1920, 30 fps, 15 s.

Princípio: fidelidade absoluta ao produto. Os relógios NUNCA são redesenhados.
Cada quadro é montado a partir dos pixels das fotos originais de estúdio,
apenas reposicionados/escalados (movimento de câmera). O fundo de estúdio das
fotos é uniforme, então o quadro 9:16 é completado com a mesma cor de fundo,
sem emendas. Textos, faixas e o logotipo são camadas gráficas por cima.

Uso:
  python3 src/render.py                 # renderiza o vídeo completo
  python3 src/render.py --still 1.2 8.5 # exporta quadros PNG de conferência
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FOTOS = ROOT / "assets/fotos"
FONTS = ROOT / "assets/fonts"
BUILD = ROOT / "build"
OUTPUT = ROOT / "output"

W, H, FPS, DUR = 1080, 1920, 30, 15.0
NFRAMES = int(round(FPS * DUR))

# Paleta
INK = (22, 22, 24)
MUTED = (128, 128, 132)
WHITE = (255, 255, 255)
BAND = (12, 12, 13)
GOLD = (205, 168, 96)
GOLD_HI = (236, 211, 146)
GOLD_LO = (166, 128, 62)

FONT_FILES = {
    "serif_it": "CormorantGaramond-MediumItalic.ttf",
    "serif_it_reg": "CormorantGaramond-Italic.ttf",
    "serif": "CormorantGaramond-Medium.ttf",
    "sans_xl": "Montserrat-ExtraLight.ttf",
    "sans_l": "Montserrat-Light.ttf",
    "sans_r": "Montserrat-Regular.ttf",
    "sans_m": "Montserrat-Medium.ttf",
    "sans_sb": "Montserrat-SemiBold.ttf",
}


# ------------------------------------------------------------------ utilidades
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def seg(t, a, b):
    return clamp((t - a) / (b - a))


def lerp(a, b, p):
    return a + (b - a) * p


def e_sine(p):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(p))


def e_cubic(p):
    p = clamp(p)
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def e_quart(p):
    p = clamp(p)
    return 8 * p ** 4 if p < 0.5 else 1 - (-2 * p + 2) ** 4 / 2


def e_out_cubic(p):
    p = clamp(p)
    return 1 - (1 - p) ** 3


def e_out_expo(p):
    p = clamp(p)
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def smoothstep_arr(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- fotografias
PAD = 1100


class Photo:
    """Foto original do produto, com o fundo de estúdio estendido sem emenda.

    C = centro da caixa (px da foto), R = raio da caixa (px da foto).
    """

    def __init__(self, name, C, R):
        im = Image.open(FOTOS / f"genese-{name}.jpg").convert("RGB")
        a = np.asarray(im).astype(np.float32)
        bg = np.median(np.concatenate([a[:8, :8].reshape(-1, 3), a[:8, -8:].reshape(-1, 3),
                                       a[-8:, -8:].reshape(-1, 3)]), axis=0)
        self.bg = tuple(int(round(v)) for v in bg)
        h, w = a.shape[:2]
        # As fotos originais têm um fio escuro de recorte na borda externa
        # (fundo, longe do relógio). A moldura de 4 px vira cor de estúdio.
        b = 4
        a[:b, :] = bg
        a[-b:, :] = bg
        a[:, :b] = bg
        a[:, -b:] = bg
        # Uniformiza só o FUNDO de estúdio (variações de 1–2 tons e ruído de
        # JPEG) para que a extensão do cenário não tenha degrau visível.
        # Pixels do produto e suas sombras (diferença > 12 tons) ficam intactos.
        yy, xx = np.mgrid[0:h, 0:w]
        dist = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)).astype(np.float32)
        edge = smoothstep_arr(dist / 120.0)
        diff = np.abs(a - bg).max(axis=2)
        keep = (smoothstep_arr((diff - 4.0) / 8.0) * np.maximum(edge, smoothstep_arr((diff - 9.0) / 10.0)))[..., None]
        a = bg + (a - bg) * keep
        core = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
        canvas = Image.new("RGB", (w + 2 * PAD, h + 2 * PAD), self.bg)
        canvas.paste(core, (PAD, PAD))
        self.im = canvas
        self.C = C
        self.R = R

    def view(self, w, h, z, fx, fy, px, py, focus=None):
        """Recorte w x h onde o ponto focal da foto cai em (px, py).

        z = raio da caixa em px do quadro (controla o zoom).
        focus = ponto da foto (default: centro da caixa).
        """
        s = z / self.R
        Fx, Fy = focus if focus is not None else self.C
        x0 = Fx - px / s
        y0 = Fy - py / s
        box = (x0 + PAD, y0 + PAD, x0 + w / s + PAD, y0 + h / s + PAD)
        tile = self.im.resize((int(w), int(h)), Image.LANCZOS, box=box)
        if s > 1.25:
            pct = int(min(70, 18 + 30 * (s - 1.25)))
            tile = tile.filter(ImageFilter.UnsharpMask(radius=1.3, percent=pct, threshold=2))
        return tile


GEOM = {
    "black": ((597, 583), 271),
    "rose": ((597, 583), 271),
    "silver": ((597, 583), 271),
    "gold": ((637, 625), 290),
}
NAMES = {"silver": "Silver", "gold": "Gold", "rose": "Rosé", "black": "Black"}
ORDER = ["silver", "gold", "rose", "black"]

PHOTOS: dict[str, Photo] = {}
LOGO_MASK: Image.Image | None = None


def init_assets():
    global LOGO_MASK
    if PHOTOS:
        return
    for k, (C, R) in GEOM.items():
        PHOTOS[k] = Photo(k, C, R)
    LOGO_MASK = Image.open(ROOT / "assets/marca/valmont-logo-alpha.png").convert("L")


def to_src(photo: Photo, rel):
    """Converte deslocamento relativo ao centro (em raios) para px da foto."""
    return (photo.C[0] + rel[0] * photo.R, photo.C[1] + rel[1] * photo.R)


# ------------------------------------------------------------------- tipografia
@lru_cache(maxsize=None)
def font(key, size):
    return ImageFont.truetype(str(FONTS / FONT_FILES[key]), size)


@lru_cache(maxsize=None)
def text_layer(text, fkey, size, color, tracking=0.0):
    """Camada RGBA do texto. Retorna (img, ox, oy): ox = centro horizontal,
    oy = linha de base, em px da camada."""
    f = font(fkey, size)
    asc, desc = f.getmetrics()
    if tracking:
        adv = [f.getlength(ch) for ch in text]
        width = sum(adv) + tracking * (len(text) - 1)
    else:
        width = f.getlength(text)
    pad = int(size * 0.5) + 8
    img = Image.new("RGBA", (int(math.ceil(width)) + 2 * pad, asc + desc + 2 * pad), color + (0,))
    d = ImageDraw.Draw(img)
    if tracking:
        x = pad
        for ch, a in zip(text, adv):
            d.text((x, pad + asc), ch, font=f, fill=color + (255,), anchor="ls")
            x += a + tracking
    else:
        d.text((pad, pad + asc), text, font=f, fill=color + (255,), anchor="ls")
    return img, pad + width / 2.0, pad + asc


def gradient_fill(layer: Image.Image, top, bottom, mid=None):
    """Recolore uma camada RGBA com gradiente vertical (efeito metal dourado)."""
    w, h = layer.size
    a = layer.getchannel("A")
    bbox = a.getbbox() or (0, 0, w, h)
    y0, y1 = bbox[1], bbox[3]
    ys = np.clip((np.arange(h) - y0) / max(1, (y1 - y0)), 0, 1)[:, None]
    top = np.array(top, np.float32)
    bottom = np.array(bottom, np.float32)
    if mid is not None:
        mid = np.array(mid, np.float32)
        col = np.where(ys < 0.5, top + (mid - top) * (ys / 0.5), mid + (bottom - mid) * ((ys - 0.5) / 0.5))
    else:
        col = top + (bottom - top) * ys
    rgb = np.repeat(col[:, None, :], w, axis=1).reshape(h, w, 3)
    out = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    out.putalpha(a)
    return out


def gold(layer):
    """Mesma camada de texto, preenchida com gradiente dourado."""
    img, ox, oy = layer
    return gradient_fill(img, GOLD_HI, GOLD_LO), ox, oy


def put(frame: Image.Image, layer, cx, by, opacity=1.0, scale=1.0, align="center"):
    """Cola camada de texto: (cx, by) = centro horizontal e linha de base.
    align='left' usa cx como margem esquerda."""
    if opacity <= 0.003:
        return
    img, ox, oy = layer
    if scale != 1.0:
        nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        ox, oy = ox * scale, oy * scale
    if align == "left":
        f = font_left_offset(layer)
        x = cx - f * scale
    else:
        x = cx - ox
    y = by - oy
    a = img.getchannel("A")
    if opacity < 1.0:
        a = a.point(lambda v, o=opacity: int(v * o + 0.5))
    frame.paste(img.convert("RGB"), (int(round(x)), int(round(y))), a)


def font_left_offset(layer):
    img, ox, oy = layer
    # A camada tem 'pad' à esquerda; o texto começa em pad = ox - largura/2.
    a = img.getchannel("A")
    bb = a.getbbox()
    return bb[0] if bb else 0


# --------------------------------------------------------------- cenas: produto
def frontal(name, p, label_t, label_out=1.0):
    """Plano frontal com o relógio inteiro e a etiqueta do modelo."""
    ph = PHOTOS[name]
    z = lerp(392, 414, e_sine(p))
    py = lerp(1048, 1036, e_sine(p))
    fr = ph.view(W, H, z, 0, 0, 560, py)
    # Etiqueta à esquerda da pulseira, em área limpa de fundo.
    a1 = e_out_cubic(seg(label_t, 0.05, 0.32)) * label_out
    a2 = e_out_cubic(seg(label_t, 0.12, 0.42)) * label_out
    put(fr, text_layer("GÊNESE", "sans_m", 23, MUTED, 7.5), 72, 372 + 10 * (1 - a1), a1, align="left")
    put(fr, text_layer(NAMES[name], "serif_it", 112, INK), 66, 468 + 16 * (1 - a2), a2, align="left")
    idx = ORDER.index(name) + 1
    put(fr, text_layer(f"0{idx}", "sans_xl", 58, (150, 150, 154)), 948, 468 + 16 * (1 - a2), a2 * 0.9)
    put(fr, text_layer("/04", "sans_l", 20, (160, 160, 164), 2.0), 1010, 468 + 16 * (1 - a2), a2 * 0.9)
    return fr


MACROS = {
    # foco em coordenadas relativas ao centro (múltiplos do raio da caixa)
    "silver": dict(focus=(0.0, -0.30), z=(700, 738), p0=(540, 930), p1=(540, 905)),
    "gold": dict(focus=(1.05, 0.0), z=(610, 640), p0=(892, 985), p1=(852, 975)),
    "rose": dict(focus=(0.0, -0.78), z=(640, 676), p0=(540, 1010), p1=(540, 985)),
    "black": dict(focus=(0.0, 0.62), z=(610, 642), p0=(540, 860), p1=(540, 815)),
}


def macro(name, p):
    ph = PHOTOS[name]
    m = MACROS[name]
    e = e_sine(p)
    z = lerp(m["z"][0], m["z"][1], e)
    px = lerp(m["p0"][0], m["p1"][0], e)
    py = lerp(m["p0"][1], m["p1"][1], e)
    return ph.view(W, H, z, 0, 0, px, py, focus=to_src(ph, m["focus"]))


def hook(t):
    """0–2 s: macro do Black; um painel preto desce e traz a frase de abertura."""
    ph = PHOTOS["black"]
    p = seg(t, 0, 2.0)
    e = e_sine(p)
    z = lerp(505, 560, e)
    fr = ph.view(W, H, z, 0, 0, 540, lerp(1205, 1190, e))
    ph_h = 560 * e_out_expo(seg(t, 0.0, 0.5))
    if ph_h > 0.5:
        d = ImageDraw.Draw(fr)
        d.rectangle((0, 0, W, int(round(ph_h)) - 1), fill=BAND)
        lw = 70 * e_out_cubic(seg(t, 0.35, 0.8))
        if lw > 0.5:
            d.rectangle((540 - lw, int(ph_h) - 2, 540 + lw, int(ph_h) - 1), fill=GOLD)
    a1 = e_out_cubic(seg(t, 0.16, 0.62))
    a2 = e_out_cubic(seg(t, 0.28, 0.74))
    put(fr, text_layer("A elegância", "serif_it", 94, WHITE), 540, 386 + 20 * (1 - a1), a1)
    put(fr, text_layer("está nos detalhes.", "serif_it", 94, WHITE), 540, 482 + 20 * (1 - a2), a2)
    return fr


# Sequência de 2 a 7 s: (modelo, tipo, início, fim)
SHOTS = [
    ("silver", "F", 2.00, 2.75),
    ("silver", "M", 2.75, 3.25),
    ("gold", "M", 3.25, 3.75),
    ("gold", "F", 3.75, 4.50),
    ("rose", "F", 4.50, 5.25),
    ("rose", "M", 5.25, 5.75),
    ("black", "M", 5.75, 6.25),
    ("black", "F", 6.25, 7.00),
]
SLIDES = {3.25: (1, 2), 4.50: (3, 4), 5.75: (5, 6)}  # corte -> (shot de saída, shot de entrada)
SLIDE_HALF = 0.20


def render_shot(i, t):
    name, kind, a, b = SHOTS[i]
    p = (t - a) / (b - a)
    if kind == "F":
        lt = t - a - (SLIDE_HALF if a in SLIDES else 0.0)
        out = 1.0 - e_sine(seg(t, 6.84, 6.98)) if i == len(SHOTS) - 1 else 1.0
        return frontal(name, p, lt, out)
    return macro(name, p)


def lineup(t):
    """2–7 s: os quatro modelos, alternando frontal e macro."""
    for tc, (iout, iin) in SLIDES.items():
        if tc - SLIDE_HALF <= t < tc + SLIDE_HALF:
            p = e_quart((t - (tc - SLIDE_HALF)) / (2 * SLIDE_HALF))
            A = render_shot(iout, t)
            B = render_shot(iin, t)
            dx = p * W
            fr = Image.new("RGB", (W, H), BAND)
            fr.paste(A, (int(round(-dx)), 0))
            fr.paste(B, (int(round(W - dx)), 0))
            return fr
    for i, (_, _, a, b) in enumerate(SHOTS):
        if a <= t < b:
            return render_shot(i, t)
    return render_shot(len(SHOTS) - 1, t)


# ------------------------------------------------------- cenas: composição/grid
COLS = [(0, 537), (543, 1080)]
CELL_H = 957
GRID = {"silver": (0, 0), "gold": (1, 0), "rose": (0, 1), "black": (1, 1)}


def band_height(t):
    h = 0.0
    h = lerp(h, 300, e_cubic(seg(t, 7.66, 8.05)))
    h = lerp(h, 760, e_quart(seg(t, 9.86, 10.26)))
    h = lerp(h, 800, e_cubic(seg(t, 11.88, 12.30)))
    return h


def cell_rect(name, hb):
    c, r = GRID[name]
    x0, x1 = COLS[c]
    if r == 0:
        y1 = 960 - hb / 2 - 3
        y0 = y1 - CELL_H
    else:
        y0 = 960 + hb / 2 + 3
        y1 = y0 + CELL_H
    return [x0, y0, x1, y1]


def draw_cell(fr, name, rect, z_scale=1.0, z_override=None, anchor_override=None, offset=(0.0, 0.0)):
    """Desenha uma célula. Zoom e enquadramento vêm da posição de repouso da
    célula (rect); `offset` desloca célula + conteúdo juntos (entrada lateral)."""
    ph = PHOTOS[name]
    x0, y0, x1, y1 = rect
    # Janela visível na posição de repouso -> define zoom e centro do relógio.
    ry0, ry1 = max(y0, 0), min(y1, H)
    vis_h = max(ry1 - ry0, 1.0)
    z = z_override if z_override is not None else min(226.0, 0.37 * vis_h) * z_scale
    if anchor_override is not None:
        ax, ay = anchor_override
    else:
        ax = (x0 + x1) / 2 - 8
        ay = (ry0 + ry1) / 2
    dx, dy = offset
    ix0, iy0 = int(round(x0 + dx)), int(round(y0 + dy))
    ix1, iy1 = int(round(x1 + dx)), int(round(y1 + dy))
    vy0, vy1 = max(iy0, 0), min(iy1, H)
    vx0, vx1 = max(ix0, 0), min(ix1, W)
    if vy1 - vy0 < 2 or vx1 - vx0 < 2:
        return
    tile = ph.view(vx1 - vx0, vy1 - vy0, z, 0, 0, ax + dx - vx0, ay + dy - vy0)
    fr.paste(tile, (vx0, vy0))


def grid_scene(t):
    fr = Image.new("RGB", (W, H), BAND)
    hb = band_height(t)
    push = 1.0 + 0.05 * seg(t, 7.5, 15.0)

    # Montagem (7,0–7,7 s): o Black encolhe para a célula; os outros entram.
    assemble = t < 7.75
    entries = {"silver": (7.08, 7.46, (0, -1)), "gold": (7.18, 7.56, (1, 0)), "rose": (7.28, 7.66, (-1, 0))}
    for name in ["silver", "gold", "rose"]:
        rect = cell_rect(name, hb)
        off = (0.0, 0.0)
        if assemble:
            a, b, (dx, dy) = entries[name]
            q = 1 - e_out_cubic(seg(t, a, b))
            if q >= 0.999:
                continue
            off = (dx * 560 * q, dy * 980 * q)
        draw_cell(fr, name, rect, push, offset=off)

    rect = cell_rect("black", hb)
    if t < 7.48:
        q = e_quart(seg(t, 7.0, 7.48))
        full = [0, 0, W, H]
        r = [lerp(full[i], rect[i], q) for i in range(4)]
        z0 = 414.0
        z1 = min(226.0, 0.37 * CELL_H) * push
        z = z0 * (z1 / z0) ** q  # zoom em escala logarítmica (natural)
        a0 = (560.0, 1036.0)
        a1 = ((rect[0] + rect[2]) / 2 - 8, (rect[1] + rect[3]) / 2)
        anc = (lerp(a0[0], a1[0], q), lerp(a0[1], a1[1], q))
        draw_cell(fr, "black", r, z_override=z, anchor_override=anc)
    else:
        draw_cell(fr, "black", rect, push)

    # Nomes discretos nas células (fase do preço)
    na = e_out_cubic(seg(t, 8.05, 8.4)) * (1 - seg(t, 9.75, 9.9))
    if na > 0:
        for name in ORDER:
            c, r = GRID[name]
            x0 = COLS[c][0] + 34
            rr = cell_rect(name, hb)
            by = rr[3] - 34 if r == 0 else rr[1] + 58
            put(fr, text_layer(NAMES[name].upper(), "sans_m", 21, (90, 90, 94), 6.0), x0, by, na, align="left")

    # ---- Preço (8,0–10,0 s)
    pa = e_out_cubic(seg(t, 7.98, 8.36)) * (1 - e_sine(seg(t, 9.78, 9.94)))
    if pa > 0:
        put(fr, gold(text_layer("COLEÇÃO GÊNESE", "sans_m", 24, GOLD, 9.0)), 540, 892, pa)
        rise = 18 * (1 - pa)
        # "R$" menor + valor grande, alinhados pela linha de base
        rs = text_layer("R$", "sans_l", 58, WHITE)
        val = text_layer("180,00", "sans_xl", 150, WHITE)
        wr = rs[0].getchannel("A").getbbox()
        wv = val[0].getchannel("A").getbbox()
        w_rs = wr[2] - wr[0]
        w_val = wv[2] - wv[0]
        gap = 22
        total = w_rs + gap + w_val
        left = 540 - total / 2
        base = 1046 + rise
        put(fr, rs, left, base, pa, align="left")
        put(fr, val, left + w_rs + gap, base, pa, align="left")

    # ---- Oferta (10,0–12,0 s)
    oa_in = seg(t, 10.04, 10.42)
    oa = e_out_cubic(oa_in) * (1 - e_sine(seg(t, 11.80, 11.96)))
    if oa > 0:
        sc = lerp(1.06, 1.0, e_out_cubic(oa_in))
        put(fr, gold(text_layer("CONDIÇÃO ESPECIAL", "sans_m", 24, GOLD, 9.0)), 540, 807, oa)
        big = text_layer("10% OFF", "sans_l", 176, WHITE)
        put(fr, big, 540, 1003, oa, scale=sc)
        a2 = e_out_cubic(seg(t, 10.18, 10.56)) * (1 - e_sine(seg(t, 11.80, 11.96)))
        line = text_layer("na compra de 2 ou mais relógios", "sans_r", 44, WHITE)
        put(fr, line, 540, 1115 + 14 * (1 - a2), a2)
        # fio dourado
        if a2 > 0:
            d = ImageDraw.Draw(fr)
            wline = 90 * a2
            d.rectangle((540 - wline, 1043, 540 + wline, 1045), fill=GOLD)

    # ---- Assinatura (12,0–15,0 s)
    if t >= 11.95:
        endcard(fr, t)
    return fr


def endcard(fr, t):
    # Logotipo dourado (forma extraída da embalagem real)
    la = e_out_cubic(seg(t, 12.05, 12.6))
    if la > 0:
        sc = lerp(1.05, 1.0, e_out_cubic(seg(t, 12.05, 12.9)))
        lw = int(470 * sc)
        lh = int(LOGO_MASK.height * lw / LOGO_MASK.width)
        m = LOGO_MASK.resize((lw, lh), Image.LANCZOS)
        logo = Image.new("RGBA", (lw, lh), GOLD + (0,))
        logo.putalpha(m)
        logo = gradient_fill(logo, GOLD_HI, GOLD_LO, mid=GOLD)
        # brilho que atravessa o logotipo uma vez
        sweep = seg(t, 13.05, 13.75)
        if 0 < sweep < 1:
            arr = np.asarray(logo).astype(np.float32)
            xx = np.arange(lw)[None, :] + 0.5 * np.arange(lh)[:, None]
            cxs = lerp(-0.3 * lw, 1.6 * lw, sweep)
            g = np.exp(-((xx - cxs) / (0.09 * lw)) ** 2)[..., None] * 0.55
            arr[..., :3] = arr[..., :3] + (255 - arr[..., :3]) * g
            logo = Image.fromarray(arr.astype(np.uint8))
        a = logo.getchannel("A").point(lambda v, o=la: int(v * o + 0.5))
        cy = 756
        fr.paste(logo.convert("RGB"), (540 - lw // 2, int(cy - lh / 2)), a)

    ta = e_out_cubic(seg(t, 12.45, 12.95))
    put(fr, text_layer("A simplicidade é a base da elegância.", "serif_it", 56, WHITE), 540, 952 + 16 * (1 - ta), ta)

    ca = e_out_cubic(seg(t, 12.80, 13.25))
    put(fr, text_layer("Escolha o seu.", "sans_r", 36, (225, 225, 228), 1.0), 540, 1058 + 14 * (1 - ca), ca)

    ba = e_out_cubic(seg(t, 12.95, 13.40))
    if ba > 0:
        button(fr, 540, 1172 + 18 * (1 - ba), ba, t)


@lru_cache(maxsize=4)
def button_base(w=580, h=104):
    S = 3
    m = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=h * S // 2, fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    body = gradient_fill(Image.merge("RGBA", (m, m, m, m)), GOLD_HI, GOLD_LO, mid=GOLD)
    lab = text_layer("COMPRE AGORA", "sans_sb", 33, (16, 16, 16), 5.0)
    put_img = body.convert("RGB")
    li, lox, loy = lab
    a = li.getchannel("A")
    bb = a.getbbox()
    cap_mid = (bb[1] + bb[3]) / 2
    put_img.paste(li.convert("RGB"), (int(round(w / 2 - lox)), int(round(h / 2 - cap_mid))), a)
    return put_img, m


def button(fr, cx, cy, alpha, t):
    img, m = button_base()
    w, h = img.size
    sweep = seg(t, 13.75, 14.45)
    if 0 < sweep < 1:
        arr = np.asarray(img).astype(np.float32)
        xx = np.arange(w)[None, :] + 0.6 * np.arange(h)[:, None]
        c = lerp(-0.25 * w, 1.3 * w, sweep)
        g = np.exp(-((xx - c) / (0.07 * w)) ** 2)[..., None] * 0.45
        arr = arr + (255 - arr) * g
        img = Image.fromarray(arr.astype(np.uint8))
    a = m.point(lambda v, o=alpha: int(v * o + 0.5))
    fr.paste(img, (int(round(cx - w / 2)), int(round(cy - h / 2))), a)


# ------------------------------------------------------------- linha do tempo
def render_raw(t):
    if t < 2.0:
        return hook(t)
    if t < 7.0:
        return lineup(t)
    return grid_scene(t)


def blur_samples(t):
    """(sub-amostras, abertura do obturador em fração de quadro); (0, 0) = sem desfoque."""
    for tc in SLIDES:
        if tc - SLIDE_HALF - 0.02 <= t <= tc + SLIDE_HALF + 0.02:
            return 16, 0.25  # 90°: desliza com nitidez, sem rastro pesado
    if 7.0 <= t <= 7.72:
        return 16, 0.4
    if 7.64 <= t <= 8.08 or 9.84 <= t <= 10.28 or 11.86 <= t <= 12.32:
        return 8, 0.5
    return 0, 0.0


def render_frame(i):
    init_assets()
    t = i / FPS
    K, shutter = blur_samples(t)
    if K:
        acc = None
        for k in range(K):
            ts = t + (k / (K - 1) - 0.5) * (shutter / FPS)
            ts = max(0.0, min(DUR - 1e-4, ts))
            a = np.asarray(render_raw(ts), dtype=np.float32)
            acc = a if acc is None else acc + a
        img = (acc / K + 0.5).astype(np.uint8)
    else:
        img = np.asarray(render_raw(t), dtype=np.uint8)
    return img.tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", nargs="*", type=float, help="tempos (s) para exportar PNG")
    ap.add_argument("--out", default=str(OUTPUT / "valmont-genese-reels-1080x1920.mp4"))
    ap.add_argument("--audio", default=str(BUILD / "trilha.wav"))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    if args.still is not None:
        init_assets()
        BUILD.mkdir(exist_ok=True)
        for ts in args.still:
            i = int(round(ts * FPS))
            arr = np.frombuffer(render_frame(i), np.uint8).reshape(H, W, 3)
            p = BUILD / f"still_{ts:05.2f}.png"
            Image.fromarray(arr).save(p)
            print(p)
        return

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", args.audio,
        "-map", "0:v", "-map", "1:a",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-profile:v", "high", "-level", "4.2",
        "-x264-params", "keyint=30:min-keyint=1",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-af", "volume=-1dB,afade=t=out:st=14.6:d=0.4",
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
        "-t", f"{DUR}", "-movflags", "+faststart",
        args.out,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(args.workers, initializer=init_assets) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=4)):
            proc.stdin.write(buf)
            if k % 30 == 0:
                print(f"  quadro {k}/{NFRAMES}", file=sys.stderr, flush=True)
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise SystemExit(f"ffmpeg falhou ({rc})")
    print("vídeo:", args.out)


if __name__ == "__main__":
    main()
