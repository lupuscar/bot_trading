"""
Configuración WSGI para BotTrading.
Expone la variable de módulo 'application' para servidores WSGI como Gunicorn.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

application = get_wsgi_application()
