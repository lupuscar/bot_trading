"""
Configuración de producción.
"""
from .base import *  # noqa: F401, F403

# ============================================
# Seguridad
# ============================================
DEBUG = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = env('SECURE_SSL_REDIRECT', default=True)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ============================================
# CORS en producción
# ============================================
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])  # noqa: F405

# ============================================
# Cache con Redis en producción
# ============================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://redis:6379/0'),  # noqa: F405
    }
}

# ============================================
# Archivos estáticos (nginx los servirá)
# ============================================
STATIC_ROOT = BASE_DIR / 'staticfiles'  # noqa: F405

# ============================================
# Logging menos verbose en producción
# ============================================
LOG_LEVEL = 'WARNING'
