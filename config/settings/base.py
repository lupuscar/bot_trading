"""
Configuración base de Django para BotTrading.
Contiene settings compartidos entre desarrollo y producción.
"""
import os
from pathlib import Path

import environ

# ============================================
# Rutas base
# ============================================
# BASE_DIR apunta a la raíz del proyecto (donde está manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Inicializar django-environ
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ['localhost']),
)

# Leer archivo .env si existe
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ============================================
# Seguridad
# ============================================
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env('DJANGO_DEBUG')
ALLOWED_HOSTS = env('DJANGO_ALLOWED_HOSTS')

# ============================================
# Aplicaciones
# ============================================
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'django_extensions',
]

LOCAL_APPS = [
    'apps.core.apps.CoreConfig',
    'apps.connectors.apps.ConnectorsConfig',
    'apps.strategies.apps.StrategiesConfig',
    'apps.backtesting.apps.BacktestingConfig',
    'apps.paper_trading.apps.PaperTradingConfig',
    'apps.live_trading.apps.LiveTradingConfig',
    'apps.dashboard.apps.DashboardConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ============================================
# Middleware
# ============================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# ============================================
# Templates
# ============================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ============================================
# Base de datos - PostgreSQL
# ============================================
DATABASES = {
    'default': {
        'ENGINE': env('DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': env('DB_NAME', default='bottradring'),
        'USER': env('DB_USER', default='bottradring'),
        'PASSWORD': env('DB_PASSWORD', default='bottradring_dev_2024'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# ============================================
# Validación de contraseñas
# ============================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================
# Internacionalización
# ============================================
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

# ============================================
# Archivos estáticos y media
# ============================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ============================================
# Primary Key por defecto
# ============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# Django REST Framework
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S%z',
}

# ============================================
# Celery
# ============================================
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/1')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutos máximo por tarea
CELERY_BEAT_SCHEDULE = {}  # Se configurará dinámicamente

# ============================================
# Redis
# ============================================
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')

# ============================================
# Logging
# ============================================
LOG_LEVEL = env('LOG_LEVEL', default='INFO')
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {module}.{funcName}:{lineno} - {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{asctime}] {levelname} - {message}',
            'style': '{',
        },
        'trading': {
            'format': '[{asctime}] {levelname} [{name}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_general': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'general.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'file_trading': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'trading.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'trading',
        },
        'file_errors': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'errors.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'ERROR',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_general'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.connectors': {
            'handlers': ['console', 'file_trading'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'apps.strategies': {
            'handlers': ['console', 'file_trading'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'apps.live_trading': {
            'handlers': ['console', 'file_trading', 'file_errors'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'apps.backtesting': {
            'handlers': ['console', 'file_trading'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'apps.paper_trading': {
            'handlers': ['console', 'file_trading'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file_general', 'file_errors'],
        'level': LOG_LEVEL,
    },
}

# ============================================
# Trading - Configuración global
# ============================================
TRADING = {
    'MIN_TIMEFRAME': '5m',
    'DEFAULT_TIMEFRAME': '1h',
    'SUPPORTED_TIMEFRAMES': ['5m', '15m', '30m', '1h', '4h', '1d', '1w'],
    'MAX_OPEN_POSITIONS': 10,
    'DEFAULT_RISK_PER_TRADE': 0.02,  # 2% del capital
    'DATA_DIR': BASE_DIR / 'data',
}
