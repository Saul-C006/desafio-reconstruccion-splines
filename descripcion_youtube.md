**Título sugerido:** Reconstrucción digital de una vasija de Tiwanaku mediante Splines Cúbicos | Métodos Numéricos

**Descripción:**

Desafío final de Métodos Numéricos. Reconstrucción digital animada de dos zonas de una
vasija cerámica de Tiwanaku: el borde superior (labio) y una oreja lateral. Se usa
interpolación con Splines Cúbicos paramétricos naturales.

Proceso: Pieza arqueológica → Puntos de control → Spline Cúbico → Reconstrucción → Animación

- Puntos de control: se extraen de la fotografía por segmentación (Python + OpenCV) y por simetría respecto al eje de la vasija.
- Spline cúbico paramétrico X(t), Y(t) con parámetro de longitud de cuerda y continuidad C0, C1 y C2. Está implementado desde cero (sistema tridiagonal y algoritmo de Thomas) y validado con scipy.
- La animación se genera directamente con el modelo matemático (matplotlib + ffmpeg).

Fuente de la fotografía: La Región — "Cinco avances de investigación sobre hallazgos en
Tiwanaku que podrían cambiar la historia"
https://www.laregion.bo/cinco-avances-de-investigacion-sobre-hallazgos-en-tiwanaku-que-podrian-cambiar-la-historia/

**Registro del Estudiante**
- Estudiante: Saul Walter Callisaya
- Título del trabajo: Reconstrucción digital de una vasija de Tiwanaku mediante Splines Cúbicos
- Enlace de YouTube: (pegar aquí)
