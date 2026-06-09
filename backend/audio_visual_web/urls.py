"""Root URL configuration. All application endpoints live under /api/."""
from django.urls import include, path

urlpatterns = [
    path("api/", include("api.urls")),
]
