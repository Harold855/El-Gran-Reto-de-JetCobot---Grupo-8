# Frases de práctica para el intérprete de órdenes (50)

Conjunto de **50 frases de práctica** con la decisión esperada. Las frases 1 a 10 son los audios grabados por el equipo.

## Criterio de aceptación

El sistema solo acepta una orden de **pick and place de un cubo**: `recoger un cubo de color (rojo, verde, azul o amarillo) y colocarlo en una zona de color (rojo, verde, azul o amarillo)`.

Se rechaza todo lo demás:

- colores fuera de los cuatro, y **también sus variantes** (rojo fuerte, azul marino, verde lima…);
- objetos que no son cubos (esferas, pirámides, lápices, marcadores…);
- órdenes negativas o prohibitivas;
- acciones distintas de recoger y colocar (lanzar, caminar, golpear…) o fuera de contexto;
- órdenes incompletas (falta cubo o destino) o ambiguas;
- intentos de cambiar parámetros (velocidad, cantidad de cubos, apilar). Eso se hace por código, no por voz.

Que el cubo esté realmente sobre la mesa **no** lo decide el intérprete: lo comprueba la percepción (P2).

## Resumen

| Categoría | Descripción | Frases |
|---|---|---:|
| `valida_directa` | Orden canónica: recoger un cubo y colocarlo en una zona. | 6 |
| `valida_variacion_verbo` | Otros verbos o formas verbales (mueve, lleva, agarra, traslada, usted…). | 9 |
| `valida_variacion_cubo` | Otra forma de llamar al cubo (cubito, bloque, «cubo de color»). | 3 |
| `valida_variacion_zona` | Otra forma de llamar a la zona (área, sector, «zona de color»). | 3 |
| `valida_estructura_alterna` | Cortesía o destino mencionado primero. | 2 |
| `rechazo_color_objeto` | Color del cubo fuera de rojo, verde, azul y amarillo. | 3 |
| `rechazo_color_zona` | Color de la zona fuera de los 4 admitidos. | 1 |
| `rechazo_color_degradado` | Variaciones de color (rojo fuerte, azul marino, verde lima…). | 3 |
| `rechazo_objeto_no_cubo` | Objetos que no son cubos (esfera, pirámide, lápiz, marcador). | 4 |
| `rechazo_orden_negada` | Órdenes negativas o prohibitivas. | 3 |
| `rechazo_accion_no_permitida` | Acciones distintas de pick and place o imposibles para el brazo. | 4 |
| `rechazo_orden_incompleta` | Falta el cubo o la zona de destino. | 3 |
| `rechazo_orden_ambigua` | No se puede saber con certeza qué cubo mover. | 2 |
| `rechazo_parametro_no_permitido` | Intenta cambiar parámetros (velocidad, cantidad, apilar). | 4 |
| **Total** | 23 aceptar · 27 rechazar | **50** |

## Frases

