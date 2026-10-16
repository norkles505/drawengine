#!/usr/bin/env bash
# Inicia DrawEngine en Linux (equivalente al compilar.bat de Windows).
cd "$(dirname "$0")" || exit 1

echo "Iniciando DrawEngine..."

# Si todavía no hay entorno virtual, lo crea
if [ ! -x venv/bin/python ]; then
  echo "No encontré el entorno virtual (venv). Creándolo..."
  bash ./crear-venv.sh || exit 1
fi

venv/bin/python main.py
codigo=$?

if [ $codigo -ne 0 ]; then
  echo
  echo "La app terminó con un error. Revisa el mensaje de arriba."
  read -rp "Presiona Enter para cerrar..." _
fi
exit $codigo
