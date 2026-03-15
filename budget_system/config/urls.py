"""BSA Budget System URL Configuration."""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('accounts/', include('apps.accounts.urls')),
    path('budget/', include('apps.budget.urls')),
    path('import/', include('apps.importer.urls')),
    path('reports/', include('apps.reports.urls')),
    path('status/', include('apps.status.urls')),
    path('', include('apps.dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
