"""Composição fotográfica dos relógios sobre superfícies reais (vista de cima).

Funções genéricas (qualquer tamanho de quadro) usadas pela campanha:
  - stone(w, h)     superfície de pedra/reboco claro com luz de janela
  - matte_black(w,h) fundo preto fosco com luz suave
  - place(...)      coloca um relógio (pixels da foto original, escalado e
                    girado só no plano) com sombra de contato, sombra original
                    transferida e bordas descontaminadas do cinza do estúdio.
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

LIGHT = np.array([0.62, 0.78])  # sombra cai para baixo/direita (luz do alto à esquerda)


def init():
    rn.init_assets()


def smooth_noise(rng, h, w, cell, amp):
    gh, gw = max(2, h // cell + 3), max(2, w // cell + 3)
    g = rng.standard_normal((gh, gw)).astype(np.float32)
    im = Image.fromarray(g, mode="F").resize((w + 2 * cell, h + 2 * cell), Image.BICUBIC)
    a = np.asarray(im)[cell:cell + h, cell:cell + w]
    return a / (a.std() + 1e-6) * amp


def stone(w, h, seed=7, base_col=(233, 225, 213), ss=2):
    rng = np.random.default_rng(seed)
    H2, W2 = h * ss, w * ss
    lum = 1.0 + smooth_noise(rng, H2, W2, 520, 0.010) + smooth_noise(rng, H2, W2, 140, 0.006)
    lum = lum + smooth_noise(rng, H2, W2, 14, 0.006) + smooth_noise(rng, H2, W2, 4, 0.006)
    lum = lum + rng.normal(0, 0.010, (H2, W2)).astype(np.float32)
    yy, xx = np.mgrid[0:H2, 0:W2].astype(np.float32)
    xn, yn = xx / W2, yy / H2
    fall = 1.045 - 0.10 * (0.55 * xn + 0.45 * yn) - 0.05 * ((xn - 0.3) ** 2 + (yn - 0.25) ** 2)
    arr = np.array(base_col, np.float32) * (lum * fall)[..., None]
    warm = smooth_noise(rng, H2, W2, 300, 1.0)[..., None]
    arr = arr + warm * np.array((2.0, 0.5, -2.0), np.float32)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    return np.asarray(img).astype(np.float32)


def matte_black(w, h, seed=3, spot=(0.5, 0.33)):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx / w - spot[0]) / 0.75) ** 2 + ((yy / h - spot[1]) / 0.55) ** 2)
    light = 1.0 - 0.55 * np.clip(d, 0, 1.4) / 1.4
    lum = light * (1 + smooth_noise(rng, h, w, 260, 0.04) + rng.normal(0, 0.035, (h, w)).astype(np.float32))
    col = np.array((30, 29, 28), np.float32)
    return col * lum[..., None]


def strap_end_rows(name):
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


_MASKS = {}


def post_mask(name):
    if name in _MASKS:
        return _MASKS[name]
    P = base.PAD
    y_top, y_bot = strap_end_rows(name)
    m = np.asarray(rn.SIL[name]).astype(np.float32)
    yy = np.arange(m.shape[0], dtype=np.float32)[:, None] - P
    keep = np.clip(np.minimum(yy - y_top, y_bot - yy) + 1.0, 0, 1)
    # Importante: nenhum "vão" interno é recortado. Reflexos brancos do metal
    # têm a mesma cor do fundo de estúdio; recortá-los alteraria o produto.
    _MASKS[name] = Image.fromarray(np.clip(m * keep, 0, 255).astype(np.uint8))
    return _MASKS[name]


def watch_layers(name, scale, angle):
    ph = base.PHOTOS[name]
    P = base.PAD
    w0, h0 = ph.im.width - 2 * P, ph.im.height - 2 * P
    crop = (P - 60, P - 60, P + w0 + 60, P + h0 + 60)
    img = ph.im.crop(crop)
    msk = post_mask(name).crop(crop)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    msk = msk.resize((nw, nh), Image.LANCZOS)
    if scale > 1.25:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.3, percent=int(min(70, 18 + 30 * (scale - 1.25))), threshold=2))
    img = img.rotate(angle, Image.BICUBIC, expand=True, fillcolor=ph.bg)
    msk = msk.rotate(angle, Image.BILINEAR, expand=True, fillcolor=0)
    cx, cy = (ph.C[0] + 60) * scale, (ph.C[1] + 60) * scale
    ox, oy = nw / 2, nh / 2
    th = math.radians(angle)
    rx = (cx - ox) * math.cos(th) + (cy - oy) * math.sin(th)
    ry = -(cx - ox) * math.sin(th) + (cy - oy) * math.cos(th)
    ccx, ccy = img.width / 2 + rx, img.height / 2 + ry
    disk = Image.new("L", img.size, 0)
    r = ph.R * scale
    ImageDraw.Draw(disk).ellipse((ccx - r, ccy - r, ccx + r, ccy + r), fill=255)
    return img, msk, disk, (ccx, ccy), ph.bg


def place(canvas, name, center, case_diam, angle=0.0, shadow_k=1.0):
    H, W = canvas.shape[:2]
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
    k = case_diam / 304.0  # sombras proporcionais ao tamanho

    def shadow(mask_img, blur, dist, a):
        sm = mask_img.filter(ImageFilter.GaussianBlur(blur * k))
        sm = sm.transform(sm.size, Image.AFFINE, (1, 0, -LIGHT[0] * dist * k, 0, 1, -LIGHT[1] * dist * k))
        return np.asarray(sm).astype(np.float32) / 255 * a * shadow_k

    s = np.maximum(shadow(full_m, 2.5, 2, 0.30), shadow(full_m, 9, 7, 0.22))
    s = np.maximum(s, shadow(full_d, 15, 13, 0.40))
    canvas = canvas * (1 - s * (1 - m))[..., None]
    t = np.asarray(full_i).astype(np.float32)
    B = np.array(bg, np.float32)

    kk = 2 * max(2, int(round(1.6 * max(scale, 1.0)))) + 1  # faixa de borda proporcional à ampliação
    hard = full_m.point(lambda v: 255 if v > 127 else 0)
    inner = hard.filter(ImageFilter.MinFilter(kk)).filter(ImageFilter.GaussianBlur(kk / 4))
    inner = np.asarray(inner).astype(np.float32) / 255
    outer = np.asarray(full_m.point(lambda v: 255 if v > 4 else 0).filter(ImageFilter.MaxFilter(kk))).astype(np.float32) / 255
    band = np.clip(outer - inner, 0, 1)
    w_in = Image.fromarray((inner * 255).astype(np.uint8))
    num = np.stack([np.asarray(Image.fromarray(np.clip(t[..., c] * inner, 0, 255).astype(np.uint8))
                               .filter(ImageFilter.GaussianBlur(3))).astype(np.float32) for c in range(3)], -1)
    den = np.asarray(w_in.filter(ImageFilter.GaussianBlur(3))).astype(np.float32)[..., None]
    F_est = np.where(den > 2, num / np.maximum(den, 1e-3), t)
    dt = np.linalg.norm(t - B, axis=-1)
    dF = np.linalg.norm(F_est - B, axis=-1)
    alpha = np.clip(dt / np.maximum(dF, 30.0), 0, 1)
    a3 = alpha[..., None]
    F = np.where(a3 > 0.25, np.clip((t - (1 - a3) * B) / np.maximum(a3, 1e-3), 0, 255), F_est)
    # Na borda, o mais escuro entre "recorte" e "multiplicar": tira o halo claro
    # do fundo de estúdio sem nunca clarear o produto.
    edge_px = np.minimum(a3 * F + (1 - a3) * canvas, t * canvas / B)
    outside = np.minimum(t / B, 1.0) * canvas
    i3, b3 = inner[..., None], band[..., None]
    rest = np.clip(1 - i3 - b3, 0, 1)
    return i3 * t + b3 * edge_px + rest * outside
