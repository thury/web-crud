#!/usr/bin/env bash
# Despliegue de web-crud en el servidor del cliente.
#
# Uso:  sudo -u webcrud ./deploy.sh            -> despliega la rama main
#       sudo -u webcrud ./deploy.sh v1.0.1     -> despliega un tag o rama específica
set -euo pipefail

APP_DIR="/srv/web-crud"
VENV="$APP_DIR/venv"
ENV_FILE="/etc/web-crud/env"
DB_PATH="$APP_DIR/data/db.sqlite3"
BACKUP_DIR="$APP_DIR/backups"
SERVICE="gunicorn"
KEEP_BACKUPS=14
REF="${1:-main}"

cd "$APP_DIR"

# Variables de entorno de Django (SECRET_KEY, ALLOWED_HOSTS, etc.)
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

PREV_COMMIT="$(git rev-parse --short HEAD)"
BACKUP_FILE=""

on_error() {
  echo
  echo "ERROR: el despliegue falló."
  echo "  Versión anterior: $PREV_COMMIT"
  if [[ -n "$BACKUP_FILE" ]]; then
    echo "  Respaldo previo : $BACKUP_FILE"
  fi
  echo "  Para volver: git checkout $PREV_COMMIT && sudo systemctl restart $SERVICE"
  echo "  Si hubo migraciones, restaura también el respaldo de la base de datos."
}
trap on_error ERR

echo "==> 1/7 Respaldo de la base de datos"
mkdir -p "$BACKUP_DIR"
if [[ -f "$DB_PATH" ]]; then
  BACKUP_FILE="$BACKUP_DIR/pre-deploy-$(date +%F-%H%M%S).sqlite3"
  sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
  # conservar solo los últimos $KEEP_BACKUPS respaldos pre-despliegue
  ls -1t "$BACKUP_DIR"/pre-deploy-*.sqlite3 | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r rm --
else
  echo "    (no existe base de datos todavía, se omite)"
fi

echo "==> 2/7 Descargando código ($REF)"
git fetch --tags --prune origin
git checkout "$REF"
if git symbolic-ref -q HEAD >/dev/null; then
  # estamos en una rama (no en un tag): avanzar solo si es fast-forward
  git pull --ff-only origin "$REF"
fi

echo "==> 3/7 Dependencias"
"$VENV/bin/pip" install --quiet -r requirements.txt

echo "==> 4/7 Migraciones"
"$VENV/bin/python" manage.py migrate --noinput

echo "==> 5/7 Archivos estáticos"
"$VENV/bin/python" manage.py collectstatic --noinput

echo "==> 6/7 Chequeo de seguridad de Django"
"$VENV/bin/python" manage.py check --deploy

echo "==> 7/7 Reiniciando Gunicorn"
sudo systemctl restart "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE"

echo
echo "Listo: versión $(git rev-parse --short HEAD) desplegada."
