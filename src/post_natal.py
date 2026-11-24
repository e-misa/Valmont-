"""Foto "flat lay" de Natal para post do Instagram (1080x1350, 4:5).

Os quatro relógios são os pixels das fotos originais de estúdio, apenas
escalados (todos no mesmo tamanho real, 36 mm) e girados no plano, como se
tivessem sido colocados sobre a mesa e fotografados de cima. O fundo de
estúdio é trocado pela superfície usando a máscara do produto. A sombra
original de cada foto é transferida para a nova superfície, e uma sombra
de contato (luz de janela vinda do alto à esquerda) assenta os objetos.

Saída: output/post-natal-flatlay-1080x1350.jpg
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render as base  # noqa: E402
import render_natal as rn  # noqa: E402

ROOT = base.ROOT
OUT = ROOT / "output/post-natal-flatlay-1080x1350.jpg"
W, H = 1080, 1350
SS = 2  # super-amostragem da superfície e da fita
rng = np.random.default_rng(2026)

LIGHT = np.array([0.62, 0.78])  # direção da sombra (para baixo e à direita)


def smooth_noise(h, w, cell, amp):
    gh, gw = max(2, h // cell + 3), max(2, w // cell + 3)
    g = rng.standard_normal((gh, gw)).astype(np.float32)
    im = Image.fromarray(g, mode="F").resize((w + 2 * cell, h + 2 * cell), Image.BICUBIC)
    a = np.asarray(im)[cell:cell + h, cell:cell + w]
    return a / (a.std() + 1e-6) * amp


def surface():
    """Reboco/pedra clara e quente, com luz de janela vinda do alto à esquerda."""
    h, w = H * SS, W * SS
    base_col = np.array((233, 225, 213), np.float32)
    lum = 1.0
    lum = lum + smooth_noise(h, w, 520, 0.010) + smooth_noise(h, w, 140, 0.006)
    lum = lum + smooth_noise(h, w, 14, 0.006) + smooth_noise(h, w, 4, 0.006)
    lum = lum + rng.normal(0, 0.010, (h, w)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xn, yn = xx / w, yy / h
    fall = 1.045 - 0.10 * (0.55 * xn + 0.45 * yn) - 0.05 * ((xn - 0.3) ** 2 + (yn - 0.25) ** 2)
    arr = base_col * (lum * fall)[..., None]
    # leve variação de cor (manchas mais quentes)
    warm = smooth_noise(h, w, 300, 1.0)[..., None]
    arr = arr + warm * np.array((2.0, 0.5, -2.0), np.float32)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    return np.asarray(img).astype(np.float32)


def bezier(p0, p1, p2, p3, n=600):
    t = np.linspace(0, 1, n)[:, None]
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def ribbon(canvas, pts, width):
    """Fita de veludo bordô deitada sobre a mesa, com sombra suave."""
    h, w = H * SS, W * SS
    P = pts * SS
    # distância assinada até a curva (via polilinha densa)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    best = np.full((h, w), 1e9, np.float32)
    side = np.full((h, w), 1e9, np.float32)
    along = np.zeros((h, w), np.float32)
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    for i in range(0, len(P) - 1, 1):
        a, b = P[i], P[i + 1]
        ab = b - a
        L2 = float(ab @ ab) + 1e-6
        x0 = int(max(0, min(a[0], b[0]) - width * SS)); x1 = int(min(w, max(a[0], b[0]) + width * SS))
        y0 = int(max(0, min(a[1], b[1]) - width * SS)); y1 = int(min(h, max(a[1], b[1]) + width * SS))
        if x1 <= x0 or y1 <= y0:
            continue
        px = xx[y0:y1, x0:x1] - a[0]
        py = yy[y0:y1, x0:x1] - a[1]
        t = np.clip((px * ab[0] + py * ab[1]) / L2, 0, 1)
        dx = px - t * ab[0]
        dy = py - t * ab[1]
        d = np.sqrt(dx * dx + dy * dy)
        sgn = np.sign(ab[0] * py - ab[1] * px)
        sub = best[y0:y1, x0:x1]
        upd = d < sub
        sub[upd] = d[upd]
        side[y0:y1, x0:x1][upd] = (d * sgn)[upd]
        along[y0:y1, x0:x1][upd] = (cum[i] + t * np.sqrt(L2))[upd]
    hw = width * SS / 2
    v = side / hw  # -1..1 através da fita
    fuzz = rng.normal(0, 1, (h, w)).astype(np.float32) * 0.8
    cov = np.clip((hw - np.abs(side) + fuzz) / 1.6 + 0.5, 0, 1)
    # sombra (deslocada para baixo/direita, borrada)
    sh = Image.fromarray((cov * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5 * SS))
    sh = np.asarray(sh.transform(sh.size, Image.AFFINE, (1, 0, -4 * SS, 0, 1, -6 * SS))).astype(np.float32) / 255
    # veludo: cor profunda, bordas que pegam luz, textura de pelo, brilho suave ao longo
    base_c = np.array((92, 13, 27), np.float32)
    pile = rng.normal(0, 1, (h, w)).astype(np.float32)
    pile = (pile + np.roll(pile, 1, 0) + np.roll(pile, 1, 1) + np.roll(pile, (1, 1), (0, 1))) / 4 * 0.05
    edge = np.exp(-((np.abs(v) - 0.93) / 0.07) ** 2) * 0.22
    sheen = 0.10 * np.sin(along / (260 * SS) + 0.8) + 0.06 * np.sin(along / (95 * SS))
    crush = smooth_noise(h, w, 22 * SS, 0.05) + smooth_noise(h, w, 7 * SS, 0.03)
    shade = 0.92 - 0.12 * v + edge + sheen + pile + crush
    col = base_c * shade[..., None]
    col = col + np.array((40, 14, 18), np.float32) * edge[..., None]
    rgb = np.clip(col, 0, 255)
    cov_s = Image.fromarray((cov * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    sh_s = Image.fromarray((sh * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    rgb_s = Image.fromarray(rgb.astype(np.uint8)).resize((W, H), Image.LANCZOS)
    c = np.asarray(cov_s).astype(np.float32)[..., None] / 255
    s = np.asarray(sh_s).astype(np.float32)[..., None] / 255
    canvas = canvas * (1 - 0.45 * s * (1 - c))
    canvas = canvas * (1 - c) + np.asarray(rgb_s).astype(np.float32) * c
    return canvas


def strap_end_rows(name):
    """Linhas (na foto) onde a pulseira de fato começa e termina: abaixo/acima
    disso só há a sombra de estúdio, que não faz parte do produto."""
    ph = base.PHOTOS[name]
    P = base.PAD
    w0, h0 = ph.im.width - 2 * P, ph.im.height - 2 * P
    a = np.asarray(ph.im.crop((P, P, P + w0, P + h0)).convert("L")).astype(np.float32)
    g = np.abs(np.diff(a, axis=1))[:-1, :] + np.abs(np.diff(a, axis=0))[:, :-1]
    cx = int(ph.C[0])
    band = g[:, cx - 90:cx + 90].mean(axis=1)
    strap_level = np.median(band[int(ph.C[1] + 1.4 * ph.R):int(ph.C[1] + 1.8 * ph.R)])
    lower = np.arange(int(ph.C[1] + 1.4 * ph.R), len(band))
    y_bot = int(lower[band[lower] > 0.35 * strap_level].max()) + 2
    upper = np.arange(0, int(ph.C[1] - 1.4 * ph.R))
    y_top = int(upper[band[upper] > 0.35 * strap_level].min()) - 2
    return y_top, y_bot


def post_mask(name):
    ph = base.PHOTOS[name]
    P = base.PAD
    y_top, y_bot = strap_end_rows(name)
    m = np.asarray(rn.SIL[name]).astype(np.float32)
    yy = np.arange(m.shape[0], dtype=np.float32)[:, None] - P
    keep = np.clip(np.minimum(yy - y_top, y_bot - yy) + 1.0, 0, 1)
    return Image.fromarray((m * keep).astype(np.uint8))


def watch_layers(name, scale, angle):
    """Foto original escalada e girada no plano + máscara do produto."""
    ph = base.PHOTOS[name]
    P = base.PAD
    w0, h0 = ph.im.width - 2 * P, ph.im.height - 2 * P
    crop = (P - 60, P - 60, P + w0 + 60, P + h0 + 60)
    img = ph.im.crop(crop)
    msk = post_mask(name).crop(crop)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    msk = msk.resize((nw, nh), Image.LANCZOS)
    img = img.rotate(angle, Image.BICUBIC, expand=True, fillcolor=ph.bg)
    msk = msk.rotate(angle, Image.BILINEAR, expand=True, fillcolor=0)
    # centro da caixa após escala/rotação
    cx, cy = ph.C[0] + 60, ph.C[1] + 60  # centro da caixa no recorte
    cx, cy = cx * scale, cy * scale
    ox, oy = nw / 2, nh / 2
    th = math.radians(angle)
    rx = (cx - ox) * math.cos(th) + (cy - oy) * math.sin(th)
    ry = -(cx - ox) * math.sin(th) + (cy - oy) * math.cos(th)
    ccx, ccy = img.width / 2 + rx, img.height / 2 + ry
    # máscara só da caixa (para a sombra mais espessa do corpo do relógio)
    disk = Image.new("L", img.size, 0)
    r = ph.R * scale
    ImageDraw.Draw(disk).ellipse((ccx - r, ccy - r, ccx + r, ccy + r), fill=255)
    return img, msk, disk, (ccx, ccy), ph.bg


def place(canvas, name, center, case_diam, angle):
    ph = base.PHOTOS[name]
    scale = case_diam / (2 * ph.R)
    img, msk, disk, (ccx, ccy), bg = watch_layers(name, scale, angle)
    x0 = int(round(center[0] - ccx))
    y0 = int(round(center[1] - ccy))
    full_m = Image.new("L", (W, H), 0)
    full_m.paste(msk, (x0, y0))
    full_d = Image.new("L", (W, H), 0)
    full_d.paste(disk, (x0, y0))
    full_i = Image.new("RGB", (W, H), bg)
    full_i.paste(img, (x0, y0))
    m = np.asarray(full_m).astype(np.float32) / 255

    def shadow(mask_img, blur, dist, k):
        sm = mask_img.filter(ImageFilter.GaussianBlur(blur))
        sm = sm.transform(sm.size, Image.AFFINE, (1, 0, -LIGHT[0] * dist, 0, 1, -LIGHT[1] * dist))
        return np.asarray(sm).astype(np.float32) / 255 * k

    s = np.maximum(shadow(full_m, 2.5, 2, 0.30), shadow(full_m, 9, 7, 0.22))
    s = np.maximum(s, shadow(full_d, 15, 13, 0.40))
    canvas = canvas * (1 - s * (1 - m))[..., None]
    t = np.asarray(full_i).astype(np.float32)
    B = np.array(bg, np.float32)

    # Interior seguro (pixels originais) e faixa de borda de ~2 px.
    hard = full_m.point(lambda v: 255 if v > 127 else 0)
    inner = np.asarray(hard.filter(ImageFilter.MinFilter(5))).astype(np.float32) / 255
    outer = np.asarray(full_m.point(lambda v: 255 if v > 4 else 0).filter(ImageFilter.MaxFilter(5))).astype(np.float32) / 255
    band = np.clip(outer - inner, 0, 1)
    # Cor do produto logo para dentro da borda (para "desmisturar" o cinza do estúdio)
    w_in = Image.fromarray((inner * 255).astype(np.uint8))
    num = np.stack([np.asarray(Image.fromarray(np.clip(t[..., c] * inner, 0, 255).astype(np.uint8))
                               .filter(ImageFilter.GaussianBlur(3))).astype(np.float32) for c in range(3)], -1)
    den = np.asarray(w_in.filter(ImageFilter.GaussianBlur(3))).astype(np.float32)[..., None]
    F_est = np.where(den > 2, num / np.maximum(den, 1e-3) * 255 / 255, t)
    dt = np.linalg.norm(t - B, axis=-1)
    dF = np.linalg.norm(F_est - B, axis=-1)
    alpha = np.clip(dt / np.maximum(dF, 30.0), 0, 1)
    a3 = alpha[..., None]
    F = np.where(a3 > 0.25, np.clip((t - (1 - a3) * B) / np.maximum(a3, 1e-3), 0, 255), F_est)
    edge_px = a3 * F + (1 - a3) * canvas
    outside = np.minimum(t / B, 1.0) * canvas
    i3, b3 = inner[..., None], band[..., None]
    rest = np.clip(1 - i3 - b3, 0, 1)
    return i3 * t + b3 * edge_px + rest * outside


def grade(arr):
    # grão fotográfico muito leve e vinheta de lente suave
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)
    vig = 1 - 0.07 * np.clip(d - 0.35, 0, 1) ** 1.6
    return arr * vig[..., None]


def main():
    rn.init_assets()
    canvas = surface()
    # Fita de veludo correndo em diagonal sob os relógios
    pts = bezier(np.array([-140, 1236.0]), np.array([300, 1000.0]),
                 np.array([760, 420.0]), np.array([1230, 120.0]))
    canvas = ribbon(canvas, pts, 132)
    # Quatro relógios paralelos, no mesmo tamanho real, ao longo da fita
    th = 50.0
    d = np.array([math.cos(math.radians(th)), -math.sin(math.radians(th))])
    c0 = np.array([W / 2 + 4, H / 2 - 6])
    L = 332
    layout = [("silver", -1.5, 1.2, (-6, 10)), ("gold", -0.5, -0.8, (8, -4)),
              ("rose", 0.5, 0.9, (-4, 6)), ("black", 1.5, -1.0, (6, -8))]
    for name, k, jitter, off in layout:
        c = c0 + d * k * L + np.array(off)
        canvas = place(canvas, name, c, 304, th + jitter)
    out = grade(canvas)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8)).save(OUT, quality=95, subsampling=0)
    print("post:", OUT)


if __name__ == "__main__":
    main()
