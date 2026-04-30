from pathlib import Path
try:
    from decouple import config, Csv
    USE_DECOUPLE = True
except ImportError:
    import os
    def config(key, default=None, cast=None):
        val = os.environ.get(key, default)
        return cast(val) if cast and val is not None else val
    def Csv():
        return lambda v: [x.strip() for x in v.split(',')]
    USE_DECOUPLE = False

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-7e!0+ux)zenh9d2-1ldg-*l79bqsus5_m(0_f@aiyqybh@e%n)')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.sites',
    'store',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'config.context_processors.cart_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── EMAIL ────────────────────────────────────────────────────────────────────
EMAIL_HOST          = config('EMAIL_HOST',          default='smtp.gmail.com')
EMAIL_PORT          = config('EMAIL_PORT',          default=587, cast=int)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',       default=True, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER',     default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default='Gflex3D <pedidos@gflex3d.cl>')

# Si no hay credenciales SMTP, imprime emails en consola (desarrollo)
if EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── GFLEX3D ──────────────────────────────────────────────────────────────────
WHATSAPP_NUMBER     = config('WHATSAPP_NUMBER',     default='56912345678')
STORE_NAME          = config('STORE_NAME',          default='Gflex3D')
STORE_EMAIL         = config('STORE_EMAIL',         default='pedidos@gflex3d.cl')
STORE_ADMIN_EMAIL   = config('STORE_ADMIN_EMAIL',   default='admin@gflex3d.cl')

BANK_NAME           = config('BANK_NAME',           default='Banco Estado')
BANK_ACCOUNT_NAME   = config('BANK_ACCOUNT_NAME',   default='Gflex3D SpA')
BANK_RUT            = config('BANK_RUT',            default='76.XXX.XXX-X')
BANK_ACCOUNT_NUMBER = config('BANK_ACCOUNT_NUMBER', default='000-000000-00')
BANK_ACCOUNT_TYPE   = config('BANK_ACCOUNT_TYPE',   default='Cuenta Corriente')
BANK_EMAIL          = config('BANK_EMAIL',          default='pagos@gflex3d.cl')

# ── AUTH ──────────────────────────────────────────────────────────────────────
LOGIN_URL          = '/cuenta/ingresar/'
LOGIN_REDIRECT_URL = '/cuenta/perfil/'
LOGOUT_REDIRECT_URL = '/'

# ── CHILEXPRESS (opcional) ────────────────────────────────────────────────────
# Agrega tu clave al .env para activar la API real de cotización
CHILEXPRESS_API_KEY = config('CHILEXPRESS_API_KEY', default='')

# ── SITEMAP ──────────────────────────────────────────────────────────────────
SITE_ID = 1

# ── WHITENOISE (archivos estáticos en producción) ────────────────────────────
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── HANDLERS DE ERROR ─────────────────────────────────────────────────────────
handler404 = 'store.views.error_404'
handler500 = 'store.views.error_500'

# ── MERCADOPAGO ───────────────────────────────────────────────────────────────
# Obtén tus claves en https://www.mercadopago.cl/developers/panel
# ACCESS_TOKEN de prueba empieza con TEST-
# ACCESS_TOKEN de producción empieza con APP_USR-
MP_ACCESS_TOKEN = config('MP_ACCESS_TOKEN', default='')
MP_WEBHOOK_SECRET = config('MP_WEBHOOK_SECRET', default='')   # firma HMAC del webhook
SITE_DOMAIN = config('SITE_DOMAIN', default='http://127.0.0.1:8000')  # sin / al final

CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'https://program-carried-amaretto.ngrok-free.dev',
]
