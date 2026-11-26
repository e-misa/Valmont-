# VALMONT Brasil — vídeos para Reels, Stories, TikTok e Facebook Ads

| Vídeo | Arquivo | Capa |
|---|---|---|
| Coleção Gênese (institucional) | `output/valmont-genese-reels-1080x1920.mp4` | `output/capa-1080x1920.jpg` |
| Natal: "Presenteie com elegância" | `output/valmont-natal-presente-1080x1920.mp4` | `output/capa-natal-1080x1920.jpg` |
| Campanha de vendas, 18 s (filmagem real) | `output/valmont-campanha-18s-1080x1920.mp4` | `output/capa-campanha-1080x1920.jpg` |
| Campanha de vendas, 18 s, **versão 2** (linho bege) | `output/valmont-campanha-18s-v2-1080x1920.mp4` | `output/capa-campanha-v2-1080x1920.jpg` |

**Foto para post (feed 4:5):** `output/post-natal-flatlay-1080x1350.jpg`. É um flat lay
(vista de cima) dos quatro modelos sobre uma fita de veludo bordô. Os relógios são os
pixels das fotos originais, todos no mesmo tamanho real e só girados no plano da mesa.
A sombra de estúdio de cada foto foi transferida para a nova superfície e as bordas
foram descontaminadas do cinza do estúdio. Para gerar de novo: `python3 src/post_natal.py`.

Os vídeos têm a mesma especificação técnica (a campanha de vendas dura 18 s):

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

## Vídeo 1: Coleção Gênese

### Roteiro (sincronizado com a trilha, 120 BPM)

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

## Vídeo 2: Natal, "Presenteie com elegância"

Clima de presente e de festas: papel de presente bordô com a montanha VALMONT
estampada em dourado, fitas de cetim, luzes desfocadas quentes e tipografia
caligráfica. Os relógios continuam sendo os pixels das fotos originais. O fundo
cinza de estúdio é trocado por um cenário marfim e dourado por meio de uma
máscara do produto (`make_sil` em `src/render_natal.py`). Dentro do relógio
(caixa, mostrador, ponteiros, logo, pulseira e coroa) nenhum pixel muda. As
transições empurram um relógio inteiro para fora enquanto o próximo entra, com
a fita na emenda, para que dois modelos nunca apareçam misturados no mesmo quadro.

| Tempo | Cena | Texto na tela |
|---|---|---|
| 0–2 s | O papel de presente se abre de baixo para cima e revela o **Gold** em close | NESTE NATAL · *Presenteie com elegância.* |
| 2–6 s | Os quatro modelos sobre fundo marfim com luzes de Natal, trocados por fita dourada a cada tempo | Clássico · Silver / Sofisticado · Gold / Delicado · Rosé / Marcante · Black |
| 6–8 s | Foto real das quatro peças nas caixas VALMONT | O PRESENTE PERFEITO · *Na caixa VALMONT, pronto para presentear.* |
| 8–10 s | Os quatro modelos em cartões, "embrulhados" por fitas douradas, com o preço na fita | COLEÇÃO GÊNESE · **R$ 180,00** |
| 10–12,5 s | As fitas saem e o painel bordô abre com a oferta | *Um para presentear. Outro para você.* · **10% OFF** · na compra de 2 ou mais relógios |
| 12,5–15 s | Assinatura com os 4 relógios visíveis | VALMONT · *A simplicidade é a base da elegância.* · *Boas Festas* · **PRESENTEIE AGORA** |

Trilha original de Natal (`src/music_natal.py`): 120 BPM, em Ré maior, com
glockenspiel, pizzicato, guizos e cordas, e um acorde de Sol menor que dá a
nostalgia natalina. A melodia é composta para o projeto e não reproduz nenhuma
canção existente.

## Vídeo 3: Campanha de vendas (18 s)

A campanha mistura a **filmagem real enviada pela marca**
(`assets/videos/valmont-referencias.mov`: mão segurando cada modelo, vista lateral,
fecho e os relógios sobre a mesa) com closes e composições feitos a partir das fotos de
estúdio sobre pedra clara (`src/flatlay.py`). A filmagem é usada no tempo real, só
recortada e ampliada, sem redesenho nem interpolação. Os cortes são secos e caem no
tempo da música, por isso nunca há dois relógios sobrepostos no mesmo quadro. O
anúncio do concorrente serviu só como referência de ritmo e de faixa de preço. Nada
dele entra no vídeo nem no repositório.

