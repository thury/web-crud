#!/usr/bin/env bash
# Preparación única del servidor del cliente (Debian/Ubuntu).
# Se puede repetir sin dañar nada: no pisa el env, el certificado ni la base.
#
#   1) Clonar el repo en /srv/web-crud (ver deploy/README.md)
#   2) sudo /srv/web-crud/deploy/instalar.sh tienda.local 192.168.1.50
#   3) sudo -u webcrud /srv/web-crud/deploy/deploy.sh
set -euo pipefail

APP_DIR="/srv/web-crud"
APP_USER="webcrud"
ENV_DIR="/etc/web-crud"
SSL_DIR="/etc/ssl/web-crud"

[[ $EUID -eq 0 ]] || { echo "Ejecuta con sudo." >&2; exit 1; }

HOST="${1:-}"
IP="${2:-}"
if [[ ! "$HOST" =~ ^[A-Za-z0-9.-]+$ || ! "$IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  echo "Uso: sudo $0 <nombre-host> <ip-del-servidor>   (ej. tienda.local 192.168.1.50)" >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$REPO_DIR" != "$APP_DIR" ]]; then
  echo "El repo debe estar en $APP_DIR (ahora está en $REPO_DIR)." >&2
  exit 1
fi

echo "==> 1/8 Paquetes (nginx, python3-venv, sqlite3, git, openssl)"
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  nginx python3-venv sqlite3 git openssl

echo "==> 2/8 Usuario y carpetas"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home-dir /var/lib/webcrud \
  --create-home --shell /usr/sbin/nologin "$APP_USER"
# El código es del usuario webcrud con grupo www-data (Nginx necesita leer los estáticos).
# data/ y backups/ se quedan fuera: solo webcrud entra ahí.
find "$APP_DIR" -path "$APP_DIR/data" -prune -o -path "$APP_DIR/backups" -prune -o \
  -exec chown "$APP_USER:www-data" {} +
chmod 750 "$APP_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 700 "$APP_DIR/data" "$APP_DIR/backups"
[[ -x "$APP_DIR/venv/bin/pip" ]] || runuser -u "$APP_USER" -- python3 -m venv "$APP_DIR/venv"
chmod +x "$APP_DIR/deploy/deploy.sh"

echo "==> 3/8 Variables de entorno ($ENV_DIR/env)"
install -d -o root -g "$APP_USER" -m 750 "$ENV_DIR"
if [[ ! -f "$ENV_DIR/env" ]]; then
  KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
  install -o root -g "$APP_USER" -m 640 "$APP_DIR/deploy/env.example" "$ENV_DIR/env"
  sed -i \
    -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$KEY|" \
    -e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$HOST,$IP|" \
    -e "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=https://$HOST,https://$IP|" \
    "$ENV_DIR/env"
else
  echo "    (ya existe, no se toca)"
fi

echo "==> 4/8 Certificado HTTPS autofirmado ($SSL_DIR)"
install -d -o root -g root -m 755 "$SSL_DIR"
if [[ ! -f "$SSL_DIR/web-crud.crt" ]]; then
  openssl req -x509 -newkey rsa:4096 -sha256 -days 825 -nodes \
    -keyout "$SSL_DIR/web-crud.key" -out "$SSL_DIR/web-crud.crt" \
    -subj "/CN=$HOST" -addext "subjectAltName=DNS:$HOST,IP:$IP"
  chmod 600 "$SSL_DIR/web-crud.key"
else
  echo "    (ya existe, no se toca)"
fi

echo "==> 5/8 Servicio de Gunicorn (systemd)"
install -m 644 "$APP_DIR/deploy/gunicorn.service" /etc/systemd/system/gunicorn.service

echo "==> 6/8 Sitio de Nginx"
install -m 644 "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/web-crud
sed -i -e "s|__HOST__|$HOST|g" -e "s|__IP__|$IP|g" /etc/nginx/sites-available/web-crud
ln -sf /etc/nginx/sites-available/web-crud /etc/nginx/sites-enabled/web-crud
rm -f /etc/nginx/sites-enabled/default
nginx -t

echo "==> 7/8 Permiso para que deploy.sh reinicie Gunicorn (solo eso)"
SUDOERS_TMP="$(mktemp)"
echo "$APP_USER ALL=(root) NOPASSWD: $(command -v systemctl) restart gunicorn" > "$SUDOERS_TMP"
visudo -cf "$SUDOERS_TMP"
install -m 440 -o root -g root "$SUDOERS_TMP" /etc/sudoers.d/web-crud
rm -f "$SUDOERS_TMP"

echo "==> 8/8 Arranque automático al encender el equipo"
systemctl daemon-reload
systemctl enable gunicorn nginx
systemctl restart nginx

cat <<FIN

Listo. Falta:
  1) Primer despliegue (migraciones, estáticos, arranque de Gunicorn):
       sudo -u $APP_USER $APP_DIR/deploy/deploy.sh
  2) Crear el usuario administrador:
       sudo -u $APP_USER bash -c 'set -a; source $ENV_DIR/env; set +a; cd $APP_DIR; venv/bin/python manage.py createsuperuser'
  3) Abrir https://$HOST (el navegador avisará del certificado autofirmado).
FIN
