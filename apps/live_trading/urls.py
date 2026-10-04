from django.urls import path
from . import views

app_name = 'live_trading'

urlpatterns = [
    path('', views.bot_list, name='list'),
    path('create/', views.bot_create, name='create'),
    path('<int:pk>/edit/', views.bot_edit, name='edit'),
    path('<int:pk>/delete/', views.bot_delete, name='delete'),
    path('<int:pk>/toggle/', views.bot_toggle, name='toggle'),
    path('<int:pk>/trades/', views.bot_trades, name='trades'),
    path('<int:pk>/logs/', views.bot_logs, name='logs'),
]
