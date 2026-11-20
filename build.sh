#!/usr/bin/env bash
# Gera o vídeo VALMONT Gênese do zero: logotipo -> trilha -> vídeo final.
# Requisitos: python3 com numpy e pillow, e ffmpeg (libx264 + aac).
set -euo pipefail
cd "$(dirname "$0")"
python3 src/logo.py
python3 src/music.py
python3 src/render.py "$@"
ffmpeg -hide_banner -loglevel error -ss 14.9 -i output/valmont-genese-reels-1080x1920.mp4 \
  -frames:v 1 -q:v 2 -y output/capa-1080x1920.jpg
echo "Pronto: output/valmont-genese-reels-1080x1920.mp4"
