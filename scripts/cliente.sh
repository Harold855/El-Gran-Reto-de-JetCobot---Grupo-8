#!/usr/bin/env bash
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u
source /opt/ros/humble/setup.bash
source "$PROYECTO/install/setup.bash"
set -u

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-92}"   # el definido en tu terminal; 92 solo si no hay ninguno

CLIENTE="${1:-alumno_1}"
PRIORIDAD="${2:-5}"

if [[ ! "$PRIORIDAD" =~ ^[0-9]+$ ]] ||
   (( PRIORIDAD > 255 )); then
    echo "ERROR: prioridad debe estar entre 0 y 255."
    exit 1
fi

echo "Cliente: $CLIENTE"
echo "Prioridad: $PRIORIDAD"
echo "Dominio ROS: $ROS_DOMAIN_ID"

exec ros2 run arm_broker cliente --ros-args \
    -p client_id:="$CLIENTE" \
    -p priority:="$PRIORIDAD"
