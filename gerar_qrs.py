"""Gera cartões de mesa com QR code (PNG) na pasta qrs/.

Uso:
    python gerar_qrs.py 192.168.0.10        # IP do seu PC na rede Wi-Fi
    python gerar_qrs.py https://meuapp.streamlit.app   # se publicar online
"""
import os
import sys
import textwrap

import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont

base = sys.argv[1] if len(sys.argv) > 1 else "localhost"
if not base.startswith("http"):
    base = f"http://{base}:8501"
MESAS_POR_RESTAURANTE = 2

os.makedirs("qrs", exist_ok=True)
R = pd.read_csv("restaurantes.csv")


def fonte(tam):
    for f in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, tam)
        except OSError:
            pass
    return ImageFont.load_default()


def centro(d, y, txt, f, cor, largura=700):
    w = d.textbbox((0, 0), txt, font=f)[2]
    d.text(((largura - w) / 2, y), txt, font=f, fill=cor)


for _, r in R.iterrows():
    for m in range(1, MESAS_POR_RESTAURANTE + 1):
        codigo = f"{r['id']}-M{m}"
        img = Image.new("RGB", (700, 1000), "#15181d")
        d = ImageDraw.Draw(img)
        centro(d, 40, "VOZ DO PRATO", fonte(52), "#d6203a")
        centro(d, 110, r["nome"], fonte(44), "#ffffff")
        centro(d, 170, f"Mesa {m}", fonte(30), "#98a2b3")
        qr = qrcode.make(f"{base}/?mesa={codigo}").resize((420, 420))
        img.paste(qr, (140, 230))
        y = 680
        for linha in ["Você sentou. Você provou.", "Agora você opina."]:
            centro(d, y, linha, fonte(34), "#ffb400"); y += 46
        y += 14
        for linha in textwrap.wrap(f"Escaneie, avalie este prato e ganhe o selo exclusivo de {r['nome']}.", 42):
            centro(d, y, linha, fonte(26), "#e6e9ee"); y += 36
        centro(d, 920, "Michelin dando voz ao público. #VozDoPrato", fonte(24), "#98a2b3")
        img.save(f"qrs/{codigo}.png")
print(f"{len(R) * MESAS_POR_RESTAURANTE} cartões em ./qrs  (URL base: {base})")
