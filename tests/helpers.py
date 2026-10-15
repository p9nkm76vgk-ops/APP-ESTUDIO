"""Documentos de prueba sintéticos (no contienen material personal)."""
from __future__ import annotations

from pathlib import Path

LENGUA_TXT = """LOS VALORES DEL SE

1. SE VARIANTE DE LE/LES
La forma se sustituye al pronombre le cuando va junto a lo, la, los o las en función de complemento directo.
Ejemplo: Se lo conté a tu hermano. Así se evita la cacofonía.

2. SE REFLEXIVO
El sujeto realiza la acción y la recibe. Puede funcionar como complemento directo o complemento indirecto.
El niño se lava. La prueba consiste en cambiar el pronombre por una tercera persona.

3. PASIVA REFLEJA
El verbo concuerda con el sujeto paciente. Se descubrió el engaño en 1898. Se puede añadir un complemento agente.
La oración impersonal no tiene sujeto y el verbo va en singular.
"""

CATALAN_TXT = """EL SONET

1. Introducció, identificació del poema.
Ens trobam amb el poema que pertany al recull Quadern de sonets, escrit el 1934. És un sonet amb dos quartets i dos tercets.
Els versos són heptasíl·labs i la rima és assonant.

2. Figures retòriques
Trobam una antítesi i una metàfora. També hi ha encavalcaments entre els versos. El poeta fa servir la personificació.
"""

FISICA_TXT = """CINEMÁTICA
1. Movimiento rectilíneo
La velocidad es el cambio de posición. La aceleración es el cambio de velocidad. La fuerza se mide en newton.
Un coche con masa de 1200 kg acelera a 2 m/s. La energía cinética depende de la velocidad.
"""

AMBIGUO_TXT = """Notas sueltas de la semana
Tengo que repasar varias cosas antes del viernes y organizar mejor el horario de tarde.
Recordar llevar el libro y preguntar dudas en clase. Hacer la lista de tareas pendientes.
""" * 3


def make_docx(path: Path, text: str) -> Path:
    import docx
    d = docx.Document()
    for i, block in enumerate(text.strip().split("\n\n")):
        lines = block.splitlines()
        if i == 0:
            d.add_heading(lines[0], level=1)
            lines = lines[1:]
        for line in lines:
            d.add_paragraph(line)
    d.save(path)
    return path


def make_pdf(path: Path, text: str) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in text.splitlines():
        c.drawString(60, y, line[:95])
        y -= 16
        if y < 60:
            c.showPage()
            y = 800
    c.save()
    return path


def make_pptx(path: Path, text: str) -> Path:
    from pptx import Presentation
    prs = Presentation()
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = lines[0]
        slide.placeholders[1].text = "\n".join(lines[1:]) or lines[0]
    prs.save(path)
    return path


def make_image(path: Path, text: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1600, 60 + 44 * len(text.splitlines())), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(text.splitlines()):
        draw.text((30, 30 + 44 * i), line, fill="black", font=font)
    img.save(path)
    return path
