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
        ORIGENES.append((xd, fila))
    # (3) intactos: labio del cuello después de la fractura
    pts.append((776, 55, "intacto"))
    for col in (830, 890):
        pts.append((col, borde_sup(m, col), "intacto"))
    return pts


# Punto del lado derecho intacto del que proviene cada punto "simetria"
ORIGENES = []

# Oreja derecha (intacta): filas donde nace y termina sobre el cuerpo
OREJA_DER = (920, 1185)
# Oreja izquierda (rota): entre el resto de su unión superior (y ≈ 1290) y el
# muñón inferior (y ≈ 1000), es decir  y ∈ [1000, 1300] aprox.
OREJA_IZQ = (760, 1045)


def linea_cuerpo_izq(m):
    """Silueta izquierda del cuerpo SIN oreja: parábola x(fila) ajustada por
    mínimos cuadrados con los bordes medidos por encima y por debajo de la oreja."""
    filas = list(range(690, 761, 10)) + list(range(1140, 1201, 10))
    xs = [borde_izq(m, f) for f in filas]
    coef = np.polyfit(filas, xs, 2)
    return lambda f: float(np.polyval(coef, f))


def puntos_zona_oreja(m, eje):
    """Zona B: oreja izquierda de la parte media. Recorrido de arriba hacia abajo.

    La forma (cuánto sobresale la oreja del cuerpo) se toma de la oreja derecha
    intacta y se traslada a la altura donde están los restos de la oreja
    izquierda (unión superior y muñón inferior)."""
    pts = []
    for fila in (700, 740):                        # cuerpo intacto (arriba)
        pts.append((borde_izq(m, fila), fila, "intacto"))
    f_d0, f_d1 = OREJA_DER
    f_i0, f_i1 = OREJA_IZQ
    # línea del cuerpo derecho bajo la oreja derecha (recta entre sus uniones)
    cuerpo_der = lambda f: np.interp(f, OREJA_DER, (borde_der(m, f_d0), borde_der(m, f_d1)))
    cuerpo_izq = linea_cuerpo_izq(m)
    # (las filas 1000-1090 de la oreja derecha quedan cortadas por el borde de
    #  la foto: esa parte la reconstruye la propia interpolación del spline)
    for fila in (940, 960, 980, 1110, 1130, 1150):   # oreja derecha -> simetría
        sobresale = borde_der(m, fila) - cuerpo_der(fila)
        fila_izq = f_i0 + (fila - f_d0) * (f_i1 - f_i0) / (f_d1 - f_d0)
        pts.append((round(cuerpo_izq(fila_izq) - sobresale), round(fila_izq), "simetria"))
        ORIGENES.append((borde_der(m, fila), fila))
    for fila in (1065, 1115):                      # muñón intacto (abajo)
        pts.append((borde_izq(m, fila), fila, "intacto"))
    return pts


def mapa_textura_oreja(m, eje):
    """Para cada píxel (fila, col) de la oreja izquierda reconstruida devuelve
    el píxel equivalente de la oreja DERECHA intacta (misma posición relativa).
    Si cae fuera de la foto, se usa el reflejo sobre el propio cuerpo."""
    f_d0, f_d1 = OREJA_DER
    f_i0, f_i1 = OREJA_IZQ
    xd0, xd1 = borde_der(m, f_d0), borde_der(m, f_d1)
    cuerpo_izq = linea_cuerpo_izq(m)
    ancho = m.shape[1]

    def mapa(filas, cols):
        filas = np.asarray(filas, float)
        cols = np.asarray(cols, float)
        fs = f_d0 + (filas - f_i0) * (f_d1 - f_d0) / (f_i1 - f_i0)
        base_i = np.array([cuerpo_izq(f) for f in filas])
        base_d = np.interp(fs, OREJA_DER, (xd0, xd1))
        cs = base_d + (base_i - cols)
        fs_i = np.clip(np.round(fs).astype(int), 0, m.shape[0] - 1)
        cs_i = np.round(cs).astype(int)
        ok = (cs_i >= 0) & (cs_i < ancho)
        ok[ok] &= m[fs_i[ok], cs_i[ok]]
        # alternativa: reflejo hacia el interior del cuerpo
        alt = np.round(2 * base_i - cols + 25).astype(int)
        fs_out = np.where(ok, fs_i, np.round(filas).astype(int))
        cs_out = np.where(ok, cs_i, alt)
        return fs_out, cs_out

    return mapa


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

    ORIGENES.clear()
    zona_a = a_cartesiano(puntos_zona_borde(m, eje_borde), alto)
    origen_a = [(x, alto - f) for x, f in ORIGENES]
    ORIGENES.clear()
    zona_b = a_cartesiano(puntos_zona_oreja(m, eje_cuerpo), alto)
    origen_b = [(x, alto - f) for x, f in ORIGENES]

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
        "origen_A": origen_a, "origen_B": origen_b,
        "mapa_A": lambda f, c: (f, 2 * eje_borde - c),
        "mapa_B": mapa_textura_oreja(m, eje_cuerpo),
    }


if __name__ == "__main__":
    d = extraer()
    print(f"Imagen: {d['ancho']} x {d['alto']} px   |  contorno: {len(d['contorno'])} puntos")
    print(f"Eje de simetría  labio: x = {d['eje_borde']:.1f}   cuerpo: x = {d['eje_cuerpo']:.1f}")
    for nombre in ("zona_a", "zona_b"):
        print(f"\n{nombre}:")
        for i, (x, y, t) in enumerate(d[nombre]):
            print(f"  P{i:<2d} = ({x:4d}, {y:4d})   {t}")
