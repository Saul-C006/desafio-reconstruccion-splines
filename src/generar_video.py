"""
generar_video.py
================
PASO 4 — Animación. Genera el video final (MP4 1280x720) de ~3:00 minutos
con la estructura exigida por el desafío:

  Parte 1 (0:00-0:25) Presentación de la pieza
  Parte 2 (0:25-0:50) Obtención de los puntos
  Parte 3 (0:50-1:15) Explicación del Spline (paramétrico, continuidad C0,C1,C2)
  Parte 4 (1:15-2:00) Reconstrucción paso a paso
  Parte 5 (2:00-2:35) Animación final (original -> reconstrucción -> resultado)
  Parte 6 (2:35-3:00) Conclusión

Todo lo que se dibuja (curvas, tramos, relleno) se calcula a partir del
modelo matemático (spline cúbico); nada se dibuja a mano.

Uso:
    python generar_video.py                 # video completo -> salida/video_reconstruccion.mp4
    python generar_video.py --preview 10 80 # solo cuadros PNG en esos segundos
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

import extraer_puntos as ep  # noqa: E402
from reconstruccion import SALIDA, construir_modelo  # noqa: E402

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
ESTUDIANTE = "Saul Walter Callisaya"
TITULO = "Reconstrucción digital de una vasija de Tiwanaku mediante Splines Cúbicos"
W, H, DPI = 1280, 720, 100
FPS = 24
DURACION = 180.0

FONDO = "#14161c"
PANEL = "#1e2129"
TEXTO = "#eceff4"
TENUE = "#9aa3b2"
ACENTO = "#f0b429"      # dorado
COL_A = "#4fc3f7"       # zona A (borde)
COL_B = "#ff7a6b"       # zona B (oreja)
COL_SIM = "#ffb74d"     # puntos de simetría
COL_INT = "#ffffff"     # puntos intactos
COLORES_TRAMO = ["#4fc3f7", "#ffd54f", "#81c784", "#ff8a65", "#ba68c8",
                 "#4dd0e1", "#f06292", "#aed581", "#ffb74d", "#9575cd", "#e57373"]

PASOS = ["Pieza original", "Zona seleccionada", "Puntos de control",
         "Primeros segmentos", "Spline completo", "Reconstrucción digital",
         "Resultado final"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "mathtext.fontset": "dejavusans",
    "text.color": TEXTO,
    "axes.labelcolor": TENUE,
    "xtick.color": TENUE,
    "ytick.color": TENUE,
})


def suave(x):
    """Rampa suave 0->1 (smoothstep)."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def prog(t, t0, t1):
    return float(np.clip((t - t0) / (t1 - t0), 0.0, 1.0))


# ---------------------------------------------------------------------------
# Datos y vistas pre-calculadas
# ---------------------------------------------------------------------------
class Vista:
    """Recorte de la foto (en píxeles) re-escalado, con su 'extent' cartesiano."""

    def __init__(self, d, x0, x1, f0, f1, max_lado=760):
        alto = d["alto"]
        self.x0, self.x1, self.f0, self.f1 = x0, x1, f0, f1
        esc = max_lado / max(x1 - x0, f1 - f0)
        tam = (max(1, int((x1 - x0) * esc)), max(1, int((f1 - f0) * esc)))

        def rec(a, interp=cv2.INTER_AREA):
            return cv2.resize(a[f0:f1, x0:x1], tam, interpolation=interp)

        self.orig = cv2.cvtColor(rec(d["imagen"]), cv2.COLOR_BGR2RGB)
        self.reco = cv2.cvtColor(rec(d["reconstruida"]), cv2.COLOR_BGR2RGB)
        self.mrec = rec(d["mascara_rec"].astype(np.uint8) * 255, cv2.INTER_NEAREST) > 0
        self.mobj = rec(d["mascara"].astype(np.uint8) * 255, cv2.INTER_NEAREST) > 0
        yy, xx = np.mgrid[0:tam[1], 0:tam[0]]
        self.cx = x0 + xx / esc                    # coordenada x de cada píxel
        self.cy = alto - (f0 + yy / esc)           # coordenada y cartesiana
        self.extent = [x0, x1, alto - f1, alto - f0]

    def mezcla(self, p_rec, eje="x", invertir=False, zona=None):
        """Imagen con el relleno revelado progresivamente (0..1)."""
        if p_rec <= 0:
            return self.orig
        if p_rec >= 1:
            return self.reco
        c = self.cx if eje == "x" else self.cy
        m = self.mrec if zona is None else (self.mrec & zona)
        sel = m[m]
        vals = c[m]
        if vals.size == 0:
            return self.orig
        lo, hi = vals.min(), vals.max()
        u = (c - lo) / max(hi - lo, 1e-9)
        if invertir:
            u = 1 - u
        out = self.orig.copy()
        rev = m & (u <= p_rec)
        out[rev] = self.reco[rev]
        del sel
        return out


def preparar():
    d = construir_modelo()
    d["v_full"] = Vista(d, 0, d["ancho"], 0, d["alto"], max_lado=900)
    d["v_vasija"] = Vista(d, 220, 1536, 0, 1440, max_lado=900)
    d["v_A"] = Vista(d, 580, 960, 0, 400, max_lado=760)
    d["v_B"] = Vista(d, 230, 620, 620, 1160, max_lado=760)
    d["v_A_ancha"] = Vista(d, 560, 1300, 0, 420, max_lado=900)
    d["v_B_ancha"] = Vista(d, 230, 1536, 640, 1240, max_lado=900)
    return d


# ---------------------------------------------------------------------------
# Elementos gráficos comunes
# ---------------------------------------------------------------------------
PARTES = [
    (0, 25, "Parte 1 · Presentación de la pieza"),
    (25, 50, "Parte 2 · Obtención de los puntos"),
    (50, 90, "Parte 3 · Spline Cúbico: modelo y código"),
    (90, 130, "Parte 4 · Reconstrucción paso a paso"),
    (130, 158, "Parte 5 · Animación final"),
    (158, 180.1, "Parte 6 · Conclusión"),
]

# Línea de tiempo del video: (inicio, fin) en el video  ->  (inicio, fin) de la
# escena original.  La escena "codigo" (1:00-1:20) muestra el método aplicado
# en el código con los números reales.
LINEA_TIEMPO = [
    ((0, 50), (0, 50)),
    ((50, 60), (50, 62)),          # fórmulas
    ((60, 80), "codigo"),          # aplicación del método en el código
    ((80, 90), (62, 75)),          # continuidad
    ((90, 110), (75, 97)),         # zona A paso a paso
    ((110, 130), (97, 119)),       # zona B paso a paso
    ((130, 158), (120, 155)),      # animación final
    ((158, 180.1), (155, 180)),    # conclusión
]


def tiempo_escena(t):
    for (a, b), dest in LINEA_TIEMPO:
        if a <= t < b:
            if dest == "codigo":
                return None
            a2, b2 = dest
            return a2 + (t - a) * (b2 - a2) / (b - a)
    return 180.0


