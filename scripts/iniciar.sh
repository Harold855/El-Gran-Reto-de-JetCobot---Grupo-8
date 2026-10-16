#!/usr/bin/env bash
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

set +u
source /opt/ros/humble/setup.bash

if [[ ! -f "$PROYECTO/install/setup.bash" ]]; then
    echo "ERROR: proyecto no compilado."
    echo "Ejecuta colcon build antes de iniciar."
    exit 1
fi

source "$PROYECTO/install/setup.bash"
set -u

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-92}"   # el definido en tu terminal; 92 solo si no hay ninguno
MODO="${MODO:-simulado}"                          # simulado | real
PERMITIR_REAL="false"
if [[ "$MODO" == "real" ]]; then
    if [[ "${PERMITIR_MOVIMIENTO_REAL:-no}" != "si" ]]; then
        echo "ERROR: MODO=real exige PERMITIR_MOVIMIENTO_REAL=si (y respaldos de hardware conectados)."
        exit 1
    fi
    PERMITIR_REAL="true"
elif [[ "$MODO" != "simulado" ]]; then
    echo "ERROR: MODO debe ser simulado o real."
    exit 1
fi

echo "========================================"
echo " GRAN RETO JETCOBOT - BROKER DEL BRAZO"
echo "========================================"
mkdir -p "$PROYECTO/evidencias/pregunta_2/mediciones"

echo "Dominio ROS: $ROS_DOMAIN_ID"
echo "Modo /pick_place: $MODO"
echo "Publicación: /joint_states (el brazo solo se mueve si el puente del kit está en marcha)"
echo "Rechazos: evidencias/pregunta_2/mediciones/rechazos.csv"
echo

exec ros2 run arm_broker broker --ros-args \
    -p politica:="${POLITICA:-prioridad}" \
    -p tau_envejecimiento_s:=8.0 \
    -p modo_ejecucion:="$MODO" \
    -p permitir_movimiento_real:="$PERMITIR_REAL" \
    -p archivo_registro_tareas:="$PROYECTO/evidencias/pregunta_2/mediciones/registro_tareas.csv" \
    -p cola_max:=20 \
    -p duracion_movimiento_s:=1.0 \
    -p pasos_interpolacion:=20 \
    -p archivo_rechazos:="$PROYECTO/evidencias/pregunta_2/mediciones/rechazos.csv"
