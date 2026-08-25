from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from demo.views import healthz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/v1/demo/", include("demo.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