def mmss(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def cabecera(fig, t):
    for a, b, nombre in PARTES:
        if a <= t < b:
            break
    ax = fig.add_axes([0, 0.925, 1, 0.075])
    ax.set_axis_off()
    ax.add_patch(Rectangle((0, 0), 1, 1, color=PANEL, transform=ax.transAxes))
    ax.text(0.015, 0.5, nombre, va="center", fontsize=17, weight="bold", color=ACENTO)
    ax.text(0.985, 0.5, f"{mmss(a)} – {mmss(min(b, 180))}", va="center", ha="right",
            fontsize=12, color=TENUE)
    ax.text(0.62, 0.5, "Splines Cúbicos · Vasija de Tiwanaku", va="center", ha="center",
            fontsize=11, color=TENUE)


def paso_actual(t):
    if t < 16:
        return 1
    if t < 25:
        return 2
    if t < 50:
        return 3
    if t < 75:
        return 0          # modelo matemático
    for base in (75, 97):
        if base <= t < base + 22:
            r = t - base
            return 3 if r < 3 else 4 if r < 9 else 5 if r < 16 else 6
    return 7


def pie(fig, t):
    p = paso_actual(t)
    ax = fig.add_axes([0, 0, 1, 0.06])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(Rectangle((0, 0), 1, 1, color=PANEL))
    n = len(PASOS)
    for i, nombre in enumerate(PASOS, start=1):
        x = (i - 0.5) / n
        activo = i == p
        hecho = p == 7 and t >= 155 or (p != 0 and i < p) or (p == 0 and i <= 3)
        col = ACENTO if activo else ("#5d6b80" if hecho else "#3a404d")
        ax.add_patch(FancyBboxPatch((x - 0.065, 0.18), 0.13, 0.64,
                                    boxstyle="round,pad=0.005,rounding_size=0.02",
                                    color=col, alpha=0.95))
        ax.text(x, 0.5, f"{i}. {nombre}", ha="center", va="center", fontsize=8.6,
                color="#111" if activo else TEXTO, weight="bold" if activo else "normal")
    if p == 0:
        ax.text(0.5, 0.5, "", ha="center")


def panel_texto(fig, rect, lineas, alpha=1.0, tam=13.5, inter=0.075, titulo=None,
                fondo=True):
    ax = fig.add_axes(rect)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    if fondo:
        ax.add_patch(FancyBboxPatch((0.0, 0.0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                    color=PANEL, alpha=0.9 * alpha))
    y = 0.93
    if titulo:
        ax.text(0.04, y, titulo, fontsize=tam + 2, weight="bold", color=ACENTO, va="top",
                alpha=alpha)
        y -= inter * 1.5
    for ln in lineas:
        if isinstance(ln, tuple):
            txt, kw = ln
        else:
            txt, kw = ln, {}
        kw = dict(kw)
        sz = kw.pop("size", tam)
        ax.text(0.04, y, txt, fontsize=sz, va="top", alpha=alpha,
                color=kw.pop("color", TEXTO), **kw)
        y -= kw.get("salto", inter) if "salto" not in kw else 0
    return ax


def panel_codigo(fig, rect, titulo, codigo, alpha=1.0, tam=9.6):
    ax = fig.add_axes(rect)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                color="#0d0f14", alpha=alpha, ec="#3a404d"))
    ax.text(0.03, 0.95, titulo, fontsize=10, color=ACENTO, va="top", alpha=alpha,
            family="DejaVu Sans Mono", weight="bold")
    ax.text(0.03, 0.83, codigo, fontsize=tam, color="#c8e6c9", va="top", alpha=alpha,
            family="DejaVu Sans Mono", linespacing=1.35)


def mostrar(fig, rect, vista, img=None, alpha=1.0, fondo=None):
    ax = fig.add_axes(rect)
    ax.set_axis_off()
    if fondo is not None:
        ax.imshow(fondo, extent=vista.extent, interpolation="bilinear")
    ax.imshow(vista.orig if img is None else img, extent=vista.extent, alpha=alpha,
              interpolation="bilinear")
    ax.set_xlim(vista.extent[0], vista.extent[1])
    ax.set_ylim(vista.extent[2], vista.extent[3])
    ax.set_aspect("equal")
    return ax


def dibujar_puntos(ax, d, z, n_vis, etiquetas=True, tam=46, fs=9):
    P = d["puntos_" + z]
    tipos = d["tipos_" + z]
    for i in range(int(np.floor(n_vis))):
        c = COL_INT if tipos[i] == "intacto" else COL_SIM
        ax.scatter(P[i, 0], P[i, 1], s=tam, c=c, edgecolors="k", linewidths=1.0, zorder=10)
        if etiquetas:
            ax.text(P[i, 0], P[i, 1], f" P{i}", fontsize=fs, color=c, zorder=11,
                    va="bottom", ha="left", weight="bold",
                    bbox=dict(boxstyle="round,pad=0.1", fc="#000000", alpha=0.45, lw=0))


def dibujar_tramos(ax, d, z, avance, lw=3.2, colores=True, color=None, alpha=1.0):
    """Dibuja los tramos del spline; avance = nº de tramos (puede ser fraccionario)."""
    sp = d["spline_" + z]
    completos = int(np.floor(avance))
    for i in range(min(completos, sp.n)):
        x, y = sp.tramo(i)
        c = COLORES_TRAMO[i % len(COLORES_TRAMO)] if colores else color
        ax.plot(x, y, color=c, lw=lw, solid_capstyle="round", zorder=8, alpha=alpha)
    if completos < sp.n:
        f = avance - completos
        if f > 0:
            ts = np.linspace(sp.t[completos], sp.t[completos] + f * (sp.t[completos + 1] -
                                                                      sp.t[completos]), 60)
            x, y = sp.Sx(ts, tramo=completos), sp.Sy(ts, tramo=completos)
            c = COLORES_TRAMO[completos % len(COLORES_TRAMO)] if colores else color
            ax.plot(x, y, color=c, lw=lw, solid_capstyle="round", zorder=8, alpha=alpha)
            ax.scatter(x[-1], y[-1], s=60, c=c, zorder=12, edgecolors="white")


def dibujar_curva(ax, d, z, frac=1.0, color=None, lw=3, alpha=1.0, ls="-"):
    sp = d["spline_" + z]
    X, Y, _ = sp.curva(80)
    k = max(2, int(len(X) * frac))
    ax.plot(X[:k], Y[:k], color=color or (COL_A if z == "A" else COL_B), lw=lw,
            alpha=alpha, ls=ls, zorder=8, solid_capstyle="round")


def fmt(v):
    return f"{v:+.3g}".replace("e-0", "e-").replace("e+0", "e+")


# ---------------------------------------------------------------------------
# Escenas
# ---------------------------------------------------------------------------
def escena_titulo(fig, d, t):
    a = suave(prog(t, 0, 1.2)) * (1 - suave(prog(t, 6.3, 7)))
    v = d["v_full"]
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.add_patch(Rectangle((0, 0), 1, 1, color=FONDO, transform=ax.transAxes))
    mostrar(fig, [0.60, 0.06, 0.38, 0.88], v, alpha=0.9 * a)
    ax2 = fig.add_axes([0.04, 0.1, 0.56, 0.8])
    ax2.set_axis_off()
    ax2.text(0, 0.86, "DESAFÍO FINAL · MÉTODOS NUMÉRICOS", fontsize=13, color=ACENTO,
             alpha=a, weight="bold")
    ax2.text(0, 0.78, "Reconstrucción Digital\nde Piezas Arqueológicas\nmediante Splines Cúbicos",
             fontsize=27, weight="bold", va="top", alpha=a, linespacing=1.15)
    ax2.text(0, 0.40, "Pieza: vasija cerámica de Tiwanaku (Bolivia)\n"
             "Zonas a reconstruir: borde superior y oreja lateral",
             fontsize=14, color=TENUE, va="top", alpha=a, linespacing=1.5)
    ax2.text(0, 0.17, f"Estudiante: {ESTUDIANTE}", fontsize=14, alpha=a)
    ax2.text(0, 0.09, "Pieza arqueológica → Puntos de control → Spline Cúbico → "
             "Reconstrucción → Animación", fontsize=10.5, color=ACENTO, alpha=a)


