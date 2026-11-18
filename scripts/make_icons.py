"""Gera os ícones do app (desenho original: espadas cruzadas num escudo). Uso: python scripts/make_icons.py"""
import pathlib
from PIL import Image, ImageDraw

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
BG, ACC, FG = (15, 17, 21), (108, 140, 255), (232, 234, 240)


def draw(size, pad):
    s = size * 4
    img = Image.new("RGB", (s, s), BG)
    d = ImageDraw.Draw(img)
    m = int(s * pad)
    d.rounded_rectangle([m, m, s - m, s - m], radius=int(s * 0.18), fill=(24, 27, 34), outline=ACC, width=int(s * 0.025))
    c, r = s / 2, s * 0.27
    for sign in (1, -1):  # duas lâminas cruzadas
        d.line([(c - r, c - sign * r), (c + r, c + sign * r)], fill=FG, width=int(s * 0.045))
        d.line([(c - r * 0.55, c - sign * r * 0.25 - sign * r * 0.3), (c - r * 0.25, c - sign * r * 0.55)], fill=ACC, width=int(s * 0.035))
    d.ellipse([c - s * 0.07, c - s * 0.07, c + s * 0.07, c + s * 0.07], fill=ACC)
    return img.resize((size, size), Image.LANCZOS)


for name, size, pad in [("icon-192.png", 192, 0.06), ("icon-512.png", 512, 0.06), ("apple-touch-icon.png", 180, 0.06), ("icon-maskable-512.png", 512, 0.16)]:
    draw(size, pad).save(SRC / name)
(SRC / "icon.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#0f1115"/>'
    '<rect x="6" y="6" width="88" height="88" rx="18" fill="#181b22" stroke="#6c8cff" stroke-width="2.5"/>'
    '<path d="M27 27 73 73M73 27 27 73" stroke="#e8eaf0" stroke-width="4.5" stroke-linecap="round"/>'
    '<circle cx="50" cy="50" r="7" fill="#6c8cff"/></svg>', encoding="utf-8")
print("ok")
