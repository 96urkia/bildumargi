# -*- coding: utf-8 -*-
"""Crea el icono de Bildumargi para Windows: la «b» con sus dos ondas,
recortada del logo completo (frontend/imagenes/completo.png) y centrada sobre
un fondo claro redondeado, para que se vea en el escritorio y en la barra de
tareas.

    python packaging/windows/crear_icono.py
"""

import os

from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(AQUI, "..", "..", "frontend", "imagenes", "completo.png")
TAM = 1024
# En completo.svg (viewBox 4.3 -811.7 5696 1054.1) la «b» y las ondas van de
# x = 4.3 a x ≈ 1004 (la onda clara); la «i» empieza en 1084.
FRACCION_MARCA = (1045 - 4.3) / 5696.0


def crear():
    logo = Image.open(LOGO).convert("RGBA")
    marca = logo.crop((0, 0, round(logo.width * FRACCION_MARCA), logo.height))
    marca = marca.crop(marca.getbbox())                       # sin márgenes vacíos
    lado = round(TAM * 0.74)
    escala = lado / max(marca.size)
    marca = marca.resize((round(marca.width * escala), round(marca.height * escala)), Image.Resampling.LANCZOS)
    icono = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    ImageDraw.Draw(icono).rounded_rectangle([0, 0, TAM - 1, TAM - 1], radius=round(TAM * 0.2),
                                            fill=(255, 255, 255, 255))
    icono.alpha_composite(marca, ((TAM - marca.width) // 2, (TAM - marca.height) // 2))
    return icono


if __name__ == "__main__":
    icono = crear()
    icono.save(os.path.join(AQUI, "bildumargi.png"))
    icono.save(os.path.join(AQUI, "bildumargi.ico"),
               sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Icono creado en", AQUI)
