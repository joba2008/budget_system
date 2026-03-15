from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('b1-vs-rebase/', views.b1_vs_rebase, name='b1_vs_rebase'),
    path('saving-detail/', views.saving_detail, name='saving_detail'),
    path('budget-heatmap/', views.budget_heatmap, name='budget_heatmap'),
    path('category-mix/', views.category_mix, name='category_mix'),
    path('yoy-comparison/', views.yoy_comparison, name='yoy_comparison'),
    path('controllable/', views.controllable, name='controllable'),
    path('budgeter-status/', views.budgeter_status_report, name='budgeter_status'),
    path('export/', views.export_report, name='export'),
]