def escena_pieza(fig, d, t):
    a = suave(prog(t, 7, 8))
    v = d["v_full"]
    mostrar(fig, [0.03, 0.075, 0.42, 0.84], v, alpha=a)
    lineas = [
        ("Tipo:  vasija / cántaro cerámico de cuerpo globular,", {}),
        ("          cuello alto, labio evertido y orejas laterales.", {"color": TENUE}),
        ("Cultura:  Tiwanaku (altiplano de Bolivia).", {}),
        ("Estado:  restaurada a partir de muchos fragmentos;", {}),
        ("          quedan zonas incompletas en su contorno.", {"color": TENUE}),
        ("", {}),
        ("Fuente de la fotografía:", {"color": ACENTO, "weight": "bold"}),
        ("La Región (laregion.bo) — \"Cinco avances de investigación", {"size": 11.5}),
        ("sobre hallazgos en Tiwanaku que podrían cambiar la historia\"", {"size": 11.5}),
        ("laregion.bo/cinco-avances-de-investigacion-sobre-hallazgos-", {"size": 10, "color": TENUE}),
        ("en-tiwanaku-que-podrian-cambiar-la-historia/", {"size": 10, "color": TENUE}),
        ("", {}),
        (f"Imagen digital: {d['ancho']} × {d['alto']} píxeles", {"color": TENUE}),
    ]
    panel_texto(fig, [0.49, 0.1, 0.48, 0.78], lineas, alpha=a, titulo="1. Pieza original",
                inter=0.062, tam=13.5)


def rect_zona(ax, x0, x1, f0, f1, alto, color, alpha, texto):
    ax.add_patch(Rectangle((x0, alto - f1), x1 - x0, f1 - f0, fill=False, ec=color,
                           lw=3, alpha=alpha, ls="--", zorder=9))
    ax.text(x0 - 15, alto - (f0 + f1) / 2, texto, color=color, fontsize=12, weight="bold",
            alpha=alpha, va="center", ha="right", zorder=10,
            bbox=dict(boxstyle="round,pad=0.2", fc="#000", alpha=0.6 * alpha, lw=0))


def escena_zonas(fig, d, t):
    v = d["v_full"]
    ax = mostrar(fig, [0.03, 0.075, 0.42, 0.84], v)
    pulso = 0.65 + 0.35 * np.sin(2 * np.pi * (t - 16) / 1.6)
    a1 = suave(prog(t, 16, 17)) * pulso
    a2 = suave(prog(t, 18, 19)) * pulso
    rect_zona(ax, 590, 830, 20, 380, d["alto"], COL_A, a1, "Zona A")
    rect_zona(ax, 250, 560, 680, 1150, d["alto"], COL_B, a2, "Zona B")
    a = suave(prog(t, 16, 17))
    lineas = [
        ("Zona A — Borde superior (labio) izquierdo", {"color": COL_A, "weight": "bold"}),
        ("  falta un tramo del labio entre el fragmento", {}),
        ("  izquierdo y el cuello (fractura).", {}),
        ("Zona B — Oreja izquierda de la parte media", {"color": COL_B, "weight": "bold"}),
        ("  solo quedan sus restos: unión (y≈1290) y muñón (y≈1000).", {}),
        ("", {}),
        ("¿Por qué estas zonas?", {"color": ACENTO, "weight": "bold"}),
        ("• La vasija es un sólido de revolución: su perfil", {}),
        ("  es simétrico respecto a un eje vertical.", {}),
        ("• El labio derecho y la oreja derecha están intactos", {}),
        ("  → sirven de guía para los puntos faltantes.", {}),
        ("• Son curvas suaves y verticales: ideales para", {}),
        ("  un Spline Cúbico PARAMÉTRICO.", {}),
    ]
    panel_texto(fig, [0.49, 0.1, 0.48, 0.78], lineas, alpha=a, titulo="2. Zona seleccionada",
                inter=0.066, tam=13)


COD_PUNTOS = """mask = segmentar(img)        # HSV: tono rojizo y saturado
contorno = cv2.findContours(mask, ...)
eje = mean((borde_izq + borde_der) / 2)
# punto intacto: leído del contorno
P = (borde_izq(mask, fila), alto - fila)
# punto guía por simetría
P = (2*eje - borde_der(mask, fila), alto - fila)"""


def escena_contorno(fig, d, t):
    v = d["v_vasija"]
    ax = mostrar(fig, [0.02, 0.075, 0.46, 0.84], v)
    c = d["contorno"]
    alto = d["alto"]
    f = suave(prog(t, 25.5, 30))
    k = max(2, int(len(c) * f))
    ax.plot(c[:k, 0], alto - c[:k, 1], color="#69f0ae", lw=1.6, zorder=6)
    a_eje = suave(prog(t, 29, 30.5))
    for eje, f0, f1, nom in ((d["eje_borde"], 0, 450, "eje labio"),
                             (d["eje_cuerpo"], 450, 1440, "eje cuerpo")):
        ax.plot([eje, eje], [alto - f1, alto - f0], ls="--", color=ACENTO, lw=2, alpha=a_eje)
        ax.text(eje + 10, alto - f0 - 30, f"{nom}\nx = {eje:.1f}", color=ACENTO, fontsize=9,
                alpha=a_eje, va="top")
    a = suave(prog(t, 25, 26))
    lineas = [
        ("1) Segmentación por color (HSV, OpenCV)", {}),
        (f"    → contorno completo: {len(c)} coordenadas (x, y)", {"color": TENUE}),
        ("2) Sistema cartesiano en píxeles:", {}),
        ("    X = columna,   Y = 2048 − fila", {"color": TENUE}),
        ("3) Eje de simetría = punto medio de los bordes", {}),
        (f"    labio: x = {d['eje_borde']:.1f}    cuerpo: x = {d['eje_cuerpo']:.1f}",
         {"color": TENUE}),
        ("4) Puntos guía por simetría:  x' = 2·x_eje − x", {}),
    ]
    panel_texto(fig, [0.51, 0.47, 0.47, 0.44], lineas, alpha=a,
                titulo="3. Obtención de coordenadas", inter=0.11, tam=12.5)
    panel_codigo(fig, [0.51, 0.09, 0.47, 0.35], "extraer_puntos.py  (carga de puntos)",
                 COD_PUNTOS, alpha=suave(prog(t, 27, 28)))


def tabla_puntos(fig, rect, d, z, n_vis, alpha=1.0):
    ax = fig.add_axes(rect)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                color=PANEL, alpha=alpha))
    col = COL_A if z == "A" else COL_B
    nom = "Zona A · borde" if z == "A" else "Zona B · oreja"
    ax.text(0.5, 0.965, f"Coordenadas — {nom}", ha="center", va="top", fontsize=11.5,
            color=col, weight="bold", alpha=alpha)
    ax.text(0.08, 0.89, " i      x        y      tipo", fontsize=10.2, va="top",
            family="DejaVu Sans Mono", color=ACENTO, alpha=alpha)
    P = d["puntos_" + z]
    tipos = d["tipos_" + z]
    dy = 0.82 / max(len(P), 1)
    for i in range(len(P)):
        if i >= n_vis:
            break
        c = COL_INT if tipos[i] == "intacto" else COL_SIM
        ax.text(0.08, 0.84 - i * dy, f"P{i:<3d} {P[i,0]:5.0f}   {P[i,1]:6.0f}   {tipos[i]}",
                fontsize=10.2, va="top", family="DejaVu Sans Mono", color=c, alpha=alpha)


