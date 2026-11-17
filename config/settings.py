"""
Configuración de web-crud (Django 5.2 LTS).

Todo lo que cambia entre desarrollo y el servidor del cliente se lee de
variables de entorno (ver deploy/env.example). En el servidor las carga
systemd desde /etc/web-crud/env.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nombre, default=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return default
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí"}


def env_list(nombre):
    return [v.strip() for v in os.environ.get(nombre, "").split(",") if v.strip()]


# --- Núcleo -----------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-solo-para-desarrollo-local"
    else:
        raise ImproperlyConfigured(
            "Falta DJANGO_SECRET_KEY. Defínela en /etc/web-crud/env "
            "(o activa DJANGO_DEBUG=1 solo en desarrollo)."
        )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
# Con HTTPS, Django exige que el origen del formulario esté confiado.
# Ejemplo: DJANGO_CSRF_TRUSTED_ORIGINS=https://tienda.local,https://192.168.1.50
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tienda",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # protección CSRF
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Base de datos ----------------------------------------------------------
# SQLite en modo WAL: lecturas concurrentes sin bloquear y más tolerante a
# cortes de luz. En el servidor vive en /srv/web-crud/data (fuera de git).

DB_PATH = Path(os.environ.get("DJANGO_DB_PATH", BASE_DIR / "data" / "db.sqlite3"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
        "OPTIONS": {
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Contraseñas y sesiones -------------------------------------------------
# Argon2 es el primer hasher: las contraseñas nuevas se guardan con él.
# Los demás quedan para poder leer hashes antiguos.

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_HTTPONLY = True  # JavaScript no puede leer la cookie de sesión
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 8  # la sesión caduca a las 8 horas
CSRF_COOKIE_SAMESITE = "Lax"

# Inicio de sesión: LoginRequiredMixin manda aquí a quien no ha entrado.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"

# --- HTTPS ------------------------------------------------------------------
# Nginx termina el TLS y reenvía a Gunicorn con X-Forwarded-Proto. Si todavía
# pruebas por HTTP en la LAN, pon DJANGO_HTTPS=0 temporalmente.

HTTPS = env_bool("DJANGO_HTTPS", not DEBUG)

SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS

if HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    # HSTS empieza apagado a propósito: con un certificado autofirmado en la
    # LAN, HSTS impide al navegador aceptar la excepción. Súbelo (ej. 31536000)
    # cuando el certificado de la tienda ya sea de confianza en sus equipos.
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- Idioma, zona horaria y archivos estáticos ------------------------------

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Ciudad_Juarez"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # lo llena collectstatic; lo sirve Nginx

# --- Logs -------------------------------------------------------------------
# A la salida estándar: systemd los guarda en el journal (journalctl -u gunicorn).

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
