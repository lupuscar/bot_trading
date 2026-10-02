"""
Configuración de desarrollo.
"""
from .base import *  # noqa: F401, F403

# ============================================
# Debug
# ============================================
DEBUG = True

# ============================================
# Hosts permitidos en desarrollo
# ============================================
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# ============================================
# Apps adicionales para desarrollo
# ============================================
try:
    import debug_toolbar  # noqa: F401
    INSTALLED_APPS += ['debug_toolbar']  # noqa: F405
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')  # noqa: F405
    INTERNAL_IPS = ['127.0.0.1']
except ImportError:
    pass

# ============================================
# Email (consola en desarrollo)
# ============================================
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ============================================
# CORS en desarrollo
# ============================================
CORS_ALLOW_ALL_ORIGINS = True

# ============================================
# Cache en desarrollo (local-memory)
# ============================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ============================================
# Logging más verbose en desarrollo
# ============================================
LOG_LEVEL = 'DEBUG'
