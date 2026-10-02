"""
Configuración de URL raíz del proyecto BotTrading.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    # Admin de Django
    path('admin/', admin.site.urls),

    # Dashboard principal
    path('', include('apps.dashboard.urls', namespace='dashboard')),

    # API REST
    path('api/v1/', include([
        path('connectors/', include('apps.connectors.urls', namespace='connectors')),
        path('strategies/', include('apps.strategies.urls', namespace='strategies')),
        path('backtesting/', include('apps.backtesting.urls', namespace='backtesting')),
        path('paper-trading/', include('apps.paper_trading.urls', namespace='paper_trading')),
        path('live-trading/', include('apps.live_trading.urls', namespace='live_trading')),
    ])),
]

# Debug toolbar en desarrollo
if settings.DEBUG:
    try:
        import debug_toolbar  # noqa: F401
        urlpatterns = [
            path('__debug__/', include('debug_toolbar.urls')),
        ] + urlpatterns
    except ImportError:
        pass

# Personalizar títulos del admin
admin.site.site_header = 'BotTrading Admin'
admin.site.site_title = 'BotTrading'
admin.site.index_title = 'Panel de Administración'