def grafico_puntos(fig, rect, d, z, n_vis, alpha=1.0, con_spline=0.0):
    ax = fig.add_axes(rect)
    ax.set_facecolor("#0d0f14")
    P = d["puntos_" + z]
    tipos = d["tipos_" + z]
    k = int(n_vis)
    cols = [COL_INT if tp == "intacto" else COL_SIM for tp in tipos[:k]]
    ax.scatter(P[:k, 0], P[:k, 1], c=cols, s=28, edgecolors="k", zorder=5, alpha=alpha)
    if k >= 2:
        ax.plot(P[:k, 0], P[:k, 1], ":", color=TENUE, lw=0.8, alpha=alpha)
    if con_spline > 0:
        dibujar_curva(ax, d, z, frac=con_spline, lw=2)
    pad = 25
    ax.set_xlim(P[:, 0].min() - pad, P[:, 0].max() + pad)
    ax.set_ylim(P[:, 1].min() - pad, P[:, 1].max() + pad)
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(color="#2a2f3a", lw=0.6)
    ax.tick_params(labelsize=8)
    ax.set_xlabel("x (px)", fontsize=9)
    ax.set_ylabel("y (px)", fontsize=9)
    ax.set_title("Gráfico de los puntos", fontsize=10.5, color=TEXTO)
    for s in ax.spines.values():
        s.set_color("#3a404d")
    return ax


def escena_puntos(fig, d, t, z, t0, t1):
    v = d["v_A_ancha"] if z == "A" else d["v_B_ancha"]
    P = d["puntos_" + z]
    tipos = d["tipos_" + z]
    n = len(P)
    n_vis = 1 + (n - 1) * prog(t, t0 + 0.5, t1 - 3)
    ax = mostrar(fig, [0.01, 0.075, 0.52, 0.84], v)
    eje = d["eje_borde"] if z == "A" else d["eje_cuerpo"]
    ax.plot([eje, eje], [v.extent[2], v.extent[3]], ls="--", color=ACENTO, lw=1.5, alpha=0.8)
    # líneas de reflexión para los puntos guía
    origenes = iter(d["origen_" + z])
    for i in range(len(P)):
        if tipos[i] == "simetria":
            xs, ys = next(origenes)
            if i < int(n_vis):
                ax.plot([xs, P[i, 0]], [ys, P[i, 1]], ls=":", color=COL_SIM, lw=1.2)
                ax.scatter(xs, ys, s=22, marker="s", c=COL_SIM, zorder=9)
    dibujar_puntos(ax, d, z, n_vis, fs=8, tam=38)
    ax.text(v.extent[0] + 10, v.extent[2] + 10,
            "● intacto (medido)     ● simetría (reflejado del lado derecho ■)",
            fontsize=9, color=TEXTO, va="bottom",
            bbox=dict(boxstyle="round", fc="#000", alpha=0.6, lw=0))
    tabla_puntos(fig, [0.545, 0.075, 0.23, 0.84], d, z, n_vis)
    grafico_puntos(fig, [0.815, 0.3, 0.17, 0.55], d, z, n_vis)
    ax2 = fig.add_axes([0.79, 0.08, 0.2, 0.18])
    ax2.set_axis_off()
    ax2.text(0, 0.9, f"{n} puntos de control", fontsize=12, weight="bold",
             color=COL_A if z == "A" else COL_B, va="top")
    ni = sum(1 for tp in tipos if tp == "intacto")
    ax2.text(0, 0.55, f"{ni} intactos + {n - ni} por simetría", fontsize=10.5, va="top")
    ax2.text(0, 0.25, "Fuente: fotografía (laregion.bo)", fontsize=9, color=TENUE, va="top")


def escena_formulas(fig, d, t):
    a = suave(prog(t, 50, 51))
    ax = fig.add_axes([0.02, 0.08, 0.55, 0.83])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                color=PANEL))
    ax.text(0.03, 0.96, "Spline Cúbico PARAMÉTRICO (natural)", fontsize=16, weight="bold",
            color=ACENTO, va="top", alpha=a)
    ax.text(0.03, 0.87, "¿Por qué paramétrico? El labio y la oreja tienen tramos verticales\n"
            "y se repliegan: x no es creciente ⇒ y(x) no es una función.",
            fontsize=11.5, va="top", color=TENUE, alpha=a, linespacing=1.4)
    a2 = suave(prog(t, 51.5, 52.5))
    ax.text(0.03, 0.72, r"$X_i(t)=a_{x,i}+b_{x,i}(t-t_i)+c_{x,i}(t-t_i)^2+d_{x,i}(t-t_i)^3$",
            fontsize=15.5, alpha=a2, color=COL_A)
    ax.text(0.03, 0.635, r"$Y_i(t)=a_{y,i}+b_{y,i}(t-t_i)+c_{y,i}(t-t_i)^2+d_{y,i}(t-t_i)^3$",
            fontsize=15.5, alpha=a2, color=COL_B)
    ax.text(0.03, 0.56, r"$t\in[t_i,\,t_{i+1}],\quad i=0,1,\ldots,n-1$", fontsize=13, alpha=a2)
    a3 = suave(prog(t, 54, 55))
    ax.text(0.03, 0.47, "Parámetro t = longitud de cuerda acumulada:", fontsize=12.5,
            alpha=a3, va="top")
    ax.text(0.03, 0.40, r"$t_0=0,\qquad t_{i+1}=t_i+\sqrt{(x_{i+1}-x_i)^2+(y_{i+1}-y_i)^2}$",
            fontsize=13.5, alpha=a3, va="top")
    a4 = suave(prog(t, 56.5, 57.5))
    ax.text(0.03, 0.29, "Unión por intervalos: cada par de puntos consecutivos (P_i, P_{i+1})\n"
            "tiene su propio polinomio cúbico → n tramos, 4n coeficientes por coordenada.",
            fontsize=11.5, alpha=a4, va="top", linespacing=1.4)
    ax.text(0.03, 0.15, r"$h_{i-1}c_{i-1}+2(h_{i-1}+h_i)c_i+h_ic_{i+1}="
            r"\frac{3}{h_i}(a_{i+1}-a_i)-\frac{3}{h_{i-1}}(a_i-a_{i-1})$",
            fontsize=13, alpha=a4, va="top")
    ax.text(0.03, 0.05, "Sistema tridiagonal → algoritmo de Thomas;  luego "
            r"$b_i,\ d_i$" " a partir de " r"$c_i$", fontsize=11, alpha=a4, color=TENUE)

    # Gráfico X(t), Y(t) de la zona A
    a5 = suave(prog(t, 52, 53))
    sp = d["spline_A"]
    for k, (rect, S, nom, col) in enumerate((([0.62, 0.55, 0.36, 0.33], sp.Sx, "X(t)", COL_A),
                                             ([0.62, 0.12, 0.36, 0.33], sp.Sy, "Y(t)", COL_B))):
        axg = fig.add_axes(rect)
        axg.set_facecolor("#0d0f14")
        frac = prog(t, 53 + k * 0.5, 58)
        for i in range(sp.n):
            if i / sp.n > frac:
                break
            ts = np.linspace(sp.t[i], sp.t[i + 1], 40)
            axg.plot(ts, S(ts, tramo=i), color=COLORES_TRAMO[i % 11], lw=2.4, alpha=a5)
        axg.scatter(sp.t, S.a.tolist() + [S(np.array([sp.t[-1]]))[0]], s=18, c="w",
                    zorder=5, alpha=a5)
        axg.set_title(f"Zona A: {nom} por tramos (cada color = un polinomio cúbico)",
                      fontsize=9.5, color=TEXTO, alpha=a5)
        axg.set_xlabel("t", fontsize=9)
        axg.tick_params(labelsize=8)
        axg.grid(color="#2a2f3a", lw=0.6)
        for s in axg.spines.values():
            s.set_color("#3a404d")


