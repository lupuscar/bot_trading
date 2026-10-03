from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/action/', views.system_action, name='system_action'),
    path('api/chart-data/', views.get_chart_data, name='chart_data'),
]
