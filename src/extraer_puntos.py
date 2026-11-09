"""
extraer_puntos.py
=================
PASO 1 — Obtención de coordenadas a partir de la fotografía.

1. Segmentación de la vasija por color (espacio HSV, OpenCV): la cerámica es
   rojiza/saturada y el fondo es claro/poco saturado.
2. Extracción del CONTORNO COMPLETO del objeto  ->  datos/contorno_completo.csv
3. Estimación del EJE DE SIMETRÍA vertical (la vasija es un sólido de
   revolución: el punto medio entre el borde izquierdo y el derecho).
4. Selección de los PUNTOS DE CONTROL de las dos zonas a reconstruir:
     Zona A: borde superior (labio) izquierdo, fracturado.
     Zona B: oreja (asa) izquierda de la parte media del cuerpo, rota.
   Cada zona usa:
     - puntos "intacto": medidos directamente sobre el contorno real,
       a ambos lados de la fractura;
     - puntos "simetria": medidos en el lado DERECHO intacto (borde y oreja
       derecha) y reflejados respecto al eje:  x' = 2*x_eje - x.
   -> datos/puntos_control.csv

Sistema de coordenadas: cartesiano en píxeles, origen en la esquina inferior
izquierda de la foto (X = columna, Y = alto - fila), para que el eje Y apunte
hacia arriba como en un gráfico matemático.
"""
from __future__ import annotations

import csv
import os

import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "datos")
IMAGEN = os.path.join(DATOS, "vasija_tiwanaku.jpg")

FUENTE = ("https://www.laregion.bo/cinco-avances-de-investigacion-sobre-"
          "hallazgos-en-tiwanaku-que-podrian-cambiar-la-historia/")

# Límite inferior de análisis (debajo aparece el cuenco que está delante)
FILA_MAX_VASIJA = 1400


# ---------------------------------------------------------------------------
def cargar_imagen():
    img = cv2.imread(IMAGEN)
    if img is None:
        raise FileNotFoundError(IMAGEN)
    return img


