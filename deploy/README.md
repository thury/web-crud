# Instalar web-crud en el servidor del cliente

Probado en la idea para Debian/Ubuntu con systemd. Todo corre en el equipo del
cliente, en su red local: Nginx (HTTPS) → socket Unix → Gunicorn → Django → SQLite.

## Primera vez

1. **Llave de solo lectura para el repo privado** (el usuario `webcrud` la usa en cada actualización):
   ```bash
   sudo useradd --system --home-dir /var/lib/webcrud --create-home --shell /usr/sbin/nologin webcrud
   sudo -u webcrud ssh-keygen -t ed25519 -N "" -f /var/lib/webcrud/.ssh/id_ed25519
   sudo cat /var/lib/webcrud/.ssh/id_ed25519.pub   # súbela en GitHub → Settings → Deploy keys (sin permiso de escritura)
   ```
2. **Clonar** (como `webcrud`, para que `git pull` funcione después):
   ```bash
   sudo install -d -o webcrud -g webcrud /srv/web-crud
   sudo -u webcrud git clone git@github.com:thury/web-crud.git /srv/web-crud
   ```
3. **Instalar** (usa el nombre y la IP fija que tendrá el servidor en la red del cliente):
   ```bash
   sudo /srv/web-crud/deploy/instalar.sh tienda.local 192.168.1.50
   ```
4. Seguir los dos pasos que imprime el script: primer `deploy.sh` y `createsuperuser`.

Dale al servidor una **IP fija** (reserva en el router) para que el certificado y `ALLOWED_HOSTS` no se rompan.

## Actualizar

```bash
sudo -u webcrud /srv/web-crud/deploy/deploy.sh          # rama main
sudo -u webcrud /srv/web-crud/deploy/deploy.sh v1.0.1   # un tag
```

Hace respaldo de la base antes, migra, junta estáticos y reinicia Gunicorn.

## Revisar que todo está vivo

```bash
systemctl status gunicorn nginx
journalctl -u gunicorn -f        # logs de la app
sudo tail -f /var/log/nginx/error.log
sudo nginx -t                    # validar la config antes de recargar
```

Prueba del arranque automático: reinicia el equipo (`sudo reboot`) y entra a la página sin tocar nada.

## Qué hay en cada pieza

| Archivo | Va a | Para qué |
|---|---|---|
| `nginx.conf` | `/etc/nginx/sites-available/web-crud` | HTTPS, estáticos, proxy a Gunicorn, límite de intentos en `/login/` |
| `gunicorn.service` | `/etc/systemd/system/gunicorn.service` | Arranca Gunicorn al encender y lo reinicia si falla |
| `env.example` | `/etc/web-crud/env` | Clave secreta y ajustes (el real nunca va a git) |
| `deploy.sh` | se corre desde el repo | Actualización con respaldo previo |

## Notas de seguridad

- **Certificado autofirmado:** el navegador avisa la primera vez. Para quitar el aviso, instala `/etc/ssl/web-crud/web-crud.crt` como certificado de confianza en las PC de la tienda. Dura 825 días; para renovarlo, borra los dos archivos de `/etc/ssl/web-crud/`, vuelve a correr `instalar.sh` y reinicia Nginx.
- **HSTS** está en 0 a propósito (ver `settings.py`). Súbelo solo cuando el certificado ya sea de confianza en todas las PC; `manage.py check --deploy` avisará de eso mientras tanto.
- **Firewall:** abre solo SSH, 80 y 443. Con ufw: `sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable` (permite SSH *antes* de activarlo).
- No expongas el puerto 443 a internet desde el router: la idea es que solo se use dentro del local.
- El límite de Nginx en `/login/` responde 429 si alguien insiste demasiado; espera un minuto.
