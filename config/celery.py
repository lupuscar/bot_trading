"""
Configuración de Celery para BotTrading.
Se carga automáticamente al arrancar Django.
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('bottradring')

# Cargar configuración desde Django settings con prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodescubrir tareas en todas las apps instaladas
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tarea de prueba para verificar que Celery funciona."""
    print(f'Request: {self.request!r}')
