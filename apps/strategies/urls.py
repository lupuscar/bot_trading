from django.urls import path
from . import views

app_name = 'strategies'

urlpatterns = [
    path('', views.strategy_list, name='list'),
    path('create/', views.strategy_create, name='create'),
    path('<int:pk>/edit/', views.strategy_edit, name='edit'),
    path('<int:pk>/delete/', views.strategy_delete, name='delete'),
    path('api/params/', views.strategy_params_form, name='api_params'),
]
