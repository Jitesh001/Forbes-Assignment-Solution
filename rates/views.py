import logging
import time

from django.core.cache import cache
from django.db.models import Max, Subquery, OuterRef
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import IngestTokenAuthentication
from .models import Rate
from .permissions import IsIngestAuthenticated
from .serializers import IngestSerializer, RateHistorySerializer, RateSerializer
from .services import ingest_single_record

logger = logging.getLogger("rates")

CACHE_TTL = 300  # 5 minutes


class LatestRatesView(generics.ListAPIView):
    """
    GET /api/rates/latest/
    Returns the most recent rate per provider, with optional ?type= filter.
    Cached for 5 minutes; invalidated on new ingest.
    """

    serializer_class = RateSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        rate_type = self.request.query_params.get("type")
        subquery_filters = {
            "provider": OuterRef("provider"),
            "rate_type": OuterRef("rate_type"),
        }
        latest_dates = (
            Rate.objects.filter(**subquery_filters)
            .order_by("-effective_date")
            .values("effective_date")[:1]
        )
        qs = Rate.objects.filter(effective_date=Subquery(latest_dates))
        if rate_type:
            qs = qs.filter(rate_type=rate_type)
        return qs.order_by("provider", "rate_type")

    def list(self, request, *args, **kwargs):
        rate_type = request.query_params.get("type")
        cache_key = f"rates:latest:{rate_type or 'all'}"

        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        start = time.monotonic()
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        elapsed_ms = (time.monotonic() - start) * 1000
        if elapsed_ms > 200:
            logger.warning("slow_query", extra={"view": "LatestRatesView", "elapsed_ms": round(elapsed_ms, 1)})

        cache.set(cache_key, data, CACHE_TTL)
        return Response(data)


class RateHistoryView(generics.ListAPIView):
    """
    GET /api/rates/history/?provider=Chase&type=30yr_fixed_mortgage&from=2025-01-01&to=2025-12-31
    Paginated time-series for a provider + type combination.
    """

    serializer_class = RateHistorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        start = time.monotonic()

        provider = self.request.query_params.get("provider")
        rate_type = self.request.query_params.get("type")
        date_from = self.request.query_params.get("from")
        date_to = self.request.query_params.get("to")

        if not provider or not rate_type:
            return Rate.objects.none()

        qs = Rate.objects.filter(provider=provider, rate_type=rate_type)

        if date_from:
            qs = qs.filter(effective_date__gte=date_from)
        if date_to:
            qs = qs.filter(effective_date__lte=date_to)

        qs = qs.order_by("effective_date")

        elapsed_ms = (time.monotonic() - start) * 1000
        if elapsed_ms > 200:
            logger.warning("slow_query", extra={"view": "RateHistoryView", "elapsed_ms": round(elapsed_ms, 1)})

        return qs

    def list(self, request, *args, **kwargs):
        provider = request.query_params.get("provider")
        rate_type = request.query_params.get("type")

        if not provider or not rate_type:
            return Response(
                {"error": "Both 'provider' and 'type' query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().list(request, *args, **kwargs)


class IngestRateView(APIView):
    """
    POST /api/rates/ingest/
    Authenticated webhook endpoint. Accepts JSON, validates, writes to DB,
    and invalidates relevant cache keys.
    """

    authentication_classes = [IngestTokenAuthentication]
    permission_classes = [IsIngestAuthenticated]

    def post(self, request):
        serializer = IngestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rate = ingest_single_record(serializer.validated_data)
        except Exception:
            logger.exception("ingest_api_failed")
            return Response(
                {"error": "Internal error during ingestion."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Invalidate caches
        self._invalidate_cache(rate.rate_type)

        return Response(
            RateSerializer(rate).data,
            status=status.HTTP_201_CREATED,
        )

    def _invalidate_cache(self, rate_type: str):
        """Clear relevant cache keys after a new record is ingested."""
        cache.delete("rates:latest:all")
        cache.delete(f"rates:latest:{rate_type}")
