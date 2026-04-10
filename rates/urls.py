from django.urls import path

from . import views

app_name = "rates"

urlpatterns = [
    path("rates/latest/", views.LatestRatesView.as_view(), name="rates-latest"),
    path("rates/history/", views.RateHistoryView.as_view(), name="rates-history"),
    path("rates/ingest/", views.IngestRateView.as_view(), name="rates-ingest"),
]
