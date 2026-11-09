# Reconstrucción digital de una vasija de Tiwanaku mediante Splines Cúbicos

Desafío final de Métodos Numéricos: reconstrucción arqueológica con **Spline Cúbico
paramétrico natural** (implementado desde cero) y animación generada por el modelo.

- **Pieza:** vasija cerámica de Tiwanaku (cuerpo globular, cuello alto, labio evertido, orejas laterales).
- **Fuente de la imagen:** La Región — [*Cinco avances de investigación sobre hallazgos en Tiwanaku que podrían cambiar la historia*](https://www.laregion.bo/cinco-avances-de-investigacion-sobre-hallazgos-en-tiwanaku-que-podrian-cambiar-la-historia/)
- **Zonas reconstruidas:**
  - **Zona A:** tramo faltante del borde superior (labio) izquierdo. Usa 12 puntos y 11 tramos.
  - **Zona B:** oreja izquierda de la parte media del cuerpo, de la que solo queda un muñón. Usa 10 puntos y 9 tramos.

## Cómo ejecutar

```bash
pip install -r requirements.txt      # y tener ffmpeg instalado
python main.py                       # todo: puntos -> spline -> reconstrucción -> video
python main.py --sin-video           # solo cálculos y figuras
python src/generar_video.py --preview 20 80 150   # cuadros PNG sueltos para revisar
```

## Estructura

| Archivo | Qué hace |
|---|---|
| `src/extraer_puntos.py` | Segmenta la vasija (HSV, OpenCV), extrae el **contorno completo** (`datos/contorno_completo.csv`), estima el **eje de simetría** y selecciona los **puntos de control** (`datos/puntos_control.csv`). |
| `src/spline_cubico.py` | Implementación propia del spline cúbico natural **explícito** y **paramétrico**: sistema tridiagonal, algoritmo de Thomas, coeficientes y verificación C⁰, C¹ y C². |
| `src/reconstruccion.py` | Construye los splines, valida contra `scipy` y rellena el material faltante con la textura del lado simétrico. |
| `src/generar_video.py` | Genera el video MP4 de 3:00 en 1280×720 a 24 fps con las 6 partes y los 7 pasos. |
| `guion_narracion.md` | Texto para grabar la voz en off sincronizada con el video. |
| `descripcion_youtube.md` | Texto para la descripción del video (registro del estudiante). |
| `salida/` | Video, imagen reconstruida, figura resumen y tablas de coeficientes. |

## Método

1. **Coordenadas.** Se usa un sistema cartesiano en píxeles: `X = columna` y `Y = 2048 − fila`.
   - Los puntos **intactos** se leen del contorno real, a ambos lados de la fractura.
   - Los puntos **por simetría** se toman del lado derecho intacto y se reflejan respecto al eje: `x' = 2·x_eje − x`.
   - El eje del labio está en x ≈ 939 y el del cuerpo en x ≈ 926.
2. **Spline paramétrico.** El parámetro `t` es la longitud de cuerda acumulada. En cada tramo:
   - `X_i(t) = a_xi + b_xi (t−t_i) + c_xi (t−t_i)² + d_xi (t−t_i)³`
   - `Y_i(t)` tiene la misma forma.
   - Las condiciones son: interpolación (C⁰), igualdad de S' (C¹) y de S'' (C²) en los nodos interiores, y frontera natural `S''=0` en los extremos.
   - Todo esto lleva a un sistema tridiagonal que se resuelve con el algoritmo de Thomas.
   - Se usa la forma paramétrica porque el labio y la oreja tienen tramos verticales: x no es creciente y no existe y(x).
3. **Verificación.** Los saltos en los nodos son de 10⁻¹³ a 10⁻¹⁸, y la diferencia frente a `scipy.interpolate.CubicSpline` es de alrededor de 10⁻¹³.
4. **Reconstrucción.** Se toma el polígono formado por la curva spline y la línea de fractura. Solo se rellenan los píxeles donde falta cerámica, y se usa la textura reflejada del lado intacto.

## Cumplimiento de la rúbrica (30 pts)

| Criterio | Dónde aparece en el video |
|---|---|
| Selección y contextualización (3) | 0:07–0:25: pieza, fuente, zonas A y B marcadas y justificación por simetría. |
| Obtención de puntos (4) | 0:25–0:50: contorno, eje, puntos numerados, tabla de coordenadas, gráfico de los puntos y fuente. |
| Aplicación de splines (7) | 0:50–1:15: fórmulas paramétricas, parámetro t, sistema tridiagonal, C⁰/C¹/C² con zoom en un nodo, verificación numérica y código. |
| Reconstrucción digital (5) | 1:15–2:00: relleno calculado a partir de la curva del spline, más los coeficientes reales de cada tramo. |
| Animación (5) | Aparición progresiva de puntos, trazado tramo a tramo, relleno progresivo, superposición y antes/después. |
| Explicación paso a paso (4) | Barra inferior con los 7 pasos y panel de texto con el paso actual. |
| Calidad y síntesis (2) | Dura exactamente 3:00 y respeta los tiempos de las 6 partes. |
