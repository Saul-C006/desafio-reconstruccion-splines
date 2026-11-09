# Guion de narración (voz en off) — 3:00 min

El video generado (`salida/video_reconstruccion.mp4`) ya trae todos los textos en
pantalla y una pista de audio en silencio. Para subirlo a YouTube conviene grabar
esta narración encima, siguiendo los tiempos. Se puede hacer con cualquier editor
(CapCut, Shotcut, DaVinci Resolve, OpenShot) o con ffmpeg:

```bash
ffmpeg -i salida/video_reconstruccion.mp4 -i mi_voz.mp3 -map 0:v -map 1:a \
       -c:v copy -c:a aac -shortest salida/video_final_con_voz.mp4
```

---

## Parte 1 · Presentación de la pieza (0:00 – 0:25)

**0:00 – 0:07 (título)**
"Hola, soy Saul Walter Callisaya. En este desafío final de Métodos Numéricos voy a
reconstruir digitalmente una pieza arqueológica usando Splines Cúbicos."

**0:07 – 0:16 (paso 1: pieza original)**
"La pieza es una vasija cerámica de Tiwanaku, de cuerpo globular, cuello alto, labio
evertido y orejas laterales. La fotografía es del diario La Región, en su nota
'Cinco avances de investigación sobre hallazgos en Tiwanaku que podrían cambiar la
historia'. La vasija fue restaurada a partir de muchos fragmentos, pero le faltan partes."

**0:16 – 0:25 (paso 2: zona seleccionada)**
"Elegí dos zonas: la zona A, un tramo del borde superior izquierdo que está roto, y la
zona B, la oreja izquierda de la parte media, de la que solo queda un muñón. Las
elegí porque la vasija es un sólido de revolución, simétrica respecto a un eje vertical,
y el lado derecho está intacto: el labio y la oreja derecha sirven de guía."

## Parte 2 · Obtención de los puntos (0:25 – 0:50)

**0:25 – 0:33**
"Para obtener las coordenadas, el programa en Python segmenta la vasija por color con
OpenCV y extrae el contorno completo: más de cuatro mil puntos x, y. Uso un sistema
cartesiano en píxeles: X es la columna e Y es dos mil cuarenta y ocho menos la fila.
Luego calculo el eje de simetría como el punto medio entre los bordes izquierdo y derecho."

**0:33 – 0:41 (zona A)**
"Para el borde tomé doce puntos de control: nueve medidos directamente sobre el
contorno intacto a ambos lados de la fractura, y tres puntos guía obtenidos reflejando
el labio derecho con la fórmula x prima igual a dos por x del eje menos x."

**0:41 – 0:50 (zona B)**
"Para la oreja tomé diez puntos: cuatro sobre el cuerpo intacto, arriba y abajo, y seis
reflejados desde la oreja derecha. La parte central de la oreja derecha queda cortada
por el borde de la foto; esa parte la completa el propio spline. Aquí se ven la tabla
de coordenadas y el gráfico de los puntos."

## Parte 3 · Explicación del Spline (0:50 – 1:15)

**0:50 – 1:02**
"Como el borde y la oreja tienen tramos verticales y se repliegan, x no es creciente y
no se puede usar y de x. Por eso uso el Spline Cúbico paramétrico: X de t e Y de t son
polinomios cúbicos por tramos. El parámetro t es la longitud de cuerda acumulada entre
puntos. Cada par de puntos consecutivos tiene su propio polinomio cúbico; con n tramos
hay cuatro n coeficientes, que salen de un sistema tridiagonal resuelto con el algoritmo
de Thomas."

**1:02 – 1:15**
"Los tramos se unen cumpliendo continuidad C cero: la curva no tiene saltos; C uno:
la pendiente es la misma en cada nodo, no hay esquinas; y C dos: la curvatura también
coincide, así la unión es suave. Con la condición natural, segunda derivada cero en los
extremos, el sistema queda completo. El programa verifica que los saltos en los nodos
son del orden de diez a la menos trece, es decir cero, y coincide con scipy."

## Parte 4 · Reconstrucción paso a paso (1:15 – 2:00)

**1:15 – 1:37 (zona A)**
"Empiezo por el borde. Primero cargo los puntos. Luego calculo y trazo el primer
segmento, S cero, con sus coeficientes. Después agrego los siguientes tramos uno por uno
hasta tener el spline completo de once tramos. Finalmente relleno el área encerrada entre
el spline y la fractura con la textura del lado simétrico: esa es la reconstrucción digital."

**1:37 – 2:00 (zona B)**
"Repito el proceso con la oreja: puntos de control, primer tramo, unión de los nueve
tramos y relleno progresivo. Se ve que el muñón roto queda dentro de la oreja
reconstruida, lo que confirma que la forma es coherente."

## Parte 5 · Animación final (2:00 – 2:35)

"Ahora la animación completa: la pieza original, la superposición de los splines sobre
la fotografía, el relleno progresivo y, al final, la comparación lado a lado del antes y
el después, con el detalle de cada zona. Todo lo que se dibuja sale del modelo matemático,
nada está dibujado a mano."

## Parte 6 · Conclusión (2:35 – 3:00)

"En conclusión, reconstruí el tramo faltante del labio superior y la oreja izquierda.
Los Splines Cúbicos son útiles porque pasan exactamente por los puntos medidos y forman
curvas suaves, sin las oscilaciones de un polinomio de grado alto. Una limitación es que
la foto es 2D, con perspectiva, y la oreja derecha está cortada por el encuadre, así que
la forma depende de suponer simetría. Como aplicación futura, este perfil se puede girar
para obtener un modelo 3D e incluso imprimir piezas de reposición. Gracias."
