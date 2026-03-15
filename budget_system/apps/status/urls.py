from django.urls import path
from . import views

app_name = 'status'

urlpatterns = [
    path('overview/', views.overview, name='overview'),
    path('update/', views.update_status, name='update_status'),
    path('submit/<str:version_name>/', views.submit_status, name='submit'),
    path('withdraw/<str:version_name>/', views.withdraw_status, name='withdraw'),
]
