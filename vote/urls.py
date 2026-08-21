from django.urls import path

from . import views
from .internal_api import active_users

urlpatterns = [
    path('internal/active-users/', active_users, name='internal_active_users'),
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('polls/', views.poll_list, name='poll_list'),
    path('polls/new/', views.poll_create, name='poll_create'),
    path('polls/<int:pk>/', views.poll_detail, name='poll_detail'),
    path('polls/<int:pk>/edit/', views.poll_edit, name='poll_edit'),
    path('polls/<int:pk>/options/add/', views.poll_option_add, name='poll_option_add'),
    path('polls/<int:pk>/close/', views.poll_close, name='poll_close'),
]
