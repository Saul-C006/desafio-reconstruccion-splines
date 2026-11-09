"""
Ejecuta todo el proceso de principio a fin:

  1. Extrae el contorno y los puntos de control de la fotografía.
  2. Calcula los splines cúbicos paramétricos y la reconstrucción.
  3. Genera el video (salida/video_reconstruccion.mp4).

Uso:  python main.py            (todo)
      python main.py --sin-video
"""
import os
import subprocess
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, SRC)

import extraer_puntos  # noqa: E402
import reconstruccion  # noqa: E402

if __name__ == "__main__":
    print("== 1. Extracción de coordenadas ==")
    d = extraer_puntos.extraer()
    print(f"   contorno: {len(d['contorno'])} puntos | eje labio x={d['eje_borde']:.1f} "
          f"| eje cuerpo x={d['eje_cuerpo']:.1f}")

    print("== 2. Splines cúbicos y reconstrucción ==")
    m = reconstruccion.construir_modelo()
    reconstruccion.guardar_tablas(m)
    reconstruccion.figura_resumen(m)
    for z in ("A", "B"):
        c0, c1, c2 = m["continuidad_" + z]
        print(f"   Zona {z}: {m['spline_' + z].n} tramos | C0={c0:.1e} C1={c1:.1e} C2={c2:.1e}"
              f" | vs scipy={m['scipy_' + z]:.1e}")

    if "--sin-video" not in sys.argv:
        print("== 3. Video ==")
        subprocess.run([sys.executable, os.path.join(SRC, "generar_video.py")], check=True)
