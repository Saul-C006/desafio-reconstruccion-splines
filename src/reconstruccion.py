"""
reconstruccion.py
=================
PASO 2 y 3 — Spline cúbico paramétrico y reconstrucción digital.

* Construye un spline cúbico natural paramétrico por zona.
* Verifica la continuidad C0, C1, C2 y compara con scipy.
* Genera la reconstrucción: el polígono encerrado por la curva del spline y la
  línea de fractura se rellena con la textura del lado simétrico intacto
  (solo donde falta material: los píxeles de cerámica original se conservan).
* Guarda figuras y tablas en  salida/.
"""
from __future__ import annotations

import csv
import os

import cv2
import numpy as np

import extraer_puntos as ep
from spline_cubico import SplineParametrico, validar_con_scipy

SALIDA = os.path.join(ep.RAIZ, "salida")


# ---------------------------------------------------------------------------
def construir_modelo():
    d = ep.extraer()
    alto = d["alto"]
    for clave, nombre in (("zona_a", "A"), ("zona_b", "B")):
        P = np.array([(x, y) for x, y, _ in d[clave]], dtype=float)
        sp = SplineParametrico(P)
        d["spline_" + nombre] = sp
        d["puntos_" + nombre] = P
        d["tipos_" + nombre] = [t for _, _, t in d[clave]]
        d["continuidad_" + nombre] = sp.verificar_continuidad()
        d["scipy_" + nombre] = validar_con_scipy(sp)
    d["poligono_A"] = poligono_borde(d["spline_A"], alto)
    d["poligono_B"] = poligono_oreja(d["spline_B"], alto)
    d["reconstruida"], d["mascara_rec"] = reconstruir(d)
    return d


def _curva_px(sp, i0, i1, alto, muestras=60):
    """Puntos (columna, fila) del spline entre los nodos i0 e i1."""
    xs, ys = [], []
    for i in range(i0, i1):
        x, y = sp.tramo(i, muestras)
        xs.append(x)
        ys.append(y)
    x = np.concatenate(xs)
    y = np.concatenate(ys)
    return np.stack([x, alto - y], axis=1)


def poligono_borde(sp, alto):
    """Zona A: curva reconstruida (P5 -> P9) + cierre por la fractura."""
    curva = _curva_px(sp, 5, 9, alto)
    cierre = np.array([[790, 58], [790, 200], [662, 200]], dtype=float)
    return np.vstack([curva, cierre])


def poligono_oreja(sp, alto):
    """Zona B: curva completa de la oreja + cierre por dentro del cuerpo."""
    curva = _curva_px(sp, 0, sp.n, alto)
    f0, f1 = curva[0, 1], curva[-1, 1]
    cierre = np.array([[455, f1], [455, f0]], dtype=float)
    return np.vstack([curva, cierre])


def reconstruir(d):
    """Rellena el material faltante con la textura reflejada del lado intacto."""
    img = d["imagen"].copy()
    alto, ancho = img.shape[:2]
    m = d["mascara"]
    rec_total = np.zeros((alto, ancho), bool)
    color_medio = img[m].reshape(-1, 3).mean(axis=0)

    for clave, eje in (("poligono_A", d["eje_borde"]), ("poligono_B", d["eje_cuerpo"])):
        pol = np.zeros((alto, ancho), np.uint8)
        cv2.fillPoly(pol, [np.round(d[clave]).astype(np.int32)], 255)
        faltante = (pol > 0) & (~m)
        filas, cols = np.nonzero(faltante)
        src = np.round(2 * eje - cols).astype(int)
        dentro = (src >= 0) & (src < ancho)
        src_c = np.clip(src, 0, ancho - 1)
        tex = img[filas, src_c].astype(float)
        # si el pixel reflejado cae fuera de la foto o no es cerámica -> color medio
        ok = dentro & m[filas, src_c]
        ruido = np.random.default_rng(0).normal(0, 6, (len(filas), 3))
        tex[~ok] = color_medio + ruido[~ok]
        img[filas, cols] = np.clip(tex, 0, 255).astype(np.uint8)
        rec_total |= faltante

    # suavizar la transición
    borde = cv2.dilate(rec_total.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    suave = cv2.GaussianBlur(img, (5, 5), 0)
    zona = borde & ~cv2.erode(rec_total.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    img[zona] = suave[zona]
    return img, rec_total


# ---------------------------------------------------------------------------
def guardar_tablas(d):
    os.makedirs(SALIDA, exist_ok=True)
    for z in ("A", "B"):
        sp = d["spline_" + z]
        with open(os.path.join(SALIDA, f"coeficientes_zona_{z}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["i", "t_i", "t_i+1", "ax", "bx", "cx", "dx", "ay", "by", "cy", "dy"])
            for fila in sp.coeficientes():
                w.writerow([fila[0]] + [f"{v:.6g}" for v in fila[1:]])


def figura_resumen(d):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    alto, ancho = d["alto"], d["ancho"]
    ext = [0, ancho, 0, alto]
    rgb = cv2.cvtColor(d["imagen"], cv2.COLOR_BGR2RGB)
    rgb_rec = cv2.cvtColor(d["reconstruida"], cv2.COLOR_BGR2RGB)
    fig, ax = plt.subplots(1, 3, figsize=(18, 8))
    ax[0].imshow(rgb, extent=ext)
    ax[0].set_title("Original + puntos de control")
    ax[1].imshow(rgb, extent=ext, alpha=0.45)
    ax[1].set_title("Splines cúbicos paramétricos")
    ax[2].imshow(rgb_rec, extent=ext)
    ax[2].set_title("Reconstrucción")
    for z, col in (("A", "#1f77b4"), ("B", "#d62728")):
        sp, P = d["spline_" + z], d["puntos_" + z]
        X, Y, _ = sp.curva()
        for a in ax[:2]:
            a.plot(X, Y, color=col, lw=2)
            a.scatter(P[:, 0], P[:, 1], c=["k" if t == "intacto" else "orange"
                                           for t in d["tipos_" + z]], s=25, zorder=5)
    for a in ax:
        a.set_xlim(250, 1450)
        a.set_ylim(700, 2048)
    fig.tight_layout()
    fig.savefig(os.path.join(SALIDA, "resumen_reconstruccion.png"), dpi=90)
    plt.close(fig)
    cv2.imwrite(os.path.join(SALIDA, "vasija_reconstruida.jpg"), d["reconstruida"])


if __name__ == "__main__":
    d = construir_modelo()
    guardar_tablas(d)
    figura_resumen(d)
    for z in ("A", "B"):
        c0, c1, c2 = d["continuidad_" + z]
        print(f"Zona {z}: {d['spline_' + z].n} tramos | saltos C0={c0:.2e} C1={c1:.2e} "
              f"C2={c2:.2e} | dif. vs scipy = {d['scipy_' + z]:.2e}")
    print("Figuras y tablas en", SALIDA)