COD_SPLINE = """for i in range(1, n):          # sistema tridiagonal
    sub[i]  = h[i-1]
    diag[i] = 2*(h[i-1] + h[i])
    sup[i]  = h[i]
    rhs[i]  = 3*((a[i+1]-a[i])/h[i] - (a[i]-a[i-1])/h[i-1])
c = resolver_tridiagonal(sub, diag, sup, rhs)  # c0=cn=0
b[i] = (a[i+1]-a[i])/h[i] - h[i]*(2*c[i]+c[i+1])/3
d[i] = (c[i+1]-c[i]) / (3*h[i])"""


def escena_continuidad(fig, d, t):
    a = suave(prog(t, 62, 63))
    lineas = [
        (r"$C^0$:  $S_i(t_{i+1}) = S_{i+1}(t_{i+1})$", {"size": 14}),
        ("        la curva no tiene saltos (tramos unidos)", {"color": TENUE, "size": 11.5}),
        (r"$C^1$:  $S_i'(t_{i+1}) = S_{i+1}'(t_{i+1})$", {"size": 14}),
        ("        misma pendiente: sin picos ni esquinas", {"color": TENUE, "size": 11.5}),
        (r"$C^2$:  $S_i''(t_{i+1}) = S_{i+1}''(t_{i+1})$", {"size": 14}),
        ("        misma curvatura: transición suave", {"color": TENUE, "size": 11.5}),
        (r"Natural:  $S''(t_0)=S''(t_n)=0$", {"size": 14}),
        ("        cierra el sistema (4n ecuaciones = 4n incógnitas)", {"color": TENUE,
                                                                       "size": 11.5}),
    ]
    panel_texto(fig, [0.02, 0.43, 0.47, 0.48], lineas, alpha=a,
                titulo="Continuidad en los nodos", inter=0.098, tam=13)
    # verificación numérica
    a2 = suave(prog(t, 66, 67))
    ax = fig.add_axes([0.02, 0.08, 0.47, 0.32])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                color=PANEL, alpha=a2))
    ax.text(0.04, 0.88, "Verificación numérica (máximo salto en los nodos)", fontsize=12,
            color=ACENTO, weight="bold", va="top", alpha=a2)
    ax.text(0.04, 0.68, "Zona     tramos     C0          C1          C2       vs scipy",
            fontsize=10, family="DejaVu Sans Mono", va="top", alpha=a2, color=TENUE)
    for k, z in enumerate("AB"):
        c0, c1, c2 = d["continuidad_" + z]
        ax.text(0.04, 0.5 - k * 0.17,
                f"  {z}        {d['spline_' + z].n:2d}    {c0:.1e}   {c1:.1e}   {c2:.1e}   "
                f"{d['scipy_' + z]:.1e}",
                fontsize=10, family="DejaVu Sans Mono", va="top", alpha=a2,
                color=COL_A if z == "A" else COL_B)
    ax.text(0.04, 0.12, "≈ 0 (error de redondeo) ⇒ curva continua y suave C², igual a scipy",
            fontsize=10.5, va="top", alpha=a2)

    # zoom de un nodo
    a3 = suave(prog(t, 63, 64))
    axz = fig.add_axes([0.53, 0.48, 0.45, 0.39])
    axz.set_facecolor("#0d0f14")
    sp = d["spline_B"]
    k = 4
    for i, col in ((k - 1, COLORES_TRAMO[0]), (k, COLORES_TRAMO[1])):
        x, y = sp.tramo(i, 80)
        axz.plot(x, y, color=col, lw=4, alpha=a3, label=f"tramo S{i}")
    tk = sp.t[k]
    px, py = sp(np.array([tk]))
    dx, dy = sp(np.array([tk]), 1)
    nn = np.hypot(dx, dy)[0]
    L = 40
    f_tg = suave(prog(t, 64, 65))
    axz.plot([px[0] - L * dx[0] / nn, px[0] + L * dx[0] / nn],
             [py[0] - L * dy[0] / nn, py[0] + L * dy[0] / nn], "--", color="w", lw=1.5,
             alpha=f_tg, label="tangente común (C¹)")
    axz.scatter(px, py, s=80, c=ACENTO, zorder=5, alpha=a3, label=f"nodo P{k}")
    R = 30
    axz.set_xlim(px[0] - 2.2 * R, px[0] + 2.2 * R)
    axz.set_ylim(py[0] - R, py[0] + R)
    axz.set_aspect("equal", adjustable="box")
    axz.grid(color="#2a2f3a", lw=0.6)
    axz.legend(loc="upper left", fontsize=8.5, facecolor=PANEL, labelcolor=TEXTO,
               edgecolor="#3a404d")
    axz.set_title("Zona B: unión de dos tramos en un nodo", fontsize=10.5, color=TEXTO)
    axz.tick_params(labelsize=8)
    for s in axz.spines.values():
        s.set_color("#3a404d")
    panel_codigo(fig, [0.53, 0.08, 0.45, 0.36], "spline_cubico.py  (cálculo del spline)",
                 COD_SPLINE, alpha=suave(prog(t, 68, 69)), tam=8.6)


COD_CURVA = """sp = SplineParametrico(P)           # P: puntos (x, y)
for i in range(sp.n):                 # tramo a tramo
    ts = linspace(sp.t[i], sp.t[i+1], 60)
    X, Y = sp.Sx(ts, tramo=i), sp.Sy(ts, tramo=i)
    plot(X, Y)
# relleno: polígono (spline + fractura) con textura simétrica"""


