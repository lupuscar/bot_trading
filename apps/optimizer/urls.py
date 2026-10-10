from django.urls import path
from . import views

app_name = 'optimizer'

urlpatterns = [
    path('', views.optimizer_list, name='list'),
    path('new/', views.optimizer_create, name='create'),
    path('<int:pk>/', views.optimizer_detail, name='detail'),
    path('<int:pk>/delete/', views.optimizer_delete, name='delete'),
    path('result/<int:result_id>/save/', views.optimizer_save_strategy, name='save_strategy'),
]
