# Guion del video — 3:00 min

El video `salida/video_reconstruccion.mp4` ya trae todos los textos y animaciones en
pantalla y una pista de audio en silencio. Graba esta narración leyendo a ritmo
normal (unas 150 palabras por minuto). Cada bloque indica qué se ve en pantalla en ese
momento.

Para unir tu voz con el video puedes usar CapCut, Shotcut, DaVinci Resolve u OpenShot,
o ffmpeg:

```bash
ffmpeg -i salida/video_reconstruccion.mp4 -i mi_voz.mp3 -map 0:v -map 1:a \
       -c:v copy -c:a aac -shortest salida/video_final_con_voz.mp4
```

---

## PARTE 1 · Presentación de la pieza (0:00 – 0:25)

**[0:00 – 0:07] En pantalla: título y foto de la vasija**
> Hola, soy Saul Walter Callisaya. En este desafío final de Métodos Numéricos voy a
> reconstruir digitalmente una pieza arqueológica usando Splines Cúbicos.

**[0:07 – 0:16] En pantalla: paso 1, pieza original, ficha y fuente**
> La pieza es una vasija cerámica de la cultura Tiwanaku. Tiene cuerpo globular,
> cuello alto, labio evertido y orejas laterales. La fotografía es del diario
> La Región, de la nota "Cinco avances de investigación sobre hallazgos en Tiwanaku
> que podrían cambiar la historia". La vasija fue armada a partir de muchos fragmentos,
> pero todavía le faltan partes.

**[0:16 – 0:25] En pantalla: paso 2, zonas A y B marcadas**
> Elegí dos zonas. La zona A es un tramo roto del borde superior izquierdo. La zona B
> es la oreja izquierda de la parte media, entre y igual a mil y mil trescientos, de la
> que solo quedan su unión superior y un muñón. Las elegí porque la vasija es simétrica
> respecto a un eje vertical, y el lado derecho, con su labio y su oreja, está intacto
> y me sirve de guía.

## PARTE 2 · Obtención de los puntos (0:25 – 0:50)

**[0:25 – 0:33] En pantalla: contorno verde, ejes de simetría y código de extracción**
> Para obtener las coordenadas, mi programa en Python separa la vasija del fondo por
> color, con OpenCV, y extrae el contorno completo: más de cuatro mil puntos x, y.
> Trabajo en un sistema cartesiano en píxeles. X es la columna e Y es dos mil cuarenta
> y ocho menos la fila. Después calculo el eje de simetría como el punto medio entre el
> borde izquierdo y el derecho.

**[0:33 – 0:41] En pantalla: puntos de la zona A, tabla de coordenadas y gráfico**
> Para el borde usé doce puntos de control. Nueve los medí directamente sobre el
> contorno intacto, a los dos lados de la rotura. Los otros tres los obtuve
> reflejando el labio derecho con la fórmula x prima igual a dos por x del eje menos x.

**[0:41 – 0:50] En pantalla: puntos de la zona B, líneas de simetría desde la oreja derecha**
> Para la oreja usé diez puntos. Cuatro están sobre la parte intacta: arriba en el
> hombro y abajo en el muñón. Los otros seis copian la forma de la oreja derecha,
> o sea cuánto sobresale del cuerpo, llevada a la altura de la oreja izquierda. Aquí se
> ven la tabla de coordenadas y el gráfico de los puntos.

## PARTE 3 · Spline Cúbico: modelo y código (0:50 – 1:30)

**[0:50 – 1:00] En pantalla: fórmulas del spline paramétrico y gráficas X(t), Y(t)**
> El borde y la oreja tienen tramos verticales: x no siempre crece, así que no puedo
> escribir y en función de x. Por eso uso el Spline Cúbico paramétrico. X de t e Y de t
> son polinomios cúbicos por tramos, y el parámetro t es la distancia acumulada entre
> puntos. Cada par de puntos consecutivos tiene su propio polinomio.

**[1:00 – 1:20] En pantalla: el código del método ejecutándose con los números reales**
> Así se aplica el método en el código, con los datos reales de la oreja. Primero
> calculo t y tomo los coeficientes a, que son las coordenadas x de los puntos.
> Luego calculo h, el ancho de cada intervalo. Con eso armo el sistema tridiagonal:
> en la diagonal va dos por la suma de dos h vecinos, y a los lados van los h.
> Las filas primera y última dan la condición natural. Resuelvo el sistema con el
> algoritmo de Thomas y obtengo los coeficientes c. Con c calculo b y d de cada tramo.
> Finalmente evalúo cada polinomio y aparece la curva de la oreja.

**[1:20 – 1:30] En pantalla: continuidad C0, C1, C2, zoom en un nodo y verificación**
> Los tramos se unen con continuidad C cero, es decir sin saltos. También C uno, con la
> misma pendiente en cada nodo, y C dos, con la misma curvatura, así que la unión es
> suave. El programa verifica que los saltos en los nodos son prácticamente cero y que
> el resultado coincide con la librería scipy.

## PARTE 4 · Reconstrucción paso a paso (1:30 – 2:10)

**[1:30 – 1:50] En pantalla: zona A, puntos, primer tramo, tramos siguientes y relleno**
> Empiezo por el borde. Primero aparecen los puntos de control. Luego se traza el
> primer tramo, S cero, con sus coeficientes calculados. Después se agregan los tramos
> uno por uno hasta completar los once del spline. Por último, el área entre el spline
> y la rotura se rellena con la textura del lado simétrico. Esa es la reconstrucción
> digital.

**[1:50 – 2:10] En pantalla: zona B, el mismo proceso en la oreja**
> Repito el proceso con la oreja: puntos de control, primer tramo y unión de los nueve
> tramos. La curva sale desde el hombro y baja hasta el muñón. Luego se rellena de
> forma progresiva con la textura de la oreja derecha.

## PARTE 5 · Animación final (2:10 – 2:38)

**[2:10 – 2:38] En pantalla: original, splines superpuestos, relleno, antes y después**
> Esta es la animación completa. Primero la pieza original, después los splines
> superpuestos sobre la fotografía, luego el relleno progresivo y, al final, la
> comparación del antes y el después con el detalle de cada zona. Todo lo que se dibuja
> sale del modelo matemático. Nada está dibujado a mano.

## PARTE 6 · Conclusión (2:38 – 3:00)

**[2:38 – 3:00] En pantalla: tarjetas de conclusión y la vasija reconstruida**
> En conclusión, reconstruí el tramo que faltaba del borde superior y la oreja
> izquierda de la parte media. Los Splines Cúbicos sirven porque pasan exactamente por
> los puntos medidos y forman curvas suaves, sin las oscilaciones de un solo polinomio
> de grado alto. Una limitación es que la foto es plana y con perspectiva, y la oreja
> derecha está cortada por el encuadre, así que la forma depende de suponer simetría.
> Como aplicación futura, el perfil se puede girar para obtener un modelo en 3D e
> incluso imprimir piezas de reposición. Gracias por su atención.