def escena_reconstruccion(fig, d, t, z, base):
    """Parte 4 para una zona: puntos -> 1er tramo -> tramos -> spline -> relleno."""
    r = t - base
    v = d["v_" + z]
    sp = d["spline_" + z]
    col = COL_A if z == "A" else COL_B
    p_rec = suave(prog(r, 16.3, 21.3))
    if z == "A":
        img = v.mezcla(p_rec, eje="y", invertir=True)
    else:
        img = v.mezcla(p_rec, eje="y", invertir=True)
    rect_img = [0.02, 0.075, 0.44, 0.84]
    ax = mostrar(fig, rect_img, v, img=img, alpha=1.0)
    # oscurecer foto durante la construcción de la curva
    oscuro = 0.45 * (1 - suave(prog(r, 15, 16.5)))
    ax.add_patch(Rectangle((v.extent[0], v.extent[2]), v.extent[1] - v.extent[0],
                           v.extent[3] - v.extent[2], color="black", alpha=oscuro, zorder=3))
    # avance de tramos
    if r < 3:
        avance = 0.0
    elif r < 9:
        avance = suave(prog(r, 3.3, 8.5))
    elif r < 16:
        avance = 1 + (sp.n - 1) * prog(r, 9, 15.5)
    else:
        avance = sp.n
    a_tramos = 1 - 0.6 * suave(prog(r, 18, 21))
    dibujar_tramos(ax, d, z, avance, lw=3.4, alpha=a_tramos)
    dibujar_puntos(ax, d, z, len(sp.P), etiquetas=r < 18, tam=42, fs=8)

    # panel derecho: paso + coeficientes
    paso = paso_actual(t)
    textos = {
        3: ("3. Puntos de control", "Se cargan los puntos P0…Pn de la zona."),
        4: ("4. Primer segmento", "Se calcula y traza el primer polinomio cúbico S0."),
        5: ("5. Unión de segmentos", "Se añaden los tramos S1, S2, … hasta el spline completo."),
        6: ("6. Reconstrucción digital",
            "Se rellena el área encerrada por el spline y la fractura\n"
            "con la textura del lado simétrico intacto."),
    }
    tit, desc = textos.get(paso, ("", ""))
    nombre = "Zona A · borde superior" if z == "A" else "Zona B · oreja lateral"
    axp = fig.add_axes([0.49, 0.56, 0.49, 0.35])
    axp.set_axis_off()
    axp.set_xlim(0, 1)
    axp.set_ylim(0, 1)
    axp.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                 color=PANEL))
    axp.text(0.04, 0.9, nombre, fontsize=12, color=col, weight="bold", va="top")
    axp.text(0.04, 0.72, tit, fontsize=17, weight="bold", color=ACENTO, va="top")
    axp.text(0.04, 0.5, desc, fontsize=12, va="top", linespacing=1.4)
    if paso >= 5:
        k_act = min(int(np.floor(avance)), sp.n)
        axp.text(0.04, 0.17, f"Tramos dibujados: {k_act} / {sp.n}" +
                 ("   ✔ spline completo (C², natural)" if k_act == sp.n else ""),
                 fontsize=11.5, va="top", color=TENUE)
    elif paso == 3:
        axp.text(0.04, 0.17, f"{len(sp.P)} puntos  →  {sp.n} tramos cúbicos", fontsize=11.5,
                 va="top", color=TENUE)

    # coeficientes del tramo actual
    i = int(min(max(np.floor(avance) - (1 if avance >= sp.n else 0), 0), sp.n - 1))
    if r < 9:
        i = 0
    if r >= 3 and r < 16:
        c = sp.coeficientes()[i]
        _, ti, ti1, ax_, bx, cx, dx, ay, by, cy, dy = c
        axc = fig.add_axes([0.49, 0.08, 0.49, 0.45])
        axc.set_axis_off()
        axc.set_xlim(0, 1)
        axc.set_ylim(0, 1)
        axc.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                     color="#0d0f14", ec="#3a404d"))
        colt = COLORES_TRAMO[i % 11]
        axc.text(0.04, 0.92, f"Tramo S{i}:   t ∈ [{ti:.1f}, {ti1:.1f}]   (P{i} → P{i+1})",
                 fontsize=12.5, color=colt, weight="bold", va="top")
        axc.text(0.04, 0.72,
                 rf"$X_{{{i}}}(t)={ax_:.1f}{fmt(bx)}\,u{fmt(cx)}\,u^2{fmt(dx)}\,u^3$",
                 fontsize=13.5, va="top")
        axc.text(0.04, 0.54,
                 rf"$Y_{{{i}}}(t)={ay:.1f}{fmt(by)}\,u{fmt(cy)}\,u^2{fmt(dy)}\,u^3$",
                 fontsize=13.5, va="top")
        axc.text(0.04, 0.37, rf"$u = t - t_{{{i}}}$", fontsize=12, va="top", color=TENUE)
        axc.text(0.04, 0.2, "Coeficientes calculados por el programa (sistema tridiagonal).",
                 fontsize=10.5, va="top", color=TENUE)
    elif r >= 16:
        panel_codigo(fig, [0.49, 0.08, 0.49, 0.45], "reconstruccion.py  (generación de la curva)",
                     COD_CURVA, tam=9.4)
    else:
        grafico_puntos(fig, [0.55, 0.1, 0.4, 0.4], d, z, len(sp.P))


COD_ANIM = """for t in frames:                    # 24 cuadros/s
    dibujar_tramos(ax, d, zona, avance(t))
    img = vista.mezcla(p_relleno(t))  # relleno progresivo
    escribir_cuadro(fig)              # -> ffmpeg (MP4)"""


def escena_final(fig, d, t):
    v = d["v_vasija"]
    if t < 130:
        # original -> superposición progresiva de las curvas
        ax = mostrar(fig, [0.02, 0.075, 0.5, 0.84], v)
        f = suave(prog(t, 120.5, 127))
        dibujar_curva(ax, d, "A", frac=f, lw=3)
        dibujar_curva(ax, d, "B", frac=f, lw=3)
        lineas = [("Pieza original", {"size": 16, "weight": "bold", "color": ACENTO}),
                  ("", {}),
                  ("Superposición de los splines cúbicos", {}),
                  ("calculados sobre la fotografía real.", {}),
                  ("", {}),
                  ("── Zona A: borde superior", {"color": COL_A}),
                  ("── Zona B: oreja lateral", {"color": COL_B})]
        panel_texto(fig, [0.55, 0.45, 0.43, 0.46], lineas, inter=0.1, tam=13)
        panel_codigo(fig, [0.55, 0.08, 0.43, 0.32], "generar_video.py  (animación)", COD_ANIM,
                     tam=9.2)
    elif t < 140:
        p = suave(prog(t, 130.5, 137))
        img = v.mezcla(p, eje="y", invertir=True)
        ax = mostrar(fig, [0.02, 0.075, 0.5, 0.84], v, img=img)
        dibujar_curva(ax, d, "A", lw=2.5, alpha=1 - 0.7 * p)
        dibujar_curva(ax, d, "B", lw=2.5, alpha=1 - 0.7 * p)
        lineas = [("Reconstrucción", {"size": 16, "weight": "bold", "color": ACENTO}),
                  ("", {}),
                  ("Relleno progresivo del material faltante", {}),
                  ("dentro de las curvas del spline.", {}),
                  ("", {}),
                  (f"Progreso: {100 * p:3.0f} %", {"color": TENUE})]
        panel_texto(fig, [0.55, 0.3, 0.43, 0.6], lineas, inter=0.1, tam=13)
    else:
        # comparación lado a lado
        a = suave(prog(t, 140, 141))
        ax1 = mostrar(fig, [0.01, 0.12, 0.33, 0.74], v)
        ax2 = mostrar(fig, [0.345, 0.12, 0.33, 0.74], v, img=v.reco, alpha=a)
        if t > 146:
            dibujar_curva(ax2, d, "A", lw=1.6, alpha=0.8 * suave(prog(t, 146, 147)), ls="--")
            dibujar_curva(ax2, d, "B", lw=1.6, alpha=0.8 * suave(prog(t, 146, 147)), ls="--")
        ax0 = fig.add_axes([0, 0.86, 0.68, 0.06])
        ax0.set_axis_off()
        ax0.text(0.25, 0.5, "ANTES (original)", ha="center", fontsize=14, weight="bold")
        ax0.text(0.75, 0.5, "DESPUÉS (reconstruida)", ha="center", fontsize=14,
                 weight="bold", color=ACENTO, alpha=a)
        # detalles
        vA, vB = d["v_A"], d["v_B"]
        mostrar(fig, [0.69, 0.5, 0.15, 0.36], vA, img=vA.orig)
        mostrar(fig, [0.84, 0.5, 0.15, 0.36], vA, img=vA.reco)
        mostrar(fig, [0.69, 0.1, 0.15, 0.36], vB, img=vB.orig)
        mostrar(fig, [0.84, 0.1, 0.15, 0.36], vB, img=vB.reco)
        axl = fig.add_axes([0.69, 0.86, 0.3, 0.06])
        axl.set_axis_off()
        axl.text(0.25, 0.5, "antes", ha="center", fontsize=11, color=TENUE)
        axl.text(0.75, 0.5, "después", ha="center", fontsize=11, color=ACENTO)
        axl2 = fig.add_axes([0.69, 0.065, 0.3, 0.04])
        axl2.set_axis_off()
        axl2.text(0.5, 0.5, "Detalle: Zona A (arriba) · Zona B (abajo)", ha="center",
                  fontsize=10, color=TENUE)


