"""API URL routing. All paths are mounted under /api/ by the project urls."""
from django.urls import path

from . import views

urlpatterns = [
    path("metrics", views.list_metrics),
    path("dataset/load", views.load_dataset),
    path("dataset/map", views.map_attributes),
    path("metrics/estimate", views.estimate_metrics),
    path("metrics/compute", views.compute_metrics),
    path("analysis/summary", views.analysis_summary),
    path("analysis/plot-data", views.plot_data),
    path("analysis/filter", views.apply_filter),
    path("export/csv", views.export_csv),
    path("export/report", views.export_report),
]