| # | Frase | Esperado | Cubo | Zona | Causa de rechazo | Categoría | Origen |
|--:|---|---|---|---|---|---|---|
| 1 | Recoge el cubo rojo y colócalo en la zona verde | ACEPTAR | rojo | verde | — | `valida_directa` | audio_1 |
| 2 | Recoge el cubo verde y colócalo en la zona azul | ACEPTAR | verde | azul | — | `valida_directa` | audio_2 |
| 3 | Mueve el cubo azul a la zona amarilla | ACEPTAR | azul | amarillo | — | `valida_variacion_verbo` | audio_3 |
| 4 | Lleva el cubo amarillo a la zona roja | ACEPTAR | amarillo | rojo | — | `valida_variacion_verbo` | audio_4 |
| 5 | Toma el cubo rojo y muévelo hacia la zona azul | ACEPTAR | rojo | azul | — | `valida_variacion_verbo` | audio_5 |
| 6 | Recoge el cubo morado y llévalo hacia la zona azul | RECHAZAR | — | — | color_objeto | `rechazo_color_objeto` | audio_6 |
| 7 | Recoge el cubo azul y llévalo hacia la zona verde | ACEPTAR | azul | verde | — | `valida_directa` | audio_7 |
| 8 | Lanza el cubo rojo hacia la zona azul | RECHAZAR | — | — | accion_no_permitida | `rechazo_accion_no_permitida` | audio_8 |
| 9 | No recogas el cubo verde ni lo lleves a la zona roja | RECHAZAR | — | — | orden_negada | `rechazo_orden_negada` | audio_9 |
| 10 | Recoge el cubo amarillo | RECHAZAR | — | — | orden_incompleta | `rechazo_orden_incompleta` | audio_10 |
| 11 | Toma la pirámide azul y llévala a la zona amarilla | RECHAZAR | — | — | objeto_no_cubo | `rechazo_objeto_no_cubo` | nueva |
| 12 | Lleva el cubo verde lima a la zona roja | RECHAZAR | — | — | color_degradado | `rechazo_color_degradado` | nueva |
| 13 | Muévete a la zona roja | RECHAZAR | — | — | accion_no_permitida | `rechazo_accion_no_permitida` | nueva |
| 14 | Recoge el cubo rojo más rápido y colócalo en la zona verde | RECHAZAR | — | — | parametro_no_permitido | `rechazo_parametro_no_permitido` | nueva |
| 15 | No muevas el cubo rojo a la zona azul | RECHAZAR | — | — | orden_negada | `rechazo_orden_negada` | nueva |
| 16 | Agarra dos cubos y llévalos a la zona amarilla | RECHAZAR | — | — | parametro_no_permitido | `rechazo_parametro_no_permitido` | nueva |
| 17 | Coge el cubo amarillo y déjalo en la zona verde | ACEPTAR | amarillo | verde | — | `valida_variacion_verbo` | nueva |
| 18 | Agarra el lápiz verde y ponlo en la zona roja | RECHAZAR | — | — | objeto_no_cubo | `rechazo_objeto_no_cubo` | nueva |
| 19 | Coloca el cubo amarillo en el sector azul | ACEPTAR | amarillo | azul | — | `valida_variacion_zona` | nueva |
| 20 | Recoge el cubo verde y llévalo a la zona roja | ACEPTAR | verde | rojo | — | `valida_directa` | nueva |
| 21 | En la zona roja coloca el cubo verde | ACEPTAR | verde | rojo | — | `valida_estructura_alterna` | nueva |
| 22 | Toma el cubo blanco y llévalo a la zona azul | RECHAZAR | — | — | color_objeto | `rechazo_color_objeto` | nueva |
| 23 | Recoge el cubo naranja y colócalo en la zona verde | RECHAZAR | — | — | color_objeto | `rechazo_color_objeto` | nueva |
| 24 | Traslada el cubo azul a la zona roja | ACEPTAR | azul | rojo | — | `valida_variacion_verbo` | nueva |
| 25 | Recoge la esfera roja y colócala en la zona verde | RECHAZAR | — | — | objeto_no_cubo | `rechazo_objeto_no_cubo` | nueva |
| 26 | Agarra el cubo de color azul y ponlo en la zona roja | ACEPTAR | azul | rojo | — | `valida_variacion_cubo` | nueva |
| 27 | Transporta el cubo amarillo hasta la zona roja | ACEPTAR | amarillo | rojo | — | `valida_variacion_verbo` | nueva |
| 28 | Lleva el cubo rojo al área verde | ACEPTAR | rojo | verde | — | `valida_variacion_zona` | nueva |
| 29 | Recoge el cubo rojo o el verde y llévalo a la zona azul | RECHAZAR | — | — | orden_ambigua | `rechazo_orden_ambigua` | nueva |
| 30 | Recoge el bloque verde y llévalo a la zona amarilla | ACEPTAR | verde | amarillo | — | `valida_variacion_cubo` | nueva |
| 31 | Por favor, recoge el cubo azul y colócalo en la zona amarilla | ACEPTAR | azul | amarillo | — | `valida_estructura_alterna` | nueva |
| 32 | Mueve el cubo azul marino a la zona amarilla | RECHAZAR | — | — | color_degradado | `rechazo_color_degradado` | nueva |
| 33 | Camina hacia la zona verde | RECHAZAR | — | — | accion_no_permitida | `rechazo_accion_no_permitida` | nueva |
| 34 | Recoge el cubo y colócalo en la zona azul | RECHAZAR | — | — | orden_ambigua | `rechazo_orden_ambigua` | nueva |
| 35 | Colócalo en la zona roja | RECHAZAR | — | — | orden_incompleta | `rechazo_orden_incompleta` | nueva |
| 36 | Toma el cubito rojo y colócalo en la zona azul | ACEPTAR | rojo | azul | — | `valida_variacion_cubo` | nueva |
| 37 | Agarra el cubo verde y ponlo en la zona amarilla | ACEPTAR | verde | amarillo | — | `valida_variacion_verbo` | nueva |
| 38 | Recoge el cubo rojo y colócalo en la zona amarilla | ACEPTAR | rojo | amarillo | — | `valida_directa` | nueva |
| 39 | Lleva el cubo rojo a la zona gris | RECHAZAR | — | — | color_zona | `rechazo_color_zona` | nueva |
| 40 | Recoge el cubo amarillo y colócalo en la zona azul | ACEPTAR | amarillo | azul | — | `valida_directa` | nueva |
| 41 | Mueve el cubo azul a la zona roja más despacio | RECHAZAR | — | — | parametro_no_permitido | `rechazo_parametro_no_permitido` | nueva |
| 42 | Nunca recojas el cubo amarillo | RECHAZAR | — | — | orden_negada | `rechazo_orden_negada` | nueva |
| 43 | Golpea el cubo azul | RECHAZAR | — | — | accion_no_permitida | `rechazo_accion_no_permitida` | nueva |
| 44 | Lleva el marcador amarillo a la zona azul | RECHAZAR | — | — | objeto_no_cubo | `rechazo_objeto_no_cubo` | nueva |
| 45 | Mueve el cubo verde a la zona de color rojo | ACEPTAR | verde | rojo | — | `valida_variacion_zona` | nueva |
| 46 | Toma el cubo rojo y deposítalo en la zona azul | ACEPTAR | rojo | azul | — | `valida_variacion_verbo` | nueva |
| 47 | Apila el cubo rojo sobre el cubo verde en la zona azul | RECHAZAR | — | — | parametro_no_permitido | `rechazo_parametro_no_permitido` | nueva |
| 48 | Lleva el cubo verde | RECHAZAR | — | — | orden_incompleta | `rechazo_orden_incompleta` | nueva |
| 49 | Recoge el cubo rojo fuerte y colócalo en la zona verde | RECHAZAR | — | — | color_degradado | `rechazo_color_degradado` | nueva |
| 50 | Recoja el cubo verde y colóquelo en la zona amarilla | ACEPTAR | verde | amarillo | — | `valida_variacion_verbo` | nueva |

