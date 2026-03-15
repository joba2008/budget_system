"""
BSA Budget System - Base Settings
Reads configuration from config.ini
"""
import configparser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read config.ini
cfg = configparser.ConfigParser()
cfg.read(BASE_DIR / 'config.ini', encoding='utf-8')

# ---- App Config ----
SECRET_KEY = cfg.get('app', 'secret_key', fallback='django-insecure-change-me')
DEBUG = cfg.getboolean('app', 'debug', fallback=True)
ALLOWED_HOSTS = [
    h.strip() for h in cfg.get('app', 'allowed_hosts', fallback='*').split(',')
]

# ---- Database Config ----
# Application database is managed by SQLAlchemy (see config/database.py).
# Django still requires a DATABASES setting for its internals (sessions, etc.).
# Using SQLite for Django's internal tables (no application data stored here).
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_django_internal.sqlite3',
    }
}

# ---- Application Definition ----
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'django_filters',
    # Local apps
    'apps.accounts',
    'apps.budget',
    'apps.importer',
    'apps.reports',
    'apps.dashboard',
    'apps.status',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'apps.accounts.middleware.SessionAuthMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

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
                'apps.accounts.context_processors.user_role',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---- Password Validation ----
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---- Internationalization ----
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# ---- Static Files ----
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ---- Media / Uploads ----
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'uploads'

# ---- Default PK ----
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---- Auth ----
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ---- LDAP (optional) ----
LDAP_ENABLED = cfg.getboolean('ldap', 'enabled', fallback=False)
if LDAP_ENABLED:
    LDAP_SERVER_URI = cfg.get('ldap', 'server_uri')
    LDAP_BIND_DN = cfg.get('ldap', 'bind_dn')
    LDAP_BIND_PASSWORD = cfg.get('ldap', 'bind_password')
    LDAP_SEARCH_BASE = cfg.get('ldap', 'search_base')
    LDAP_USER_ATTR = cfg.get('ldap', 'user_attr', fallback='sAMAccountName')

# ---- Redis (optional) ----
REDIS_ENABLED = cfg.getboolean('redis', 'enabled', fallback=False)
if REDIS_ENABLED:
    REDIS_HOST = cfg.get('redis', 'host', fallback='127.0.0.1')
    REDIS_PORT = cfg.get('redis', 'port', fallback='6379')
    REDIS_DB = cfg.get('redis', 'db', fallback='0')
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}',
        }
    }
