#!/usr/bin/env bash
# Crea (o recrea desde cero) el entorno virtual de DrawEngine e instala requirements.txt.
cd "$(dirname "$0")" || exit 1

echo "=== Creando el entorno virtual de DrawEngine ==="

PY=""
for c in python3.13 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: No encontré python3. Instálalo con el gestor de paquetes de tu distro."
  read -rp "Presiona Enter para salir..." _
  exit 1
fi

if [ -d venv ]; then
  echo "Ya existe la carpeta venv. Borrándola para recrearla limpia..."
  rm -rf venv
fi

if ! "$PY" -m venv venv; then
  rm -rf venv
  echo
  echo "ERROR: No se pudo crear el venv."
  echo "En Debian/Ubuntu/Mint instala el módulo con: sudo apt install python3-venv"
  read -rp "Presiona Enter para salir..." _
  exit 1
fi

echo
echo "=== Instalando dependencias (requirements.txt) ==="
venv/bin/python -m pip install --upgrade pip
if ! venv/bin/python -m pip install -r requirements.txt; then
  echo
  echo "ERROR: Falló la instalación de dependencias."
  read -rp "Presiona Enter para salir..." _
  exit 1
fi

echo
echo "Listo. Ahora puedes abrir DrawEngine con ./iniciar.sh"