def escena_conclusion(fig, d, t):
    a = suave(prog(t, 155, 156))
    v = d["v_vasija"]
    mostrar(fig, [0.66, 0.08, 0.33, 0.83], v, img=v.reco, alpha=a)
    secciones = [
        ("¿Qué se reconstruyó?", COL_A,
         "El tramo faltante del labio superior izquierdo (12 puntos, 11 tramos)\n"
         "y la oreja izquierda de la parte media, entre y ≈ 1000 y 1300 (10 puntos, 9 tramos)."),
        ("Utilidad de los Splines Cúbicos", ACENTO,
         "Curvas suaves (C²) que pasan exactamente por los puntos medidos,\n"
         "sin las oscilaciones de un polinomio único de grado alto."),
        ("Limitación encontrada", COL_B,
         "La foto es 2D y con perspectiva; la oreja derecha está cortada por el\n"
         "encuadre y la forma faltante depende de suponer simetría."),
        ("Aplicación futura", "#81c784",
         "Girar el perfil (sólido de revolución) para un modelo 3D, imprimir\n"
         "piezas de reposición y catalogar digitalmente keros y vasijas."),
    ]
    for k, (tit, col, txt) in enumerate(secciones):
        ak = suave(prog(t, 156 + k * 3.5, 157 + k * 3.5))
        y0 = 0.73 - k * 0.205
        ax = fig.add_axes([0.02, y0, 0.62, 0.185])
        ax.set_axis_off()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.03",
                                    color=PANEL, alpha=ak))
        ax.add_patch(Rectangle((0, 0), 0.008, 1, color=col, alpha=ak))
        ax.text(0.03, 0.85, tit, fontsize=14, weight="bold", color=col, va="top", alpha=ak)
        ax.text(0.03, 0.52, txt, fontsize=11.5, va="top", alpha=ak, linespacing=1.4)
    af = suave(prog(t, 172, 173))
    ax = fig.add_axes([0.02, 0.07, 0.62, 0.05])
    ax.set_axis_off()
    ax.text(0, 0.5, "Pieza → Puntos → Spline Cúbico → Reconstrucción → Animación  ✔",
            fontsize=12, color=ACENTO, alpha=af, va="center", weight="bold")


# ---------------------------------------------------------------------------
CODIGO_METODO = [
    "t = [0] + cumsum(norm(P[i+1] - P[i]))   # parámetro t",
    "a = x.copy()                            # a_i = x_i",
    "h = diff(t)                             # h_i = t_i+1 - t_i",
    "for i in range(1, n):                   # sistema tridiagonal",
    "    sub[i]  = h[i-1]",
    "    diag[i] = 2*(h[i-1] + h[i])",
    "    sup[i]  = h[i]",
    "    rhs[i]  = 3*((a[i+1]-a[i])/h[i] - (a[i]-a[i-1])/h[i-1])",
    "diag[0] = diag[n] = 1;  rhs[0] = rhs[n] = 0   # natural",
    "c = resolver_tridiagonal(sub, diag, sup, rhs) # Thomas",
    "for i in range(n):",
    "    b[i] = (a[i+1]-a[i])/h[i] - h[i]*(2*c[i]+c[i+1])/3",
    "    d[i] = (c[i+1]-c[i]) / (3*h[i])",
    "X(t) = a[i] + b[i]*u + c[i]*u**2 + d[i]*u**3   # u = t - t_i",
]
# (segundo de inicio, líneas resaltadas, etapa)
ETAPAS_CODIGO = [
    (0, (0, 1), "Datos: parámetro t y a_i = x_i"),
    (3, (2, 2), "Paso 1: amplitudes h_i de cada intervalo"),
    (6, (3, 8), "Paso 2: se arma el sistema tridiagonal A·c = r"),
    (11, (9, 9), "Paso 3: se resuelve con el algoritmo de Thomas → c_i"),
    (14, (10, 12), "Paso 4: se obtienen b_i y d_i de cada tramo"),
    (17, (13, 13), "Paso 5: se evalúa el spline y se dibuja la curva"),
]


def datos_metodo(sp):
    """Recalcula (para mostrar) todos los valores intermedios del método para X(t)."""
    S = sp.Sx
    t = sp.t
    x = sp.P[:, 0]
    n = len(t) - 1
    h = np.diff(t)
    A = np.zeros((n + 1, n + 1))
    r = np.zeros(n + 1)
    A[0, 0] = A[n, n] = 1
    for i in range(1, n):
        A[i, i - 1] = h[i - 1]
        A[i, i] = 2 * (h[i - 1] + h[i])
        A[i, i + 1] = h[i]
        r[i] = 3 * ((x[i + 1] - x[i]) / h[i] - (x[i] - x[i - 1]) / h[i - 1])
    c = np.concatenate([S.c, [0.0]])
    return t, x, h, A, r, c, S.b, S.d


