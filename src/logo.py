"""Extrai o logotipo VALMONT (montanha + palavra) da foto real da embalagem.

O logotipo é recortado da tampa da caixa (hot stamping dourado sobre cartão
escuro). Nenhum desenho novo é criado: a forma vem dos pixels da foto, apenas
ampliada e suavizada para virar uma máscara alfa nítida em alta resolução.

Saída: assets/marca/valmont-logo-alpha.png (máscara em tons de cinza).
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets/fotos/embalagem-colecao.jpg"
OUT = ROOT / "assets/marca/valmont-logo-alpha.png"

# Região da tampa de trás, onde o logotipo aparece inteiro e frontal.
BOX = (290, 55, 590, 175)
S = 8  # fator de super-amostragem


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def main():
    im = Image.open(SRC).convert("RGB")
    w, h = BOX[2] - BOX[0], BOX[3] - BOX[1]
    big = im.crop(BOX).resize((w * S, h * S), Image.LANCZOS)
    big = big.filter(ImageFilter.GaussianBlur(S * 0.25))
    a = np.asarray(big).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = a.mean(axis=2)
    # Dourado: vermelho bem acima do azul e mais claro que o cartão.
    score = 0.6 * (r - b) + 0.4 * (lum - 80.0)
    m = smoothstep((score - 45.0) / 14.0)

    # Suaviza o contorno (ruído do celular) sem mudar a forma.
    mi = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(S * 0.45))
    m2 = np.asarray(mi).astype(np.float32) / 255.0
    m2 = smoothstep((m2 - 0.38) / 0.24)

    mask = Image.fromarray((m2 * 255).astype(np.uint8))
    bbox = mask.point(lambda v: 255 if v > 40 else 0).getbbox()
    mask = mask.crop(bbox)
    pad = 24
    canvas = Image.new("L", (mask.width + 2 * pad, mask.height + 2 * pad), 0)
    canvas.paste(mask, (pad, pad))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT)
    print("logo:", OUT, canvas.size)


if __name__ == "__main__":
    main()
