from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('users/', views.user_management, name='user_management'),
    path('users/save/', views.user_save, name='user_save'),
    path('users/delete/', views.user_delete, name='user_delete'),
]