def escena_codigo(fig, d, r):
    """Parte 3b: el método de splines cúbicos aplicado en el código, paso a paso,
    con los valores numéricos reales de la Zona B (coordenada X)."""
    sp = d["spline_B"]
    t, x, h, A, rhs, c, b, dd = datos_metodo(sp)
    n = len(t) - 1
    k = max(i for i, e in enumerate(ETAPAS_CODIGO) if e[0] <= r)
    _, (l0, l1), titulo = ETAPAS_CODIGO[k]

    # --- código con la línea en ejecución resaltada ---------------------------
    ax = fig.add_axes([0.015, 0.08, 0.47, 0.83])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                color="#0d0f14", ec="#3a404d"))
    ax.text(0.03, 0.965, "spline_cubico.py — SplineCubicoNatural.__init__", fontsize=10.5,
            color=ACENTO, va="top", family="DejaVu Sans Mono", weight="bold")
    ax.text(0.03, 0.915, "Aplicación del método · Zona B (oreja) · coordenada X(t)",
            fontsize=10, color=COL_B, va="top")
    y0, dy = 0.84, 0.052
    for i, ln in enumerate(CODIGO_METODO):
        activo = l0 <= i <= l1
        if activo:
            ax.add_patch(Rectangle((0.015, y0 - i * dy - dy * 0.78), 0.97, dy * 0.95,
                                   color="#3d3418"))
        ax.text(0.025, y0 - i * dy, f"{i + 1:2d}", fontsize=8.5, color="#5d6b80", va="top",
                family="DejaVu Sans Mono")
        ax.text(0.075, y0 - i * dy, ln, fontsize=8.6, va="top", family="DejaVu Sans Mono",
                color="#fff3c4" if activo else "#a5d6a7")
    ax.text(0.03, 0.08, "▶ " + titulo, fontsize=11.5, color=ACENTO, weight="bold", va="center")

    # --- tabla de valores (crece por columnas) --------------------------------
    cols = [("i", lambda i: f"{i}"), ("t_i", lambda i: f"{t[i]:.1f}"),
            ("a_i=x_i", lambda i: f"{x[i]:.0f}")]
    if k >= 1:
        cols.append(("h_i", lambda i: f"{h[i]:.1f}" if i < n else ""))
    if k >= 3:
        cols.append(("c_i", lambda i: f"{c[i]:+.2e}"))
    if k >= 4:
        cols.append(("b_i", lambda i: f"{b[i]:+.3f}" if i < n else ""))
        cols.append(("d_i", lambda i: f"{dd[i]:+.2e}" if i < n else ""))
    axt = fig.add_axes([0.5, 0.08, 0.485, 0.42])
    axt.set_axis_off()
    axt.set_xlim(0, 1)
    axt.set_ylim(0, 1)
    axt.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                 color=PANEL))
    anchos = [0.05, 0.12, 0.13, 0.12, 0.17, 0.15, 0.17]
    xc = 0.03
    for j, (nom, f) in enumerate(cols):
        nueva = (k >= 1 and nom == "h_i" and k == 1) or (nom == "c_i" and k == 3) or \
                (nom in ("b_i", "d_i") and k == 4)
        color = ACENTO if nueva else TEXTO
        axt.text(xc, 0.94, nom, fontsize=9.5, color=ACENTO, va="top", weight="bold",
                 family="DejaVu Sans Mono")
        for i in range(n + 1):
            axt.text(xc, 0.84 - i * 0.078, f(i), fontsize=8.8, va="top", color=color,
                     family="DejaVu Sans Mono")
        xc += anchos[j]

    # --- parte superior derecha: sistema / gráfico ----------------------------
    rect = [0.5, 0.53, 0.485, 0.38]
    if k < 2:
        panel_texto(fig, rect, [
            (f"{n + 1} puntos de control  →  {n} tramos cúbicos", {}),
            ("t = longitud de cuerda acumulada (px)", {"color": TENUE}),
            ("Se resuelve igual para X(t) y para Y(t).", {"color": TENUE}),
            ("Los números que aparecen son los que", {}),
            ("calcula el programa en este momento.", {}),
        ], titulo="Zona B · oreja lateral", inter=0.14, tam=12)
    elif k < 5:
        axm = fig.add_axes(rect)
        axm.set_axis_off()
        axm.set_xlim(0, 1)
        axm.set_ylim(0, 1)
        axm.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
                                     color=PANEL))
        axm.text(0.03, 0.95, "Sistema tridiagonal  A · c = r", fontsize=11, color=ACENTO,
                 weight="bold", va="top")
        m = n + 1
        x0, y0, cw, ch = 0.03, 0.82, 0.068, 0.074
        for i in range(m):
            for j in range(m):
                v = A[i, j]
                txt = "·" if v == 0 else f"{v:.0f}"
                col = ACENTO if (i == j and v != 0) else (TEXTO if v != 0 else "#4a5160")
                axm.text(x0 + j * cw, y0 - i * ch, txt, fontsize=7.4, va="top",
                         family="DejaVu Sans Mono", color=col)
            axm.text(x0 + m * cw + 0.01, y0 - i * ch, f"{rhs[i]:+.3f}", fontsize=7.4,
                     va="top", family="DejaVu Sans Mono", color=COL_B)
        axm.text(x0 + m * cw + 0.01, y0 + 0.07, "r", fontsize=9, color=COL_B, va="top")
    else:
        axg = fig.add_axes([0.53, 0.56, 0.2, 0.33])
        axg.set_facecolor("#0d0f14")
        fr = prog(r, 17, 19.5)
        for i in range(sp.n):
            if i / sp.n > fr:
                break
            ts = np.linspace(sp.t[i], sp.t[i + 1], 40)
            axg.plot(ts, sp.Sx(ts, tramo=i), color=COLORES_TRAMO[i % 11], lw=2.2)
        axg.scatter(t, x, s=14, c="w", zorder=5)
        axg.set_title("X(t) evaluado por tramos", fontsize=9, color=TEXTO)
        axg.tick_params(labelsize=7)
        for s_ in axg.spines.values():
            s_.set_color("#3a404d")
        axc = fig.add_axes([0.77, 0.56, 0.2, 0.33])
        axc.set_facecolor("#0d0f14")
        P = sp.P
        axc.scatter(P[:, 0], P[:, 1], s=14, c="w", zorder=5)
        dibujar_curva(axc, d, "B", frac=fr, lw=2.2)
        axc.set_aspect("equal", adjustable="datalim")
        axc.set_title("Curva (X(t), Y(t))", fontsize=9, color=TEXTO)
        axc.tick_params(labelsize=7)
        for s_ in axc.spines.values():
            s_.set_color("#3a404d")


def dibujar_cuadro(fig, d, t_video):
    fig.clf()
    fig.patch.set_facecolor(FONDO)
    t = tiempo_escena(t_video)
    if t is None:
        escena_codigo(fig, d, t_video - 60)
        cabecera(fig, t_video)
        pie(fig, 62)
        fundido(fig, t_video)
        return
    if t < 7:
        escena_titulo(fig, d, t)
        return
    if t < 16:
        escena_pieza(fig, d, t)
    elif t < 25:
        escena_zonas(fig, d, t)
    elif t < 33:
        escena_contorno(fig, d, t)
    elif t < 41.5:
        escena_puntos(fig, d, t, "A", 33, 41.5)
    elif t < 50:
        escena_puntos(fig, d, t, "B", 41.5, 50)
    elif t < 62:
        escena_formulas(fig, d, t)
    elif t < 75:
        escena_continuidad(fig, d, t)
    elif t < 97:
        escena_reconstruccion(fig, d, t, "A", 75)
    elif t < 119:
        escena_reconstruccion(fig, d, t, "B", 97)
    elif t < 120:
        escena_final(fig, d, 120)
    elif t < 155:
        escena_final(fig, d, t)
    else:
        escena_conclusion(fig, d, t)
    cabecera(fig, t_video)
    pie(fig, t)
    fundido(fig, t_video)


def fundido(fig, t):
    """Fundido a negro breve entre partes."""
    for a, _, _ in PARTES[1:]:
        if abs(t - a) < 0.35:
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_axis_off()
            ax.add_patch(Rectangle((0, 0), 1, 1, color="black",
                                   alpha=1 - abs(t - a) / 0.35, transform=ax.transAxes))


def nueva_figura():
    return plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)


def cuadro_rgb(fig):
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba())[:, :, :3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", nargs="*", type=float, help="segundos a exportar como PNG")
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--salida", default=os.path.join(SALIDA, "video_reconstruccion.mp4"))
    args = ap.parse_args()

    os.makedirs(SALIDA, exist_ok=True)
    print("Preparando modelo…")
    d = preparar()
    fig = nueva_figura()

    if args.preview is not None:
        carpeta = os.path.join(SALIDA, "cuadros")
        os.makedirs(carpeta, exist_ok=True)
        for s in args.preview:
            dibujar_cuadro(fig, d, s)
            ruta = os.path.join(carpeta, f"cuadro_{s:06.1f}.png")
            cv2.imwrite(ruta, cv2.cvtColor(cuadro_rgb(fig), cv2.COLOR_RGB2BGR))
            print(ruta)
        return

    n = int(DURACION * args.fps)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(args.fps), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
           "-c:a", "aac", "-shortest", "-movflags", "+faststart", args.salida]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(n):
        t = k / args.fps
        dibujar_cuadro(fig, d, t)
        proc.stdin.write(cuadro_rgb(fig).tobytes())
        if k % (args.fps * 10) == 0:
            print(f"  {mmss(t)} / {mmss(DURACION)}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("Video generado:", args.salida)


if __name__ == "__main__":
    sys.exit(main())
