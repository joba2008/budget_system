from django.urls import path
from . import views, api

app_name = 'budget'

urlpatterns = [
    path('versions/', views.version_list, name='version_list'),
    path('versions/<str:version_name>/edit/', views.budget_edit, name='budget_edit'),
    path('versions/<str:v1_name>/compare/<str:v2_name>/', views.version_compare, name='version_compare'),
    # API endpoints
    path('api/cell/save/', api.cell_save, name='api_cell_save'),
    path('api/row/data/', api.row_data, name='api_row_data'),
    path('api/recalc-rebase/', api.recalc_rebase, name='api_recalc_rebase'),
]
