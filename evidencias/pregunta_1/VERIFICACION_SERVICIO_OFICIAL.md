# Verificación funcional del servicio oficial

- Servicio: /interpretar_orden
- Interfaz: interprete_ordenes_interfaces/srv/InterpretarOrden
- Orden válida: cubo rojo hacia zona verde
- Resultado: permitido=True, degradado=False, prioridad=1
- Tiempo del servidor: 300.86 ms
- Segunda orden: cubo azul hacia zona roja
- Resultado: permitido=False por discrepancia LAYA en destino
- Tiempo del servidor: 328.69 ms
- No se ejecutaron movimientos físicos.
