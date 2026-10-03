from django.urls import path
from . import views

app_name = 'backtesting'

urlpatterns = [
    path('', views.run_list, name='run_list'),
    path('new/', views.run_create, name='run_create'),
    path('<int:pk>/', views.run_detail, name='run_detail'),
    path('<int:pk>/delete/', views.run_delete, name='run_delete'),
]