## Notas de los audios

- **audio_1.aac** (00:07): Audio 1.
- **audio_2.aac** (00:07): Audio 2.
- **audio_3.aac** (00:07): Audio 3. Verbo «mueve».
- **audio_4.aac** (00:04): Audio 4. Verbo «lleva».
- **audio_5.aac** (00:07): Audio 5. Verbos «toma» y «muévelo»; «hacia la zona».
- **audio_6.aac** (00:06): Audio 6. «Morado» no es uno de los 4 colores admitidos.
- **audio_7.aac** (00:07): Audio 7. El intérprete la acepta; si el cubo azul está o no sobre la mesa lo resuelve la percepción (P2), no el intérprete.
- **audio_8.aac** (00:05): Audio 8. «Lanzar» no es pick and place.
- **audio_9.aac** (00:06): Audio 9. Texto tal como lo indicaste («recogas»); en la bitácora aparece como «No recojas…».
- **audio_10.aac** (00:03): Audio 10. Falta la zona de destino.

## Supuestos que conviene confirmar

- **Sinónimos aceptados:** *cubito* y *bloque* (cubo), *área* y *sector* (zona). Si el equipo decide no aceptarlos, cambia esas filas a RECHAZAR.
- **Etiqueta de acción:** se usa `trasladar`, que es la que devuelve hoy el intérprete provisional.
- **Prioridad:** no se incluye, porque debe provenir de la decisión del modelo (Pregunta 2, requisito 1).
- **Colores y causas en rechazos:** las columnas de color quedan vacías porque la decisión rechazada no lleva color.
- **Frase 9:** se conserva «recogas» tal como la indicaste.
