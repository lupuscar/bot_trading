from django.urls import path
from . import views

app_name = 'connectors'

urlpatterns = [
    path('', views.connector_list, name='list'),
    path('create/', views.connector_create, name='create'),
    path('<int:pk>/edit/', views.connector_edit, name='edit'),
    path('<int:pk>/delete/', views.connector_delete, name='delete'),
    path('<int:pk>/test/', views.connector_test, name='test'),
]
