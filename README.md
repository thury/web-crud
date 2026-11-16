# web-crud

Inventario y pedidos para una tienda, hecho con Django 5.2 LTS. Pensado para
correr en un equipo dentro del local del cliente (Nginx + Gunicorn + SQLite),
sin depender de internet.

## Qué incluye

- **Productos, clientes y pedidos** con control de stock: confirmar un pedido
  descuenta el inventario, cancelarlo lo devuelve, y el precio de cada línea
  queda congelado al venderse.
- **Columnas personalizadas**: el cliente agrega columnas (texto, número, fecha,
  sí/no o lista) a productos, clientes o pedidos desde *Columnas personalizadas*,
  sin tocar código. Desactivar una columna la oculta sin borrar sus datos.
- **Seguridad base**: contraseñas con Argon2, cookies `HttpOnly`/`Secure`, CSRF,
  HTTPS forzado detrás de Nginx, `SECRET_KEY` obligatoria fuera de desarrollo.

## Desarrollo

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=1            # clave de desarrollo, sin HTTPS forzado
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver       # http://127.0.0.1:8000/admin/
```

Pruebas: `DJANGO_DEBUG=1 python manage.py test`

## Despliegue (servidor del cliente)

Todo está en `deploy/`:

- `env.example`: variables de entorno (se copia a `/etc/web-crud/env`).
- `gunicorn.service`: unidad de systemd.
- `deploy.sh`: actualiza la app (respaldo, `git pull`, migraciones, estáticos, reinicio).

La configuración de Nginx se agrega después.
