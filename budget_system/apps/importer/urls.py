from django.urls import path
from . import views

app_name = 'importer'

urlpatterns = [
    path('sample.csv', views.sample_csv_download, name='sample_csv'),
    path('template/download/', views.template_download, name='template_download'),
    path('upload/', views.upload_view, name='upload'),
    path('confirm/', views.confirm_import, name='confirm'),
]
