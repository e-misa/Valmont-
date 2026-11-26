#!/usr/bin/env bash
# Gera os vídeos VALMONT do zero.
#   ./build.sh          -> todos os vídeos
#   ./build.sh genese   -> só o vídeo da Coleção Gênese
#   ./build.sh natal    -> só o vídeo de Natal
#   ./build.sh campanha -> só a campanha de vendas de 18 s (filmagem real + estúdio)
# Requisitos: python3 com numpy e pillow, e ffmpeg (libx264 + aac).
set -euo pipefail
cd "$(dirname "$0")"
alvo="${1:-todos}"
python3 src/logo.py
if [[ "$alvo" == "todos" || "$alvo" == "genese" ]]; then
  python3 src/music.py
  python3 src/render.py
  ffmpeg -hide_banner -loglevel error -ss 14.9 -i output/valmont-genese-reels-1080x1920.mp4 \
    -frames:v 1 -q:v 2 -y output/capa-1080x1920.jpg
  echo "Pronto: output/valmont-genese-reels-1080x1920.mp4"
fi
if [[ "$alvo" == "todos" || "$alvo" == "natal" ]]; then
  python3 src/music_natal.py
  python3 src/render_natal.py
  ffmpeg -hide_banner -loglevel error -ss 14.9 -i output/valmont-natal-presente-1080x1920.mp4 \
    -frames:v 1 -q:v 2 -y output/capa-natal-1080x1920.jpg
  echo "Pronto: output/valmont-natal-presente-1080x1920.mp4"
fi
if [[ "$alvo" == "todos" || "$alvo" == "campanha" ]]; then
  python3 src/music_campanha.py
  python3 src/render_campanha.py
  ffmpeg -hide_banner -loglevel error -ss 17.9 -i output/valmont-campanha-18s-1080x1920.mp4 \
    -frames:v 1 -q:v 2 -y output/capa-campanha-1080x1920.jpg
  echo "Pronto: output/valmont-campanha-18s-1080x1920.mp4"
fi
