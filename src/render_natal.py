"""Vídeo de Natal VALMONT — "Presenteie com elegância" (1080x1920, 30 fps, 15 s).

Mesma regra do vídeo principal: os relógios são SEMPRE os pixels das fotos
originais. Aqui o fundo de estúdio cinza é trocado por um cenário quente de
Natal usando uma máscara do produto: dentro do relógio nada muda; só o fundo
(e as sombras suaves sobre ele) recebe a nova cor e as luzes desfocadas.

Uso:
  python3 src/render_natal.py                 # vídeo completo
  python3 src/render_natal.py --still 0.5 9   # quadros PNG de conferência
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render as base  # noqa: E402
from render import (  # noqa: E402
    DUR, FPS, GOLD, GOLD_HI, GOLD_LO, H, NAMES, ORDER, PHOTOS, ROOT, W,
    clamp, e_cubic, e_out_cubic, e_quart, e_sine, gold, gradient_fill, lerp,
    put, seg, smoothstep_arr, text_layer,
)

base.FONT_FILES["script"] = "PinyonScript-Regular.ttf"

NFRAMES = int(round(FPS * DUR))
BUILD = ROOT / "build"
OUTPUT = ROOT / "output"

IVORY = (247, 239, 227)
INK_B = (78, 16, 30)        # bordô escuro para texto sobre claro/dourado
WARM_MUTED = (150, 126, 108)
DESCR = {"silver": "CLÁSSICO", "gold": "SOFISTICADO", "rose": "DELICADO", "black": "MARCANTE"}

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)

SIL: dict[str, Image.Image] = {}
BOX_PHOTO: Image.Image | None = None
MOUNTAIN: Image.Image | None = None


# ------------------------------------------------------------ máscaras/ativos
def make_sil(name):
    """Silhueta do relógio (1 = produto intocável, 0 = fundo de estúdio)."""
    ph = PHOTOS[name]
    a = np.asarray(Image.open(base.FOTOS / f"genese-{name}.jpg").convert("RGB")).astype(np.float32)
    bg = np.array(ph.bg, np.float32)
    b = 4
    a[:b] = bg
    a[-b:] = bg
    a[:, :b] = bg
    a[:, -b:] = bg
    diff = np.abs(a - bg).max(axis=2)
    h, w = a.shape[:2]

    def filled(th):
        m = Image.fromarray(((diff > th) * 255).astype(np.uint8))
        m = m.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
        ImageDraw.floodfill(m, (0, 0), 128)  # tudo que o fundo alcança por fora
        return np.asarray(m) != 128  # furos fechados (mostrador) contam como produto

    # Núcleo do produto (metal, pulseira): limiar alto -> as sombras suaves
    # sobre o fundo ficam de fora e recebem o tom do cenário.
    core = filled(28)
    # Dentro da caixa, limiar baixo garante o mostrador branco inteiro.
    yy, xx = np.mgrid[0:h, 0:w]
    disk = ((xx - ph.C[0]) ** 2 + (yy - ph.C[1]) ** 2) <= (ph.R * 1.08) ** 2
    sil = (core | (filled(10) & disk)).astype(np.uint8) * 255
    sil = Image.fromarray(sil).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    canvas = Image.new("L", (w + 2 * base.PAD, h + 2 * base.PAD), 0)
    canvas.paste(sil, (base.PAD, base.PAD))
    return canvas


def init_assets():
    global BOX_PHOTO, MOUNTAIN
    base.init_assets()
    if SIL:
        return
    for k in ORDER:
        SIL[k] = make_sil(k)
    BOX_PHOTO = Image.open(base.FOTOS / "embalagem-colecao.jpg").convert("RGB").crop((0, 388, 960, 1008))
    # Ícone da montanha (parte de cima do logotipo) para a estampa do papel.
    lm = np.asarray(base.LOGO_MASK).astype(np.float32)
    rows = lm.sum(axis=1)
    h = len(rows)
    lo, hi = int(h * 0.40), int(h * 0.70)
    split = lo + int(np.argmin(rows[lo:hi]))
    MOUNTAIN = base.LOGO_MASK.crop((0, 0, base.LOGO_MASK.width, split))
    MOUNTAIN = MOUNTAIN.crop(MOUNTAIN.getbbox())


# --------------------------------------------------------------- cenários
@lru_cache(maxsize=1)
def warm_base():
    d = np.sqrt(((XX - 540) / 760) ** 2 + ((YY - 1000) / 1180) ** 2)
    k = smoothstep_arr((d - 0.32) / 0.95)[..., None]
    c0 = np.array((244, 238, 229), np.float32)
    c1 = np.array((198, 164, 122), np.float32)
    return c0 + (c1 - c0) * k


def make_bokeh(seed, n, rmin, rmax, amin, amax, colors, avoid_center=False):
    r = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        x, y = r.uniform(-80, W + 80), r.uniform(-80, H + 80)
        if avoid_center and abs(x - 540) < 330 and 420 < y < 1560 and r.uniform() < 0.8:
            continue
        out.append(dict(
            x=x, y=y, r=r.uniform(rmin, rmax), a=r.uniform(amin, amax),
            c=np.array(colors[r.integers(len(colors))], np.float32),
            vx=r.uniform(-14, 14), vy=r.uniform(-26, -6),
            ph=r.uniform(0, 6.28), fq=r.uniform(0.25, 0.6),
        ))
    return out


LIGHT_BOKEH = make_bokeh(11, 26, 34, 120, 0.30, 0.62,
                         [(1.0, 0.80, 0.50), (1.0, 0.86, 0.60), (1.0, 0.74, 0.44)], avoid_center=True)
DARK_BOKEH = make_bokeh(5, 30, 26, 115, 0.16, 0.42,
                        [(1.0, 0.76, 0.40), (1.0, 0.84, 0.55), (1.0, 0.55, 0.36)])


def apply_bokeh(arr, items, t, gain=1.0, center_quiet=0.0):
    L = np.zeros((H, W, 3), np.float32)
    for b in items:
        x = b["x"] + b["vx"] * t + 6 * math.sin(0.7 * t + b["ph"])
        y = b["y"] + b["vy"] * t
        r = b["r"]
        a = b["a"] * gain * (0.86 + 0.14 * math.sin(2 * math.pi * b["fq"] * t + b["ph"]))
        if center_quiet > 0:
            a *= 1 - center_quiet * math.exp(-((y - 960) / 430) ** 2)
        x0, x1 = int(max(0, x - r - 2)), int(min(W, x + r + 3))
        y0, y1 = int(max(0, y - r - 2)), int(min(H, y + r + 3))
        if x1 <= x0 or y1 <= y0:
            continue
        yy, xx = np.ogrid[y0:y1, x0:x1]
        d = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
        prof = smoothstep_arr((r - d) / (0.24 * r)) * (0.80 + 0.20 * smoothstep_arr((d - 0.55 * r) / (0.45 * r)))
        L[y0:y1, x0:x1] += prof[..., None] * b["c"] * a
    L = np.clip(L, 0, 1)
    return 255 - (255 - arr) * (1 - L)


def warm_bg(t):
    return apply_bokeh(warm_base(), LIGHT_BOKEH, t)


@lru_cache(maxsize=4)
def wrap_tex(pattern_alpha, height=H, cy=None):
    """Papel de presente bordô com estampa discreta da montanha VALMONT."""
    cy = height / 2 if cy is None else cy
    yy, xx = np.mgrid[0:height, 0:W].astype(np.float32)
    d = np.sqrt(((xx - 540) / 820) ** 2 + ((yy - cy) / 1250) ** 2)
    k = smoothstep_arr((d - 0.18) / 1.0)[..., None]
    c0 = np.array((116, 24, 44), np.float32)
    c1 = np.array((44, 7, 17), np.float32)
    tex = c0 + (c1 - c0) * k
    grain = np.random.default_rng(3).normal(0, 2.0, (height, W, 1)).astype(np.float32)
    tex = tex + grain
    if pattern_alpha > 0:
        iw = 60
        ih = int(MOUNTAIN.height * iw / MOUNTAIN.width)
        icon = MOUNTAIN.resize((iw, ih), Image.LANCZOS)
        pat = Image.new("L", (W, height), 0)
        sx, sy = 172, 150
        for j, y in enumerate(range(-ih, height + sy, sy)):
            off = (sx // 2) if j % 2 else 0
            for x in range(-iw + off, W + sx, sx):
                pat.paste(icon, (x, y), icon)
        pa = np.asarray(pat).astype(np.float32)[..., None] / 255.0 * pattern_alpha
        goldc = np.array((214, 176, 104), np.float32)
        tex = tex * (1 - pa) + goldc * pa
    return np.clip(tex, 0, 255)


def burg_bg(t, pattern=0.10, quiet=0.0):
    return apply_bokeh(wrap_tex(round(pattern, 3)).copy(), DARK_BOKEH, t, gain=1.0, center_quiet=quiet)


# -------------------------------------------------------------- produto
def product(bg_arr, name, w, h, z, px, py, focus=None):
    """Recorte w x h do relógio sobre o cenário bg_arr (mesmo tamanho).
    Dentro da silhueta: pixels originais. Fora: fundo trocado pelo cenário."""
    ph = PHOTOS[name]
    tile = ph.view(w, h, z, 0, 0, px, py, focus)
    s = z / ph.R
    Fx, Fy = focus if focus is not None else ph.C
    x0 = Fx - px / s
    y0 = Fy - py / s
    box = (x0 + base.PAD, y0 + base.PAD, x0 + w / s + base.PAD, y0 + h / s + base.PAD)
    m = SIL[name].resize((int(w), int(h)), Image.BILINEAR, box=box)
    t = np.asarray(tile, np.float32)
    mm = np.asarray(m, np.float32)[..., None] / 255.0
    B = np.array(ph.bg, np.float32)
    return mm * t + (1 - mm) * (t * bg_arr / B)


@lru_cache(maxsize=2)
def card_bg(w, h):
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    c0 = np.array((246, 240, 231), np.float32)
    c1 = np.array((234, 222, 204), np.float32)
    return np.broadcast_to(c0 + (c1 - c0) * y, (h, w, 3)).copy()


# --------------------------------------------------------------- fitas
RAMP_X = [0.0, 0.33, 0.58, 0.82, 1.0]
RAMP_C = np.array([(88, 56, 20), (166, 124, 54), (212, 174, 98), (241, 215, 150), (255, 247, 222)], np.float32)


def satin_color(v, s, phase=0.0):
    av = np.abs(v)
    L = 0.40 + 0.22 * np.cos(np.clip(v, -1, 1) * np.pi / 2)
    L = L + 0.36 * np.exp(-((v + 0.32) / 0.16) ** 2) + 0.12 * np.exp(-((v - 0.44) / 0.10) ** 2)
    L = L - 0.22 * smoothstep_arr((av - 0.78) / 0.22) - 0.12 * np.exp(-((av - 0.9) / 0.025) ** 2)
    L = L * (1 + 0.06 * np.sin(s / 260.0 + phase))
    L = np.clip(L, 0, 1)
    return np.stack([np.interp(L, RAMP_X, RAMP_C[:, c]) for c in range(3)], axis=-1)


def draw_ribbon(arr, nx, ny, c, width, phase=0.0, s_range=None, shadow=(0.0, 12.0), alpha=1.0):
    """Fita de cetim dourada: faixa |u - c| < width/2, u = x*nx + y*ny."""
    if alpha <= 0:
        return arr
    u = XX * nx + YY * ny
    s = XX * ny + YY * nx  # coordenada ao longo da fita (x na horizontal, y na vertical)
    hw = width / 2
    along = 1.0
    if s_range is not None:
        a0, a1 = s_range
        along = np.clip(np.minimum(s - a0, a1 - s) + 0.5, 0, 1)
    # sombra projetada
    du = shadow[0] * nx + shadow[1] * ny
    dsh = np.abs(u - c - du) - hw
    sh = 0.34 * (1 - smoothstep_arr(dsh / 26.0)) * along * alpha
    arr = arr * (1 - sh[..., None])
    cov = np.clip(hw - np.abs(u - c) + 0.5, 0, 1) * along * alpha
    v = (u - c) / hw
    col = satin_color(v, s, phase)
    return arr * (1 - cov[..., None]) + col * cov[..., None]


def wipe(A, B, p, width=120):
    """Transição: a cena nova empurra a antiga para a esquerda e uma fita de
    cetim dourada passa na emenda. Os dois relógios nunca se sobrepõem."""
    dx = int(round(p * W))
    out = np.empty_like(A)
    out[:, : W - dx] = A[:, dx:]
    out[:, W - dx:] = B[:, :dx]
    return draw_ribbon(out, 1.0, 0.0, W - p * W, width, phase=p * 3, shadow=(-10, 0))


# ------------------------------------------------------------- tipografia
def to_img(arr):
    return Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8))


def to_arr(img):
    return np.asarray(img, np.float32)


@lru_cache(maxsize=1)
def wrap_tall():
    return wrap_tex(0.12, H + 760, cy=640 + 760)


# ----------------------------------------------------------------- cenas
def hook(t):
    """0–2 s: o papel de presente se abre e revela o Gold."""
    e = e_sine(seg(t, 0, 2.0))
    arr = product(warm_bg(t), "gold", W, H, lerp(548, 600, e), 540, lerp(1252, 1236, e))
    yb = lerp(1330, 640, e_out_cubic(seg(t, 0.08, 0.80)))
    iy = int(round(yb))
    # sombra da tampa sobre a cena
    ys = np.arange(H, dtype=np.float32)[:, None, None]
    shade = np.where(ys >= yb, 0.30 * np.exp(-(ys - yb) / 30.0), 0.0)
    arr = arr * (1 - shade)
    tex = wrap_tall()
    off = 640 + 760 - iy
    arr[:iy] = tex[off:off + iy]
    arr = draw_ribbon(arr, 0.0, 1.0, yb - 31, 62, phase=1.3, shadow=(0, 10))
    img = to_img(arr)
    a0 = e_out_cubic(seg(t, 0.42, 0.85))
    a1 = e_out_cubic(seg(t, 0.52, 0.98))
    a2 = e_out_cubic(seg(t, 0.64, 1.10))
    put(img, gold(text_layer("NESTE NATAL", "sans_m", 26, GOLD, 10.0)), 540, yb - 330 + 10 * (1 - a0), a0)
    put(img, text_layer("Presenteie", "serif_it", 104, IVORY), 540, yb - 220 + 16 * (1 - a1), a1)
    put(img, text_layer("com elegância.", "serif_it", 104, IVORY), 540, yb - 118 + 16 * (1 - a2), a2)
    return to_arr(img)


MODEL_SHOTS = [("silver", 2.0, 3.0), ("gold", 3.0, 4.0), ("rose", 4.0, 5.0), ("black", 5.0, 6.0)]
CAM = {
    "silver": dict(z=(388, 410), px=(560, 560), py=(1050, 1036)),
    "gold": dict(z=(392, 408), px=(548, 570), py=(1044, 1040)),
    "rose": dict(z=(412, 392), px=(560, 560), py=(1034, 1046)),
    "black": dict(z=(388, 412), px=(560, 556), py=(1050, 1034)),
}


def model_shot(name, t, t0, t1):
    c = CAM[name]
    p = e_sine((t - t0 + 0.2) / (t1 - t0 + 0.4))
    arr = product(warm_bg(t), name, W, H, lerp(*c["z"], p), lerp(*c["px"], p), lerp(*c["py"], p))
    img = to_img(arr)
    lt = t - t0 - 0.08
    a1 = e_out_cubic(seg(lt, 0.0, 0.28))
    a2 = e_out_cubic(seg(lt, 0.07, 0.36))
    put(img, text_layer(DESCR[name], "sans_sb", 22, (138, 98, 44), 7.5), 72, 372 + 10 * (1 - a1), a1, align="left")
    put(img, text_layer(NAMES[name], "serif_it", 112, INK_B), 66, 468 + 16 * (1 - a2), a2, align="left")
    idx = ORDER.index(name) + 1
    put(img, text_layer(f"0{idx}", "sans_xl", 58, WARM_MUTED), 948, 468 + 16 * (1 - a2), a2 * 0.9)
    put(img, text_layer("/04", "sans_l", 20, WARM_MUTED, 2.0), 1010, 468 + 16 * (1 - a2), a2 * 0.9)
    return to_arr(img)


@lru_cache(maxsize=4)
def rounded_mask(w, h, r):
    S = 3
    m = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=r * S, fill=255)
    return m.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=4)
def card_shadow(w, h, r, blur=26):
    pad = blur * 3
    m = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(m).rounded_rectangle((pad, pad, pad + w, pad + h), radius=r, fill=255)
    return m.filter(ImageFilter.GaussianBlur(blur)), pad


def paste_card(img, content, x, y, r=22, alpha=1.0, border=True):
    """Cola um 'cartão' (foto) com cantos arredondados, sombra e filete dourado."""
    w, h = content.size
    ix, iy = int(round(x)), int(round(y))
    sh, pad = card_shadow(w, h, r)
    sha = sh.point(lambda v, o=alpha: int(v * 0.55 * o))
    img.paste((8, 2, 5), (ix - pad, iy - pad + 16), sha)
    m = rounded_mask(w, h, r)
    if alpha < 1:
        m = m.point(lambda v, o=alpha: int(v * o))
    img.paste(content, (ix, iy), m)
    if border:
        d = ImageDraw.Draw(img, "RGBA")
        d.rounded_rectangle((ix, iy, ix + w - 1, iy + h - 1), radius=r, outline=GOLD + (int(170 * alpha),), width=2)


def box_scene(t, img=None, alpha=1.0):
    """6–8 s: a caixa VALMONT real (foto original da embalagem)."""
    if img is None:
        k = seg(t, 7.8, 8.3)
        bg = burg_bg(t, pattern=0.10 * (1 - k))
        img = to_img(bg)
    cw = 984
    ch = int(BOX_PHOTO.height * cw / BOX_PHOTO.width)
    zoom = lerp(1.0, 1.06, e_sine(seg(t, 5.8, 8.2)))
    bw, bh = BOX_PHOTO.width / zoom, BOX_PHOTO.height / zoom
    bx0 = (BOX_PHOTO.width - bw) / 2
    by0 = (BOX_PHOTO.height - bh) / 2
    content = BOX_PHOTO.resize((cw, ch), Image.LANCZOS, box=(bx0, by0, bx0 + bw, by0 + bh))
    out = 1 - e_cubic(seg(t, 7.78, 8.12))
    sc = lerp(1.0, 0.94, 1 - out)
    if sc != 1.0:
        content = content.resize((int(cw * sc), int(ch * sc)), Image.LANCZOS)
    cy = 1030
    paste_card(img, content, 540 - content.width / 2, cy - content.height / 2, alpha=out * alpha)
    ta = e_out_cubic(seg(t, 6.12, 6.5)) * (1 - e_sine(seg(t, 7.7, 7.92)))
    tb = e_out_cubic(seg(t, 6.22, 6.62)) * (1 - e_sine(seg(t, 7.7, 7.92)))
    tc = e_out_cubic(seg(t, 6.34, 6.74)) * (1 - e_sine(seg(t, 7.7, 7.92)))
    put(img, gold(text_layer("O PRESENTE PERFEITO", "sans_m", 24, GOLD, 9.0)), 540, 380 + 10 * (1 - ta), ta)
    put(img, text_layer("Na caixa VALMONT,", "serif_it", 88, IVORY), 540, 486 + 14 * (1 - tb), tb)
    put(img, text_layer("pronto para presentear.", "serif_it", 88, IVORY), 540, 578 + 14 * (1 - tc), tc)
    return img


# Grade "embrulhada" (8–15 s)
COLS = [(28, 526), (554, 1052)]
CARD_H = 820
GRID = {"silver": (0, 0), "gold": (1, 0), "rose": (0, 1), "black": (1, 1)}
ENTRY = {"silver": 8.00, "gold": 8.06, "rose": 8.12, "black": 8.18}


def band_h(t):
    h = 252.0
    h = lerp(h, 960.0, e_quart(seg(t, 9.95, 10.4)))
    return h


def card_rect(name, hb):
    c, r = GRID[name]
    x0, x1 = COLS[c]
    if r == 0:
        y1 = 960 - hb / 2
        y0 = y1 - CARD_H
    else:
        y0 = 960 + hb / 2
        y1 = y0 + CARD_H
    return x0, y0, x1, y1


def product_card(name, rect, push):
    x0, y0, x1, y1 = rect
    w, h = int(x1 - x0), int(y1 - y0)
    vy0, vy1 = max(y0, 0), min(y1, H)
    vis = max(vy1 - vy0, 1)
    z = min(205.0, 0.37 * vis) * push
    ax = w / 2 - 6
    ay = (vy0 + vy1) / 2 - y0
    arr = product(card_bg(w, h), name, w, h, z, ax, ay)
    return to_img(arr)


def grid_scene(t):
    k = seg(t, 7.8, 8.3)
    bg = burg_bg(t, pattern=0.10 * (1 - k), quiet=0.75 * seg(t, 9.9, 10.4))
    img = to_img(bg)
    if t < 8.15:
        box_scene(t, img)
    hb = band_h(t)
    push = 1.0 + 0.05 * seg(t, 8.0, 15.0)
    for name in ORDER:
        q = e_out_cubic(seg(t, ENTRY[name], ENTRY[name] + 0.42))
        if q <= 0:
            continue
        x0, y0, x1, y1 = card_rect(name, hb)
        dy = (1 - q) * (-980 if GRID[name][1] == 0 else 980)
        content = product_card(name, (x0, y0, x1, y1), push)
        paste_card(img, content, x0, y0 + dy, alpha=min(1.0, q * 1.6))
    arr = to_arr(img)

    # Fitas: a coleção "embrulhada" com o preço (8,4–10 s)
    vgrow = e_out_cubic(seg(t, 8.45, 8.85))
    vret = e_cubic(seg(t, 9.9, 10.2))
    if vgrow > 0 and vret < 1:
        arr = draw_ribbon(arr, 1.0, 0.0, 540, 30, phase=0.4, s_range=(H * vret, H * vgrow), shadow=(8, 0))
    hgrow = e_out_cubic(seg(t, 8.36, 8.76))
    hout = e_quart(seg(t, 9.86, 10.22))
    if hgrow > 0 and hout < 1:
        shift = W * 1.1 * hout
        arr = draw_ribbon(arr, 0.0, 1.0, 960, 222, phase=2.0, s_range=(shift - 4, W * hgrow + shift + 4), shadow=(0, 12))
    img = to_img(arr)

    pa = e_out_cubic(seg(t, 8.66, 9.0)) * (1 - e_sine(seg(t, 9.8, 9.95)))
    if pa > 0:
        dx = W * 1.1 * hout
        put(img, text_layer("COLEÇÃO GÊNESE", "sans_sb", 22, INK_B, 8.0), 540 + dx, 918, pa)
        rs = text_layer("R$", "sans_r", 50, INK_B)
        val = text_layer("180,00", "sans_l", 122, INK_B)
        wr = rs[0].getchannel("A").getbbox()
        wv = val[0].getchannel("A").getbbox()
        total = (wr[2] - wr[0]) + 18 + (wv[2] - wv[0])
        left = 540 - total / 2 + dx
        put(img, rs, left, 1022, pa, align="left")
        put(img, val, left + (wr[2] - wr[0]) + 18, 1022, pa, align="left")

    # Oferta (10–12,5 s)
    fo = 1 - e_sine(seg(t, 12.25, 12.42))
    o1 = e_out_cubic(seg(t, 10.22, 10.58)) * fo
    o2 = e_out_cubic(seg(t, 10.40, 10.76)) * fo
    o3 = seg(t, 10.62, 10.98)
    o4 = e_out_cubic(seg(t, 10.80, 11.16)) * fo
    if o1 > 0:
        put(img, text_layer("Um para presentear.", "serif_it", 74, IVORY), 540, 742 + 14 * (1 - o1), o1)
        put(img, gold(text_layer("Outro para você.", "serif_it", 74, GOLD)), 540, 826 + 14 * (1 - o2), o2)
        if o3 > 0:
            put(img, text_layer("10% OFF", "sans_l", 176, IVORY), 540, 1032, e_out_cubic(o3) * fo,
                scale=lerp(1.06, 1.0, e_out_cubic(o3)))
        if o4 > 0:
            d = ImageDraw.Draw(img)
            wl = 90 * o4
            d.rectangle((540 - wl, 1072, 540 + wl, 1074), fill=GOLD)
            put(img, text_layer("na compra de 2 ou mais relógios", "sans_r", 44, IVORY), 540, 1146 + 12 * (1 - o4), o4)

    if t >= 12.4:
        endcard(img, t)
    return to_arr(img)


@lru_cache(maxsize=1)
def logo_rgba(width=440):
    lh = int(base.LOGO_MASK.height * width / base.LOGO_MASK.width)
    m = base.LOGO_MASK.resize((width, lh), Image.LANCZOS)
    logo = Image.new("RGBA", (width, lh), GOLD + (0,))
    logo.putalpha(m)
    return gradient_fill(logo, GOLD_HI, GOLD_LO, mid=GOLD)


@lru_cache(maxsize=1)
def button_img(w=620, h=106):
    S = 3
    m = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=h * S // 2, fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    body = gradient_fill(Image.merge("RGBA", (m, m, m, m)), GOLD_HI, GOLD_LO, mid=GOLD).convert("RGB")
    li, lox, loy = text_layer("PRESENTEIE AGORA", "sans_sb", 32, INK_B, 5.0)
    a = li.getchannel("A")
    bb = a.getbbox()
    body.paste(li.convert("RGB"), (int(round(w / 2 - lox)), int(round(h / 2 - (bb[1] + bb[3]) / 2))), a)
    return body, m


def sweep(img_rgb, t, a, b, width=0.08, k=0.5):
    p = seg(t, a, b)
    if not 0 < p < 1:
        return img_rgb
    arr = np.asarray(img_rgb).astype(np.float32)
    h, w = arr.shape[:2]
    xx = np.arange(w)[None, :] + 0.55 * np.arange(h)[:, None]
    c = lerp(-0.3 * w, 1.5 * w, p)
    g = np.exp(-((xx - c) / (width * w)) ** 2)[..., None] * k
    arr[..., :3] = arr[..., :3] + (255 - arr[..., :3]) * g
    return Image.fromarray(arr.astype(np.uint8))


def endcard(img, t):
    la = e_out_cubic(seg(t, 12.5, 13.0))
    if la > 0:
        logo = sweep(logo_rgba(), t, 13.3, 13.9, 0.09, 0.55)
        sc = lerp(1.05, 1.0, e_out_cubic(seg(t, 12.5, 13.3)))
        if sc != 1.0:
            logo = logo.resize((int(logo.width * sc), int(logo.height * sc)), Image.LANCZOS)
        a = logo.getchannel("A").point(lambda v, o=la: int(v * o + 0.5))
        img.paste(logo.convert("RGB"), (540 - logo.width // 2, int(712 - logo.height / 2)), a)
    ta = e_out_cubic(seg(t, 12.85, 13.3))
    put(img, text_layer("A simplicidade é a base da elegância.", "serif_it", 54, IVORY), 540, 878 + 14 * (1 - ta), ta)
    sa = e_out_cubic(seg(t, 13.05, 13.55))
    put(img, gold(text_layer("Boas Festas", "script", 112, GOLD)), 540, 1022 + 12 * (1 - sa), sa)
    ba = e_out_cubic(seg(t, 13.25, 13.7))
    if ba > 0:
        body, m = button_img()
        body = sweep(body, t, 14.0, 14.6, 0.07, 0.45)
        a = m.point(lambda v, o=ba: int(v * o + 0.5))
        img.paste(body, (540 - body.width // 2, int(1150 + 16 * (1 - ba) - body.height / 2)), a)


# ------------------------------------------------------------ linha do tempo
WIPES = [2.0, 3.0, 4.0, 5.0, 6.0]
WIPE_HALF = 0.2


def scene_at(t):
    if t < 2.0:
        return hook(t)
    for name, a, b in MODEL_SHOTS:
        if a <= t < b:
            return model_shot(name, t, a, b)
    if t < 7.8:
        return to_arr(box_scene(t))
    return grid_scene(t)


def scene_named(key, t):
    if key == "hook":
        return hook(t)
    if key == "box":
        return to_arr(box_scene(t))
    for name, a, b in MODEL_SHOTS:
        if name == key:
            return model_shot(name, t, a, b)
    raise KeyError(key)


SEQ = ["hook", "silver", "gold", "rose", "black", "box"]


def render_raw(t):
    for i, tc in enumerate(WIPES):
        if tc - WIPE_HALF <= t < tc + WIPE_HALF:
            p = e_quart((t - (tc - WIPE_HALF)) / (2 * WIPE_HALF))
            A = scene_named(SEQ[i], t)
            B = scene_named(SEQ[i + 1], t)
            return wipe(A, B, p)
    return scene_at(t)


def blur_samples(t):
    for tc in WIPES:
        if tc - WIPE_HALF - 0.02 <= t <= tc + WIPE_HALF + 0.02:
            return 12, 0.25
    if 0.05 <= t <= 0.85:
        return 8, 0.45
    if 7.98 <= t <= 8.65 or 9.84 <= t <= 10.45:
        return 8, 0.45
    return 0, 0.0


def render_frame(i):
    init_assets()
    t = i / FPS
    K, shutter = blur_samples(t)
    if K:
        acc = None
        for k in range(K):
            ts = min(DUR - 1e-4, max(0.0, t + (k / (K - 1) - 0.5) * (shutter / FPS)))
            a = render_raw(ts)
            acc = a if acc is None else acc + a
        img = acc / K
    else:
        img = render_raw(t)
    return np.clip(img + 0.5, 0, 255).astype(np.uint8).tobytes()


def loudness_gain(wav, target=-14.0, tp_max=-1.5):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af",
                        f"loudnorm=I={target}:TP={tp_max}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1]
    d = json.loads(txt)
    gain = target - float(d["input_i"])
    gain = min(gain, tp_max - float(d["input_tp"]))
    return gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", nargs="*", type=float)
    ap.add_argument("--out", default=str(OUTPUT / "valmont-natal-presente-1080x1920.mp4"))
    ap.add_argument("--audio", default=str(BUILD / "trilha_natal.wav"))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    if args.still is not None:
        init_assets()
        BUILD.mkdir(exist_ok=True)
        for ts in args.still:
            arr = np.frombuffer(render_frame(int(round(ts * FPS))), np.uint8).reshape(H, W, 3)
            p = BUILD / f"natal_{ts:05.2f}.png"
            Image.fromarray(arr).save(p)
            print(p)
        return

    gain = loudness_gain(args.audio)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", args.audio, "-map", "0:v", "-map", "1:a",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-profile:v", "high", "-level", "4.2",
        "-x264-params", "keyint=30:min-keyint=1",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-af", f"volume={gain:.2f}dB,afade=t=out:st=14.5:d=0.5",
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
        "-t", f"{DUR}", "-movflags", "+faststart", args.out,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(args.workers, initializer=init_assets) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=3)):
            proc.stdin.write(buf)
            if k % 30 == 0:
                print(f"  quadro {k}/{NFRAMES}", file=sys.stderr, flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg falhou")
    print("vídeo:", args.out)


if __name__ == "__main__":
    main()