| Tempo | Cena | Texto na tela |
|---|---|---|
| 0–1 s | Macro do **Gold** sobre pedra clara | VALMONT · *A elegância está nos detalhes.* |
| 1–2 s | Filmagem real: mão segurando o Gold | (mesmo título) |
| 2–4 s | **Silver**: na mão, depois sobre a mesa | GÊNESE · SILVER |
| 4–6 s | **Gold**: mostrador sobre a mesa, depois o fecho | GÊNESE · GOLD |
| 6–8 s | **Rosé**: de frente na mão, depois de lado | GÊNESE · ROSÉ |
| 8–10 s | **Black**: na mão, depois macro de estúdio | GÊNESE · BLACK |
| 10–13 s | Os quatro modelos e uma faixa preta | COLEÇÃO GÊNESE · **R$ 180,00 cada** |
| 13–16 s | Gold e Black lado a lado | LEVE 2 OU MAIS · **GANHE 10% OFF** |
| 16–18 s | Os quatro modelos e a assinatura | VALMONT · *A simplicidade é a base da elegância.* · **COMPRE AGORA** |

As etiquetas dos modelos ficam numa faixa fixa no topo (y 290–362). Cada trecho de
filmagem foi escolhido para a caixa do relógio nunca passar por baixo delas.

Não há relógio no pulso porque não existe filmagem ou foto real disso. Também não há
preço "de/por", contagem regressiva nem prazo, já que nenhum deles foi informado.

### Versão 2 (mais fiel ao briefing)

Mesma filmagem real, roteiro e textos. Muda o seguinte:
- os closes e as composições ficam sobre **tecido de linho bege** (`fl.linen`, com trama de fios
  irregulares e dobras suaves) em vez de pedra;
- os macros têm **profundidade de campo** de lente macro: nítido no mostrador e no logotipo,
  com desfoque suave e crescente só nas bordas do quadro (`fl.depth_of_field`);
- o plano do Gold sobre a mesa (4–5 s) faz uma **aproximação suave** do mostrador frontal;
- a mão real entra aos 1,2 s, logo depois do macro de abertura.

Para gerar: `python3 src/render_campanha.py --versao 2` (ou `./build.sh campanha`, que gera as duas).

## Trilha sonora

A trilha do vídeo 1 (`src/music.py`) foi **composta e sintetizada neste projeto**, nota por nota,
sem samples nem loops de terceiros. Tem 120 BPM, em Ré menor com resolução em Fá maior,
e usa pad, arpejo de piano elétrico, "tique-taque" de relógio, kick, estalos, baixo,
impactos nos cortes e whooshes nas transições. Por ser original, pode ser usada
comercialmente pela VALMONT Brasil sem licença adicional.

Se preferir uma música de biblioteca (Artlist, Epidemic Sound etc.), basta trocar o
arquivo de áudio: `python3 src/render.py --audio caminho/da/musica.wav`.

## Como gerar novamente

Requisitos: `python3` com `numpy` e `pillow`, e `ffmpeg`.

```bash
./build.sh                                   # os dois vídeos (ou: ./build.sh genese | ./build.sh natal)
python3 src/render.py --still 1.0 8.5 14.9   # quadros PNG de conferência do vídeo 1 (em build/)
python3 src/render_natal.py --still 0.5 9    # quadros PNG de conferência do vídeo de Natal
python3 src/render_campanha.py --still 0.5 11  # quadros PNG de conferência da campanha
```

## Estrutura

```
assets/fotos/   fotos originais dos produtos (fonte obrigatória dos relógios)
assets/fonts/   Cormorant Garamond, Montserrat e Pinyon Script (SIL Open Font License, uso comercial livre)
assets/marca/   máscara do logotipo extraída da embalagem real
src/logo.py     extração do logotipo
src/music.py           trilha original do vídeo 1
src/render.py          vídeo 1 (Coleção Gênese)
src/music_natal.py     trilha original de Natal
src/render_natal.py    vídeo 2 (Natal)
src/post_natal.py      foto flat lay de Natal para o feed
src/flatlay.py         composição de estúdio (relógio real sobre pedra, sombras, bordas)
src/music_campanha.py  trilha original da campanha de 18 s
src/render_campanha.py vídeo 3 (campanha de vendas)
assets/videos/         filmagem real dos quatro modelos enviada pela marca
output/         vídeo final e capa
```
