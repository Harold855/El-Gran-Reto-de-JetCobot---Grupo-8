# Pregunta 1 — Informe final de interpretación de órdenes

## 1. Implementación

Se implementó un intérprete de órdenes en ROS 2 que consulta
un servidor LAYA mediante HTTP y recibe decisiones tipadas
de acción, objeto, color, destino, prioridad y permiso.

Las preguntas al modelo utilizan elecciones estructuradas,
evitando texto libre. Esto permite validar los valores antes
de enviarlos a otros componentes del robot.

El timeout es configurable mediante el parámetro `laya_timeout`.
Ante errores de conexión, se utiliza un clasificador propio por
palabras clave y se activa `degradado=True`.

La implementación incluye validación de seguridad.
Con `validacion_estricta=true`, las discrepancias entre LAYA
y las reglas locales provocan el rechazo de la orden.
Con `false`, se mantiene el modo híbrido de evaluación.

## 2. Tabla comparativa de exactitud

| Método | Correctas | Incorrectas | Exactitud |
|---|---:|---:|---:|
| LAYA real | 15/50 | 35 | 30.0 % |
| Palabras clave | 50/50 | 0 | 100.0 % |

La exactitud de LAYA se calculó utilizando sus decisiones
originales, sin sustituirlas por respuestas locales.
Las órdenes inválidas se evalúan por su rechazo.
La prioridad se registra, pero no se puntúa en esta
comparación porque no existe prioridad esperada en el CSV.

## 3. Latencia

| Métrica | Calma | Escenario etiquetado como carga |
|---|---:|---:|
| Consultas | 50 | 50 |
| Mediana total | 298.95 ms | 318.00 ms |
| P95 total | 441.7 ms | 424.5 ms |
| Mediana del servidor | 281.75 ms | 301.12 ms |
| Mediana de tiempo restante | 16.58 ms | 16.51 ms |
| Respuestas degradadas | 0 | 0 |

Las medianas de los componentes no tienen por qué sumar
exactamente la mediana total.

El tiempo restante es el tiempo no atribuido a la inferencia
del servidor; incluye comunicación y otros gastos.

## 4. Análisis de errores

Se evaluaron 50 frases del conjunto disponible con LAYA real
y con el clasificador local. LAYA obtuvo 15/50 aciertos,
mientras que el clasificador por palabras clave obtuvo
50/50. La principal diferencia apareció en las
órdenes inválidas: LAYA autorizó incorrectamente
27 de ellas. También
se observaron 7 errores de destino
y 1 errores de objeto entre las
órdenes válidas autorizadas. Una frase puede presentar
más de un error.

El clasificador local obtuvo mejores resultados en este
conjunto porque identifica estructuras concretas, como
el color que acompaña a «cubo» y el que acompaña a
«zona», además de detectar prohibiciones y expresiones
no admitidas. Su exactitud del 100 % corresponde únicamente
a estas 50 frases y no garantiza igual comportamiento
ante instrucciones nuevas.

En las mediciones del servicio híbrido se obtuvieron
50/50 aciertos por escenario. Este resultado no es
la exactitud independiente de LAYA: en ese modo
los parámetros físicos se verificaban localmente.

La mediana total aumentó 19.05 ms entre escenarios,
aproximadamente un 6.4 %, mientras que el P95
disminuyó 17.2 ms. El tiempo reportado por el
servidor aumentó y el tiempo restante permaneció
aproximadamente constante. La ejecución denominada
«carga» no demuestra por sí sola concurrencia real
de otros equipos.

## 5. Verificaciones y limitaciones

- Conexión HTTP al servidor LAYA: comprobada.
- Modelo informado por el servidor: `multilingual`.
- Respaldo local ante conexión rechazada: comprobado.
- Rechazo de una discrepancia de destino en modo seguro:
  comprobado.
- Servicio probado: `/interpretar_orden_p1_prueba`.
- Para la demostración se requiere el nombre oficial
  `/interpretar_orden`, sin servidores duplicados.
- El preset asignado por el docente no está confirmado.
- Debe confirmarse que el CSV usado corresponda al
  conjunto oficial de 50 frases del docente.
- La concurrencia real del escenario de carga no está
  acreditada mediante los resultados disponibles.

## 6. Archivos de evidencia

- `frases_50.csv`: conjunto de entrada.
- `mediciones/comparacion_real_laya_20261015_203034.csv`:
  respuestas originales de ambos métodos.
- `mediciones/tabla_exactitud_laya_20261015_203034.md`:
  comparación independiente.
- `mediciones/prediccion_laya_20261015_203034.txt`:
  predicción previa.
- `resultados_p1_g8/`: resultados históricos del
  servicio híbrido y latencias.
- `mediciones/comparacion_calma_vs_carga_20261015_190345.md`:
  comparación de escenarios.
