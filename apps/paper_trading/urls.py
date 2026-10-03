from django.urls import path

from . import views

app_name = 'paper_trading'

urlpatterns = [
    path('', views.paper_list, name='paper_list'),
    path('<int:pk>/', views.paper_detail, name='paper_detail'),
]