def segmentar(img):
    """Máscara binaria de la cerámica (True = vasija)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    rojizo = (h <= 25) | (h >= 150)               # tonos de arcilla
    estricto = rojizo & ((s > 60) | ((v < 100) & (s > 35)))
    # en la mitad superior (fondo claro) se admite también la pintura oscura
    # y las zonas pálidas del cuello; abajo hay sombras grises que se excluyen
    permisivo = rojizo & ((s > 45) | ((v < 170) & (s > 20)))
    permisivo[1000:, :] = False
    m = (estricto | permisivo).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    # quedarse con la vasija (componente más grande por encima del cuenco)
    m[FILA_MAX_VASIJA:, :] = 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = (lab == k).astype(np.uint8) * 255
    # rellenar huecos interiores (grietas, manchas oscuras)
    cont, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    lleno = np.zeros_like(m)
    cv2.drawContours(lleno, cont, -1, 255, thickness=cv2.FILLED)
    return lleno > 0


def contorno(mascara):
    cont, _ = cv2.findContours(mascara.astype(np.uint8) * 255, cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_NONE)
    c = max(cont, key=cv2.contourArea)[:, 0, :]
    return c  # (columna, fila)


def borde_izq(mascara, fila):
    xs = np.where(mascara[fila])[0]
    return int(xs.min())


def borde_der(mascara, fila):
    xs = np.where(mascara[fila])[0]
    return int(xs.max())


def borde_sup(mascara, col):
    ys = np.where(mascara[:, col])[0]
    return int(ys.min())


def eje_simetria(mascara, filas):
    medios = [(borde_izq(mascara, f) + borde_der(mascara, f)) / 2.0 for f in filas]
    return float(np.mean(medios)), medios


# ---------------------------------------------------------------------------
def puntos_zona_borde(m, eje):
    """Zona A: labio superior izquierdo. Recorrido: desde la base del labio
    (unión con el cuello) subiendo por el borde exterior hasta el labio
    intacto del cuello."""
    pts = []
    # (1) intactos: borde exterior del fragmento izquierdo del labio
    for fila in (355, 295, 235, 175, 135):
        pts.append((borde_izq(m, fila), fila, "intacto"))
    # punta superior del fragmento (inicio de la fractura)
    pts.append((668, 118, "intacto"))
    # (2) simetría: borde derecho del labio reflejado (zona faltante)
    for fila in (95, 78, 62):
        xd = borde_der(m, fila)
        pts.append((round(2 * eje - xd), fila, "simetria"))
    # (3) intactos: labio del cuello después de la fractura
    pts.append((776, 55, "intacto"))
    for col in (830, 890):
        pts.append((col, borde_sup(m, col), "intacto"))
    return pts


def puntos_zona_oreja(m, eje):
    """Zona B: oreja izquierda del cuerpo. Recorrido de arriba hacia abajo."""
    pts = []
    for fila in (840, 895):                       # cuerpo intacto (arriba)
        pts.append((borde_izq(m, fila), fila, "intacto"))
    # (las filas 1000-1090 de la oreja derecha quedan cortadas por el borde de
    #  la foto: esa parte la reconstruye la propia interpolación del spline)
    for fila in (940, 960, 980):                   # oreja derecha reflejada
        pts.append((round(2 * eje - borde_der(m, fila)), fila, "simetria"))
    for fila in (1110, 1130, 1150):               # oreja derecha reflejada
        pts.append((round(2 * eje - borde_der(m, fila)), fila, "simetria"))
    for fila in (1215, 1270):                     # cuerpo intacto (abajo)
        pts.append((borde_izq(m, fila), fila, "intacto"))
    return pts


def a_cartesiano(pts, alto):
    return [(x, alto - f, tipo) for (x, f, tipo) in pts]


# ---------------------------------------------------------------------------
def extraer():
    img = cargar_imagen()
    alto, ancho = img.shape[:2]
    m = segmentar(img)
    c = contorno(m)

    # eje del labio (filas donde ambos lados del labio están intactos)
    eje_borde, _ = eje_simetria(m, range(145, 251, 5))
    # eje del cuerpo (filas sin orejas a ambos lados)
    filas_cuerpo = list(range(800, 900, 5)) + list(range(1220, 1400, 5))
    eje_cuerpo, _ = eje_simetria(m, filas_cuerpo)

    zona_a = a_cartesiano(puntos_zona_borde(m, eje_borde), alto)
    zona_b = a_cartesiano(puntos_zona_oreja(m, eje_cuerpo), alto)

    # guardar contorno completo (cartesiano)
    os.makedirs(DATOS, exist_ok=True)
    with open(os.path.join(DATOS, "contorno_completo.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x", "y"])
        for x, fila in c:
            w.writerow([int(x), int(alto - fila)])

    with open(os.path.join(DATOS, "puntos_control.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["zona", "i", "x", "y", "tipo"])
        for nombre, zona in (("A_borde", zona_a), ("B_oreja", zona_b)):
            for i, (x, y, tipo) in enumerate(zona):
                w.writerow([nombre, i, x, y, tipo])

    return {
        "imagen": img, "mascara": m, "contorno": c, "alto": alto, "ancho": ancho,
        "eje_borde": eje_borde, "eje_cuerpo": eje_cuerpo,
        "zona_a": zona_a, "zona_b": zona_b,
    }


if __name__ == "__main__":
    d = extraer()
    print(f"Imagen: {d['ancho']} x {d['alto']} px   |  contorno: {len(d['contorno'])} puntos")
    print(f"Eje de simetría  labio: x = {d['eje_borde']:.1f}   cuerpo: x = {d['eje_cuerpo']:.1f}")
    for nombre in ("zona_a", "zona_b"):
        print(f"\n{nombre}:")
        for i, (x, y, t) in enumerate(d[nombre]):
            print(f"  P{i:<2d} = ({x:4d}, {y:4d})   {t}")
