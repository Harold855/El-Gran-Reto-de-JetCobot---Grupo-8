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

export ROS_DOMAIN_ID=162

echo "========================================"
echo " GRAN RETO JETCOBOT - BROKER DEL BRAZO"
echo "========================================"
mkdir -p "$PROYECTO/evidencias/pregunta_2/mediciones"

echo "Dominio ROS: $ROS_DOMAIN_ID"
echo "Publicación: /joint_states (el brazo solo se mueve si el puente del kit está en marcha)"
echo "Rechazos: evidencias/pregunta_2/mediciones/rechazos.csv"
echo

exec ros2 run arm_broker broker --ros-args \
    -p politica:="${POLITICA:-prioridad}" \
    -p tau_envejecimiento_s:=8.0 \
    -p cola_max:=20 \
    -p duracion_movimiento_s:=1.0 \
    -p pasos_interpolacion:=20 \
    -p archivo_rechazos:="$PROYECTO/evidencias/pregunta_2/mediciones/rechazos.csv"
