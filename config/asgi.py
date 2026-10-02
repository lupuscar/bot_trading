"""
Configuración ASGI para BotTrading.
Necesario para WebSockets (Django Channels) en el futuro.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

application = get_asgi_application()
