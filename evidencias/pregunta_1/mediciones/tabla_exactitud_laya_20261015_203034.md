# Pregunta 1 - Exactitud independiente de LAYA

Evaluación de 50 frases con el servidor real.
La evaluación utiliza las seis decisiones originales de LAYA.
Las correcciones del intérprete híbrido no se contabilizan como aciertos de LAYA.

| Método | Correctas | Incorrectas | Exactitud |
|---|---:|---:|---:|
| LAYA real | 15/50 | 35 | 30.0 % |
| Palabras clave | 50/50 | 0 | 100.0 % |

- Errores de consulta HTTP o formato: 0
- Modelo utilizado: multilingual
- Prioridad: registrada, pero no incluida en la exactitud porque el CSV no contiene prioridad esperada.
- Para frases inválidas se evalúa el rechazo; para frases válidas se evalúan autorización, acción, objeto, color y destino.
- Mediana HTTP: 399.48 ms
- P95 HTTP: 506.56 ms

## Frases incorrectas de LAYA

| ID | Frase | LAYA objeto | LAYA color | LAYA destino |
|---|---|---|---|---|
| 2 | Recoge el cubo verde y colócalo en la zona azul | cubo | verde | amarillo |
| 3 | Mueve el cubo azul a la zona amarilla | cubo | azul | rojo |
| 6 | Recoge el cubo morado y llévalo hacia la zona azul | cubo | ninguno | azul |
| 7 | Recoge el cubo azul y llévalo hacia la zona verde | cubo | azul | rojo |
| 8 | Lanza el cubo rojo hacia la zona azul | cubo | rojo | rojo |
| 9 | No recogas el cubo verde ni lo lleves a la zona roja | cubo | ninguno | ninguno |
| 10 | Recoge el cubo amarillo | cubo | amarillo | ninguno |
| 11 | Toma la pirámide azul y llévala a la zona amarilla | otro | verde | amarillo |
| 12 | Lleva el cubo verde lima a la zona roja | cubo | ninguno | rojo |
| 13 | Muévete a la zona roja | cubo | azul | rojo |
| 14 | Recoge el cubo rojo más rápido y colócalo en la zona verde | cubo | rojo | verde |
| 15 | No muevas el cubo rojo a la zona azul | cubo | ninguno | ninguno |
| 16 | Agarra dos cubos y llévalos a la zona amarilla | cubo | verde | amarillo |
| 17 | Coge el cubo amarillo y déjalo en la zona verde | cubo | amarillo | amarillo |
| 18 | Agarra el lápiz verde y ponlo en la zona roja | otro | azul | rojo |
| 19 | Coloca el cubo amarillo en el sector azul | cubo | amarillo | amarillo |
| 20 | Recoge el cubo verde y llévalo a la zona roja | cubo | verde | amarillo |
| 22 | Toma el cubo blanco y llévalo a la zona azul | cubo | rojo | azul |
| 23 | Recoge el cubo naranja y colócalo en la zona verde | cubo | amarillo | verde |
| 25 | Recoge la esfera roja y colócala en la zona verde | otro | verde | verde |
| 28 | Lleva el cubo rojo al área verde | cubo | rojo | amarillo |
| 29 | Recoge el cubo rojo o el verde y llévalo a la zona azul | cubo | rojo | azul |
| 30 | Recoge el bloque verde y llévalo a la zona amarilla | ninguno | verde | amarillo |
| 32 | Mueve el cubo azul marino a la zona amarilla | cubo | rojo | azul |
| 33 | Camina hacia la zona verde | ninguno | verde | verde |
| 34 | Recoge el cubo y colócalo en la zona azul | cubo | rojo | azul |
| 35 | Colócalo en la zona roja | cubo | azul | rojo |
| 39 | Lleva el cubo rojo a la zona gris | cubo | rojo | azul |
| 41 | Mueve el cubo azul a la zona roja más despacio | cubo | azul | azul |
| 42 | Nunca recojas el cubo amarillo | cubo | amarillo | amarillo |
| 43 | Golpea el cubo azul | cubo | rojo | rojo |
| 44 | Lleva el marcador amarillo a la zona azul | ninguno | amarillo | rojo |
| 47 | Apila el cubo rojo sobre el cubo verde en la zona azul | cubo | rojo | azul |
| 48 | Lleva el cubo verde | cubo | verde | amarillo |
| 49 | Recoge el cubo rojo fuerte y colócalo en la zona verde | cubo | rojo | verde |
