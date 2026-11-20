# VALMONT Brasil — Coleção Gênese · vídeo para Reels, Stories, TikTok e Facebook Ads

**Arquivo final:** `output/valmont-genese-reels-1080x1920.mp4`
**Capa sugerida:** `output/capa-1080x1920.jpg`

| Especificação | Valor |
|---|---|
| Formato | Vertical 9:16, 1080 × 1920 |
| Duração | 15,0 s, 30 fps (450 quadros) |
| Vídeo | H.264 High, yuv420p, BT.709, `faststart` |
| Áudio | AAC 256 kbps, 48 kHz, estéreo, ~ −14 LUFS (padrão das redes) |

## Fidelidade ao produto

Os relógios **não foram redesenhados nem gerados por IA**. Cada quadro usa os pixels
das fotos originais de estúdio (`assets/fotos/`), só com movimento de câmera
(escala e posição):

- caixa, pulseira, mostrador, ponteiros, logotipo e coroa são os da foto original;
- nenhuma rotação, deformação, troca de cor ou reflexo foi adicionada ao produto;
- o fundo de estúdio das fotos é uniforme. O quadro 9:16 foi completado com a
  mesma cor de fundo de cada foto. Só o fundo foi uniformizado (diferenças de 1 a 2
  tons e um fio de recorte na borda externa da foto). Sombras e produto ficaram intactos;
- o logotipo do cartão final foi extraído da tampa da caixa real
  (`assets/fotos/embalagem-colecao.jpg`, ver `src/logo.py`), sem redesenho.

## Roteiro (sincronizado com a trilha, 120 BPM)

| Tempo | Cena | Texto na tela |
|---|---|---|
| 0–2 s | Close do **Black** já no primeiro quadro. Câmera aproxima devagar e um painel preto desce com a frase | *A elegância está nos detalhes.* |
| 2–7 s | Os quatro modelos, alternando frontal e macro: Silver (frontal → macro), Gold (macro → frontal), Rosé (frontal → macro), Black (macro → frontal). Cortes no tempo e deslizes laterais nas trocas de modelo | Gênese · Silver / Gold / Rosé / Black (01–04) |
| 7–10 s | O Black recua para uma grade 2×2 e os outros três modelos entram. Uma faixa preta abre no centro com o preço | COLEÇÃO GÊNESE · **R$ 180,00** |
| 10–12 s | A faixa cresce e mostra a condição especial | CONDIÇÃO ESPECIAL · **10% OFF** · na compra de 2 ou mais relógios |
| 12–15 s | Assinatura: logotipo dourado, frase, chamada e botão, com os 4 relógios visíveis | VALMONT · *A simplicidade é a base da elegância.* · Escolha o seu. · **COMPRE AGORA** |

Todo o texto comercial fica na área segura central (entre y = 270 e y = 1250 px),
longe dos botões e legendas do Instagram, do TikTok e do Facebook. O vídeo é
compreensível sem som.

## Trilha sonora

A trilha (`src/music.py`) foi **composta e sintetizada neste projeto**, nota por nota,
sem samples nem loops de terceiros. Tem 120 BPM, em Ré menor com resolução em Fá maior,
e usa pad, arpejo de piano elétrico, "tique-taque" de relógio, kick, estalos, baixo,
impactos nos cortes e whooshes nas transições. Por ser original, pode ser usada
comercialmente pela VALMONT Brasil sem licença adicional.

Se preferir uma música de biblioteca (Artlist, Epidemic Sound etc.), basta trocar o
arquivo de áudio: `python3 src/render.py --audio caminho/da/musica.wav`.

## Como gerar novamente

Requisitos: `python3` com `numpy` e `pillow`, e `ffmpeg`.

```bash
./build.sh                                   # logotipo -> trilha -> vídeo -> capa
python3 src/render.py --still 1.0 8.5 14.9   # só exporta quadros PNG para conferência (em build/)
```

## Estrutura

```
assets/fotos/   fotos originais dos produtos (fonte obrigatória dos relógios)
assets/fonts/   Cormorant Garamond e Montserrat (SIL Open Font License, uso comercial livre)
assets/marca/   máscara do logotipo extraída da embalagem real
src/logo.py     extração do logotipo
src/music.py    composição da trilha original
src/render.py   montagem dos quadros e codificação do MP4
output/         vídeo final e capa
```
