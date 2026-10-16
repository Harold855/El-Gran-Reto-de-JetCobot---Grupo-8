#!/usr/bin/env bash
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u
source /opt/ros/humble/setup.bash
source "$PROYECTO/install/setup.bash"
set -u

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-92}"   # el definido en tu terminal; 92 solo si no hay ninguno
echo "Dominio ROS: $ROS_DOMAIN_ID"

echo "=== VERIFICACION DEL BROKER ==="

echo
echo "[1] Acciones disponibles:"
timeout 8 ros2 action list

echo
echo "[2] Tipo de /move_arm:"
timeout 8 ros2 action info /move_arm

echo
echo "[2b] Tipo de /pick_place (debe haber UN solo servidor):"
timeout 8 ros2 action info /pick_place

echo
echo "[3] Publicador de /joint_states:"
timeout 8 ros2 topic info /joint_states

echo
echo "[4] Estado de la cola:"
timeout 8 ros2 topic echo /arm/queue_state --once

